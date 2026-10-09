from decimal import Decimal

from sqlalchemy.orm import Session

from app.integrations.mock_supplier import MockSupplierClient
from app.models import AgentEvent, PurchaseOrder, PurchaseOrderItem
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
        run = self.repo.agent_run(agent_run_id)
        if not run:
            raise NotFoundError("Agent run not found")
        if not run.evidence_snapshot or "proposed_action" not in run.evidence_snapshot:
            raise ValidationError("Agent run has no executable proposed action")
        proposed = ProposedAction.model_validate(run.evidence_snapshot["proposed_action"])
        idempotency_key = f"agent-run-{agent_run_id}-recommendation-{proposed.recommendation_id}"
        existing = self.repo.purchase_order_by_idempotency(idempotency_key)
        if existing:
            return existing

        approval = self.repo.pending_approval_for_run(agent_run_id)
        if approval:
            raise ValidationError("Proposal is awaiting approval")

        if run.status not in {"PROPOSED", "APPROVED", "VALIDATION_FAILED"}:
            raise ValidationError(f"Agent run state {run.status} cannot be executed")

        run.status = "EXECUTING"
        constraint_result = self.constraint_engine.evaluate(
            proposed.product_id,
            proposed.warehouse_id,
            proposed.supplier_id,
            proposed.quantity,
            proposed.expected_delivery_date,
        )
        if not constraint_result.valid:
            run.status = "FAILED"
            self.db.add(
                AgentEvent(
                    agent_run_id=agent_run_id,
                    event_type="EXECUTION_BLOCKED",
                    message="Current-state revalidation blocked purchase-order execution.",
                    metadata_json=constraint_result.model_dump(mode="json"),
                )
            )
            raise ValidationError("Current-state revalidation failed")

        budget = self.repo.lock_current_budget(proposed.warehouse_id, PurchasingRepository.budget_period_for(proposed.expected_delivery_date))
        if not budget:
            raise ValidationError("Budget record is missing")
        total = money(Decimal(proposed.quantity) * Decimal(proposed.unit_price))
        if total > budget.available_budget:
            run.status = "FAILED"
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
                metadata_json={"purchase_order_id": purchase_order.id, "supplier_status": supplier_result.status},
            )
        )

        order_validation = self.validation_service.validate_purchase_order(agent_run_id, purchase_order, proposed)
        supplier_validation = self.validation_service.validate_supplier_outcome(agent_run_id, purchase_order, proposed)
        if order_validation.status == "PASSED" and supplier_validation.status == "PASSED":
            purchase_order.status = "VALIDATED"
            run.status = "VALIDATED"
        else:
            run.status = "VALIDATION_FAILED"
            self.recovery_service.handle_validation_failure(agent_run_id, purchase_order, supplier_validation.errors_json)
        return purchase_order

