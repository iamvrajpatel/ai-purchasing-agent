from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.integrations.mock_supplier import MockSupplierClient
from app.models import AgentEvent, PurchaseOrder, PurchaseOrderItem, PurchaseOrderRecoveryCase
from app.repositories.purchasing_repository import PurchasingRepository
from app.schemas.recovery import RecoveryCaseDetail, RecoveryProposedAction
from app.services.constraint_engine import ConstraintEngine
from app.services.inventory_service import InventoryService
from app.services.supplier_service import SupplierService
from app.utils.calculations import money, round_up_to_multiple
from app.utils.exceptions import AuthorizationError, NotFoundError, ValidationError


class PurchaseOrderRecoveryService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.repo = PurchasingRepository(db)
        self.inventory_service = InventoryService(db)
        self.supplier_service = SupplierService(db)
        self.constraint_engine = ConstraintEngine(db)
        self.supplier_client = MockSupplierClient(db)

    def get_for_purchase_order(self, purchase_order_id: int) -> PurchaseOrderRecoveryCase | None:
        return self.db.scalar(
            select(PurchaseOrderRecoveryCase)
            .where(PurchaseOrderRecoveryCase.purchase_order_id == purchase_order_id)
            .order_by(PurchaseOrderRecoveryCase.created_at.desc())
        )

    def analyze_purchase_order(self, purchase_order_id: int, agent_run_id: int | None = None) -> PurchaseOrderRecoveryCase:
        purchase_order = self._purchase_order(purchase_order_id)
        item = self._single_item(purchase_order)
        requested_quantity = item.quantity
        confirmed_quantity = self._confirmed_quantity(purchase_order)
        shortfall_quantity = max(0, requested_quantity - confirmed_quantity)
        if shortfall_quantity <= 0:
            raise ValidationError("Purchase order does not have a supplier shortfall")

        recovery_case = self.get_for_purchase_order(purchase_order_id)
        if not recovery_case:
            recovery_case = PurchaseOrderRecoveryCase(purchase_order_id=purchase_order_id, agent_run_id=agent_run_id)
            self.db.add(recovery_case)
            self.db.flush()
        elif agent_run_id and not recovery_case.agent_run_id:
            recovery_case.agent_run_id = agent_run_id

        requirement = self.inventory_service.calculate_purchase_requirement(
            item.product_id,
            purchase_order.warehouse_id,
            self.settings.planning_horizon_days,
        )
        remaining_requirement_after_confirmed = max(0, requirement.required_quantity - confirmed_quantity)
        evidence: dict = {
            "supplier_outcome": purchase_order.supplier_response_json or {},
            "requested_quantity": requested_quantity,
            "confirmed_quantity": confirmed_quantity,
            "shortfall_quantity": shortfall_quantity,
            "calculated_requirement": requirement.required_quantity,
            "remaining_requirement_after_confirmed": remaining_requirement_after_confirmed,
            "sellable_inventory": requirement.sellable_inventory,
            "timely_incoming_quantity": requirement.timely_incoming_quantity,
            "forecast_demand": requirement.forecast_demand,
            "safety_stock": requirement.safety_stock,
            "supplier_options": [],
        }

        recovery_case.requested_quantity = requested_quantity
        recovery_case.confirmed_quantity = confirmed_quantity
        recovery_case.shortfall_quantity = shortfall_quantity

        if remaining_requirement_after_confirmed <= 0:
            self._store_decision(
                recovery_case,
                status="RESOLVED",
                decision="NO_ACTION_REQUIRED",
                reasoning="Confirmed supplier quantity plus available and incoming inventory covers projected demand.",
                evidence=evidence,
                risks=[],
                missing_information=[],
                proposed_action=None,
            )
            return recovery_case

        failed_reasons: list[str] = []
        for supplier in self.supplier_service.list_options(item.product_id):
            if supplier.supplier_id == purchase_order.supplier_id:
                continue
            proposed_quantity = round_up_to_multiple(max(shortfall_quantity, supplier.minimum_order_quantity), supplier.order_multiple)
            constraint_result = self.constraint_engine.evaluate(
                item.product_id,
                purchase_order.warehouse_id,
                supplier.supplier_id,
                proposed_quantity,
                requirement.required_by_date,
            )
            option = {
                "supplier_id": supplier.supplier_id,
                "supplier_name": supplier.supplier_name,
                "quantity": proposed_quantity,
                "unit_price": str(supplier.unit_price),
                "valid": constraint_result.valid,
                "failed_checks": [
                    {"name": check.name, "status": check.status, "details": check.details}
                    for check in constraint_result.checks
                    if check.status in {"FAIL", "UNKNOWN"}
                ],
            }
            evidence["supplier_options"].append(option)
            if constraint_result.valid:
                total = money(Decimal(proposed_quantity) * supplier.unit_price)
                proposed_action = RecoveryProposedAction(
                    purchase_order_id=purchase_order.id,
                    product_id=item.product_id,
                    warehouse_id=purchase_order.warehouse_id,
                    supplier_id=supplier.supplier_id,
                    quantity=proposed_quantity,
                    unit_price=supplier.unit_price,
                    total_amount=total,
                    expected_delivery_date=date.today() + timedelta(days=supplier.lead_time_days),
                    decision="SOURCE_REMAINDER",
                )
                self._store_decision(
                    recovery_case,
                    status="PENDING_APPROVAL",
                    decision="SOURCE_REMAINDER",
                    reasoning=f"Supplier confirmed {confirmed_quantity} of {requested_quantity}; source the remaining {shortfall_quantity} units from {supplier.supplier_name}.",
                    evidence=evidence,
                    risks=[],
                    missing_information=[],
                    proposed_action=proposed_action.model_dump(mode="json"),
                )
                self._add_event(agent_run_id, "RECOVERY_PROPOSED", "Recovery analysis proposed a supplemental purchase order.", recovery_case)
                return recovery_case
            failed_reasons.extend(f"{supplier.supplier_name}: {violation.code}" for violation in constraint_result.violations)

        self._store_decision(
            recovery_case,
            status="ESCALATED",
            decision="ESCALATE",
            reasoning="Supplier confirmed fewer units than requested, and no alternate supplier passed mandatory constraints.",
            evidence=evidence,
            risks=["No feasible alternate supplier found", *failed_reasons],
            missing_information=[] if evidence["supplier_options"] else ["No active alternate supplier catalog rows were available"],
            proposed_action=None,
        )
        self._add_event(agent_run_id, "RECOVERY_ESCALATED", "Recovery analysis could not find a feasible supplemental purchase order.", recovery_case)
        return recovery_case

    def approve(self, recovery_case_id: int, buyer_identity: str) -> PurchaseOrderRecoveryCase:
        self._assert_buyer(buyer_identity)
        recovery_case = self._recovery_case(recovery_case_id)
        if recovery_case.status != "PENDING_APPROVAL" or not recovery_case.proposed_action_json:
            raise ValidationError("Recovery case is not awaiting approval")
        recovery_case.status = "APPROVED"
        recovery_case.approved_by = buyer_identity
        recovery_case.approved_at = datetime.now(timezone.utc)
        return recovery_case

    def execute(self, recovery_case_id: int) -> PurchaseOrder:
        recovery_case = self._recovery_case(recovery_case_id)
        if recovery_case.supplemental_purchase_order_id:
            return self._purchase_order(recovery_case.supplemental_purchase_order_id)
        if recovery_case.status != "APPROVED" or not recovery_case.proposed_action_json:
            raise ValidationError("Recovery case must be approved before execution")

        proposed = RecoveryProposedAction.model_validate(recovery_case.proposed_action_json)
        original = self._purchase_order(proposed.purchase_order_id)
        idempotency_key = f"recovery-case-{recovery_case.id}-original-po-{original.id}"
        existing = self.repo.purchase_order_by_idempotency(idempotency_key)
        if existing:
            recovery_case.supplemental_purchase_order_id = existing.id
            return existing

        constraint_result = self.constraint_engine.evaluate(
            proposed.product_id,
            proposed.warehouse_id,
            proposed.supplier_id,
            proposed.quantity,
            proposed.expected_delivery_date,
        )
        if not constraint_result.valid:
            recovery_case.status = "EXECUTION_BLOCKED"
            recovery_case.risks_json = ["Current-state revalidation failed"]
            recovery_case.evidence_json = {
                **(recovery_case.evidence_json or {}),
                "execution_constraint_result": constraint_result.model_dump(mode="json"),
            }
            raise ValidationError("Recovery execution revalidation failed")

        budget = self.repo.lock_current_budget(proposed.warehouse_id, PurchasingRepository.budget_period_for(proposed.expected_delivery_date))
        if not budget:
            raise ValidationError("Budget record is missing")
        if proposed.total_amount > budget.available_budget:
            recovery_case.status = "EXECUTION_BLOCKED"
            recovery_case.risks_json = ["Budget changed after recovery approval"]
            raise ValidationError("Budget changed after recovery approval; execution stopped")

        purchase_order = PurchaseOrder(
            supplier_id=proposed.supplier_id,
            warehouse_id=proposed.warehouse_id,
            status="EXECUTED",
            expected_delivery_date=proposed.expected_delivery_date,
            total_amount=proposed.total_amount,
            source_recommendation_id=original.source_recommendation_id,
            agent_run_id=recovery_case.agent_run_id,
            idempotency_key=idempotency_key,
        )
        purchase_order.items.append(
            PurchaseOrderItem(
                product_id=proposed.product_id,
                quantity=proposed.quantity,
                unit_price=proposed.unit_price,
                line_total=proposed.total_amount,
            )
        )
        budget.committed_amount += proposed.total_amount
        self.db.add(purchase_order)
        self.db.flush()

        supplier_result = self.supplier_client.submit_purchase_order(
            proposed.supplier_id,
            proposed.product_id,
            proposed.quantity,
            idempotency_key,
        )
        purchase_order.supplier_confirmation_status = supplier_result.status
        purchase_order.supplier_response_json = supplier_result.response
        purchase_order.external_reference = supplier_result.external_reference
        purchase_order.status = "VALIDATED" if supplier_result.status == "CONFIRMED" and supplier_result.confirmed_quantity == proposed.quantity else "VALIDATION_FAILED"

        recovery_case.supplemental_purchase_order_id = purchase_order.id
        recovery_case.status = "EXECUTED" if purchase_order.status == "VALIDATED" else "VALIDATION_FAILED"
        self._add_event(
            recovery_case.agent_run_id,
            "RECOVERY_ORDER_EXECUTED",
            f"Created supplemental purchase order {purchase_order.id}",
            recovery_case,
            {"supplemental_purchase_order_id": purchase_order.id, "supplier_status": supplier_result.status},
        )
        return purchase_order

    def to_detail(self, recovery_case: PurchaseOrderRecoveryCase) -> RecoveryCaseDetail:
        approval = None
        if recovery_case.status in {"PENDING_APPROVAL", "APPROVED", "EXECUTED", "VALIDATION_FAILED", "EXECUTION_BLOCKED"}:
            approval = {
                "status": "APPROVED" if recovery_case.approved_at else "PENDING",
                "approved_by": recovery_case.approved_by,
                "approved_at": recovery_case.approved_at.isoformat() if recovery_case.approved_at else None,
            }
        return RecoveryCaseDetail(
            id=recovery_case.id,
            purchase_order_id=recovery_case.purchase_order_id,
            agent_run_id=recovery_case.agent_run_id,
            supplemental_purchase_order_id=recovery_case.supplemental_purchase_order_id,
            status=recovery_case.status,
            decision=recovery_case.decision,
            requested_quantity=recovery_case.requested_quantity,
            confirmed_quantity=recovery_case.confirmed_quantity,
            shortfall_quantity=recovery_case.shortfall_quantity,
            reasoning=recovery_case.reasoning,
            evidence=recovery_case.evidence_json or {},
            risks=recovery_case.risks_json or [],
            missing_information=recovery_case.missing_information_json or [],
            proposed_action=recovery_case.proposed_action_json,
            approval=approval,
            created_at=recovery_case.created_at,
            updated_at=recovery_case.updated_at,
        )

    def _store_decision(
        self,
        recovery_case: PurchaseOrderRecoveryCase,
        status: str,
        decision: str,
        reasoning: str,
        evidence: dict,
        risks: list[str],
        missing_information: list[str],
        proposed_action: dict | None,
    ) -> None:
        recovery_case.status = status
        recovery_case.decision = decision
        recovery_case.reasoning = reasoning
        recovery_case.evidence_json = evidence
        recovery_case.risks_json = risks
        recovery_case.missing_information_json = missing_information
        recovery_case.proposed_action_json = proposed_action

    def _purchase_order(self, purchase_order_id: int) -> PurchaseOrder:
        purchase_order = self.db.scalar(
            select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(PurchaseOrder.id == purchase_order_id)
        )
        if not purchase_order:
            raise NotFoundError("Purchase order not found")
        return purchase_order

    def _recovery_case(self, recovery_case_id: int) -> PurchaseOrderRecoveryCase:
        recovery_case = self.db.get(PurchaseOrderRecoveryCase, recovery_case_id)
        if not recovery_case:
            raise NotFoundError("Recovery case not found")
        return recovery_case

    @staticmethod
    def _single_item(purchase_order: PurchaseOrder) -> PurchaseOrderItem:
        if not purchase_order.items:
            raise ValidationError("Purchase order has no items")
        return purchase_order.items[0]

    @staticmethod
    def _confirmed_quantity(purchase_order: PurchaseOrder) -> int:
        response = purchase_order.supplier_response_json or {}
        if response.get("confirmed_quantity") is not None:
            return int(response["confirmed_quantity"])
        return 0 if purchase_order.supplier_confirmation_status in {"REJECTED", "PARTIALLY_CONFIRMED"} else PurchaseOrderRecoveryService._single_item(purchase_order).quantity

    def _add_event(
        self,
        agent_run_id: int | None,
        event_type: str,
        message: str,
        recovery_case: PurchaseOrderRecoveryCase,
        extra: dict | None = None,
    ) -> None:
        if not agent_run_id:
            return
        metadata = {"recovery_case_id": recovery_case.id, "purchase_order_id": recovery_case.purchase_order_id}
        metadata.update(extra or {})
        self.db.add(AgentEvent(agent_run_id=agent_run_id, event_type=event_type, message=message, metadata_json=metadata))

    def _assert_buyer(self, buyer_identity: str) -> None:
        if buyer_identity != self.settings.mock_buyer_user:
            raise AuthorizationError("Only the configured buyer can approve or reject recovery proposals")
