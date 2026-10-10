from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from app.integrations.mock_supplier import MockSupplierClient
from app.models import AgentEvent, ApprovalRequest, PurchaseOrder, PurchaseOrderItem
from app.repositories.purchasing_repository import PurchasingRepository
from app.schemas.purchasing import ProposedAction
from app.services.constraint_engine import ConstraintEngine
from app.services.recovery_service import RecoveryService
from app.services.validation_service import ValidationService
from app.utils.calculations import money
from app.utils.exceptions import NotFoundError, ValidationError


class PurchaseOrderService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PurchasingRepository(db)
        self.constraint_engine = ConstraintEngine(db)
        self.validation_service = ValidationService(db)
        self.recovery_service = RecoveryService(db)
        self.supplier_client = MockSupplierClient(db)

    def execute_agent_run(self, agent_run_id: int) -> PurchaseOrder:
        purchase_orders = self.execute_agent_run_orders(agent_run_id)
        if not purchase_orders:
            raise ValidationError("No purchase orders were created")
        return purchase_orders[0]

    def execute_agent_run_orders(self, agent_run_id: int) -> list[PurchaseOrder]:
        run = self.repo.agent_run(agent_run_id)
        if not run:
            raise NotFoundError("Agent run not found")
        if not run.evidence_snapshot:
            raise ValidationError("Agent run has no executable proposed action")

        if self.repo.pending_approvals_for_run(agent_run_id):
            raise ValidationError("Proposal is awaiting approval")
        if any(approval.status == "REJECTED" for approval in self.repo.approvals_for_run(agent_run_id)):
            raise ValidationError("One or more proposal approvals were rejected")

        if run.status not in {"PROPOSED", "APPROVED", "VALIDATION_FAILED", "VALIDATED"}:
            raise ValidationError(f"Agent run state {run.status} cannot be executed")

        run.status = "EXECUTING"
        action_records = self._action_records(run)
        if not action_records:
            raise ValidationError("Agent run has no executable proposed action")

        purchase_orders: list[PurchaseOrder] = []
        for index, (proposed, approval) in enumerate(action_records, start=1):
            purchase_orders.append(self._execute_action(run.id, proposed, approval, index))

        if all(order.status == "VALIDATED" for order in purchase_orders):
            run.status = "VALIDATED"
        elif any(order.status == "VALIDATION_FAILED" for order in purchase_orders):
            run.status = "VALIDATION_FAILED"
        return purchase_orders

    def execute_approval(self, approval_id: int) -> PurchaseOrder:
        approval = self.db.get(ApprovalRequest, approval_id)
        if not approval:
            raise NotFoundError("Approval request not found")
        if approval.status != "APPROVED":
            raise ValidationError("Approval must be approved before execution")
        action_json = approval.proposed_action_json or {}
        if action_json.get("purchase_order_id"):
            return self._purchase_order(int(action_json["purchase_order_id"]))
        run = self.repo.agent_run(approval.agent_run_id)
        if not run:
            raise NotFoundError("Agent run not found")
        proposed = ProposedAction.model_validate(action_json)
        purchase_order = self._execute_action(run.id, proposed, approval, 1)
        action_json["purchase_order_id"] = purchase_order.id
        action_json["executed_at"] = datetime.now(timezone.utc).isoformat()
        action_json["execution_status"] = purchase_order.status
        approval.proposed_action_json = dict(action_json)
        flag_modified(approval, "proposed_action_json")
        if not self.repo.pending_approvals_for_run(run.id) and all(
            row.proposed_action_json.get("purchase_order_id") for row in self.repo.approvals_for_run(run.id) if row.status == "APPROVED"
        ):
            run.status = "VALIDATED" if purchase_order.status == "VALIDATED" else run.status
        return purchase_order

    def _execute_action(self, agent_run_id: int, proposed: ProposedAction, approval: ApprovalRequest | None, action_index: int) -> PurchaseOrder:
        idempotency_key = f"approval-{approval.id}" if approval else f"agent-run-{agent_run_id}-action-{action_index}"
        existing = self.repo.purchase_order_by_idempotency(idempotency_key)
        if existing:
            if approval and not (approval.proposed_action_json or {}).get("purchase_order_id"):
                action_json = dict(approval.proposed_action_json or {})
                action_json["purchase_order_id"] = existing.id
                action_json["execution_status"] = existing.status
                approval.proposed_action_json = action_json
                flag_modified(approval, "proposed_action_json")
            return existing

        constraint_result = self.constraint_engine.evaluate(
            proposed.product_id,
            proposed.warehouse_id,
            proposed.supplier_id,
            proposed.quantity,
            proposed.expected_delivery_date,
        )
        if not constraint_result.valid:
            self.db.add(
                AgentEvent(
                    agent_run_id=agent_run_id,
                    event_type="EXECUTION_BLOCKED",
                    message="Current-state revalidation blocked purchase-order execution.",
                    metadata_json={"approval_id": approval.id if approval else None, **constraint_result.model_dump(mode="json")},
                )
            )
            raise ValidationError("Current-state revalidation failed")

        budget = self.repo.lock_current_budget(proposed.warehouse_id, PurchasingRepository.budget_period_for(proposed.expected_delivery_date))
        if not budget:
            raise ValidationError("Budget record is missing")
        total = money(Decimal(proposed.quantity) * Decimal(proposed.unit_price))
        if total > budget.available_budget:
            raise ValidationError("Budget changed after approval; execution stopped")

        purchase_order = PurchaseOrder(
            supplier_id=proposed.supplier_id,
            warehouse_id=proposed.warehouse_id,
            status="EXECUTED",
            expected_delivery_date=proposed.expected_delivery_date,
            total_amount=total,
            source_recommendation_id=proposed.recommendation_id,
            agent_run_id=agent_run_id,
            idempotency_key=idempotency_key,
        )
        purchase_order.items.append(
            PurchaseOrderItem(
                product_id=proposed.product_id,
                quantity=proposed.quantity,
                unit_price=proposed.unit_price,
                line_total=total,
            )
        )
        budget.committed_amount += total
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
        self.db.add(
            AgentEvent(
                agent_run_id=agent_run_id,
                event_type="PURCHASE_ORDER_EXECUTED",
                message=f"Created purchase order {purchase_order.id}",
                metadata_json={
                    "purchase_order_id": purchase_order.id,
                    "approval_id": approval.id if approval else None,
                    "supplier_id": proposed.supplier_id,
                    "supplier_name": proposed.supplier_name,
                    "product_id": proposed.product_id,
                    "product_sku": proposed.product_sku,
                    "product_name": proposed.product_name,
                    "supplier_status": supplier_result.status,
                },
            )
        )

        order_validation = self.validation_service.validate_purchase_order(agent_run_id, purchase_order, proposed)
        supplier_validation = self.validation_service.validate_supplier_outcome(agent_run_id, purchase_order, proposed)
        if order_validation.status == "PASSED" and supplier_validation.status == "PASSED":
            purchase_order.status = "VALIDATED"
        else:
            self.recovery_service.handle_validation_failure(agent_run_id, purchase_order, supplier_validation.errors_json)
        return purchase_order

    def _purchase_order(self, purchase_order_id: int) -> PurchaseOrder:
        purchase_order = self.db.get(PurchaseOrder, purchase_order_id)
        if not purchase_order:
            raise NotFoundError("Purchase order not found")
        return purchase_order

    def _action_records(self, run) -> list[tuple[ProposedAction, ApprovalRequest | None]]:
        approvals = self.repo.approved_approvals_for_run(run.id)
        if approvals:
            return [(ProposedAction.model_validate(approval.proposed_action_json), approval) for approval in approvals]
        raw_actions = run.evidence_snapshot.get("proposed_actions") or (
            [run.evidence_snapshot["proposed_action"]] if run.evidence_snapshot.get("proposed_action") else []
        )
        return [(ProposedAction.model_validate(raw_action), None) for raw_action in raw_actions]

