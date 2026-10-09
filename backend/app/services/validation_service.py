from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import AgentValidation, PurchaseOrder
from app.schemas.purchasing import ProposedAction, PurchasingDecision


class ValidationService:
    def __init__(self, db: Session):
        self.db = db

    def validate_decision(self, agent_run_id: int, decision: PurchasingDecision, proposed_action: ProposedAction | None) -> AgentValidation:
        errors: list[dict] = []
        checks = {
            "decision": decision.decision,
            "has_reasoning": bool(decision.reasoning),
            "has_evidence": bool(decision.evidence),
            "constraint_valid": decision.constraint_result.valid if decision.constraint_result else None,
        }
        if decision.decision in {"ACCEPT", "MODIFY"} and not proposed_action:
            errors.append({"code": "MISSING_PROPOSED_ACTION", "message": "Executable decision has no proposed action"})
        if proposed_action and proposed_action.quantity <= 0:
            errors.append({"code": "INVALID_QUANTITY", "message": "Proposed quantity must be positive"})
        if decision.constraint_result and not decision.constraint_result.valid:
            errors.append({"code": "CONSTRAINT_FAILURE", "message": "Mandatory constraints did not pass"})

        validation = AgentValidation(
            agent_run_id=agent_run_id,
            purchase_order_id=None,
            validation_type="PRE_EXECUTION_DECISION",
            status="FAILED" if errors else "PASSED",
            checks_json=checks,
            errors_json=errors or None,
        )
        self.db.add(validation)
        return validation

    def validate_purchase_order(self, agent_run_id: int, purchase_order: PurchaseOrder, proposed_action: ProposedAction) -> AgentValidation:
        item = purchase_order.items[0] if purchase_order.items else None
        errors: list[dict] = []
        checks = {
            "supplier_id": purchase_order.supplier_id,
            "warehouse_id": purchase_order.warehouse_id,
            "quantity": item.quantity if item else None,
            "unit_price": str(item.unit_price) if item else None,
            "total_amount": str(purchase_order.total_amount),
            "status": purchase_order.status,
        }
        if purchase_order.supplier_id != proposed_action.supplier_id:
            errors.append({"code": "SUPPLIER_MISMATCH", "message": "Persisted supplier differs from proposal"})
        if purchase_order.warehouse_id != proposed_action.warehouse_id:
            errors.append({"code": "WAREHOUSE_MISMATCH", "message": "Persisted warehouse differs from proposal"})
        if not item or item.product_id != proposed_action.product_id or item.quantity != proposed_action.quantity:
            errors.append({"code": "ITEM_MISMATCH", "message": "Persisted item differs from proposal"})
        if Decimal(purchase_order.total_amount) != Decimal(proposed_action.total_amount):
            errors.append({"code": "TOTAL_MISMATCH", "message": "Persisted total differs from proposal"})

        validation = AgentValidation(
            agent_run_id=agent_run_id,
            purchase_order_id=purchase_order.id,
            validation_type="POST_EXECUTION_ORDER",
            status="FAILED" if errors else "PASSED",
            checks_json=checks,
            errors_json=errors or None,
        )
        self.db.add(validation)
        return validation

    def validate_supplier_outcome(self, agent_run_id: int, purchase_order: PurchaseOrder, proposed_action: ProposedAction) -> AgentValidation:
        response = purchase_order.supplier_response_json or {}
        confirmed_quantity = response.get("confirmed_quantity")
        status = response.get("status") or purchase_order.supplier_confirmation_status
        errors: list[dict] = []
        checks = {
            "supplier_status": status,
            "requested_quantity": proposed_action.quantity,
            "confirmed_quantity": confirmed_quantity,
        }
        if status != "CONFIRMED":
            errors.append({"code": "SUPPLIER_NOT_CONFIRMED", "message": f"Supplier returned {status}"})
        if confirmed_quantity != proposed_action.quantity:
            errors.append({"code": "PARTIAL_SUPPLIER_CONFIRMATION", "message": "Supplier confirmed fewer units than requested"})
        validation = AgentValidation(
            agent_run_id=agent_run_id,
            purchase_order_id=purchase_order.id,
            validation_type="SUPPLIER_OUTCOME",
            status="FAILED" if errors else "PASSED",
            checks_json=checks,
            errors_json=errors or None,
        )
        self.db.add(validation)
        return validation

