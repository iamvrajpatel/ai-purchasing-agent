from sqlalchemy.orm import Session

from app.models import AgentEvent, PurchaseOrder
from app.services.purchase_order_recovery_service import PurchaseOrderRecoveryService


class RecoveryService:
    def __init__(self, db: Session):
        self.db = db

    def handle_validation_failure(self, agent_run_id: int, purchase_order: PurchaseOrder, errors: list | None) -> None:
        purchase_order.status = "VALIDATION_FAILED"
        recovery_case_id = None
        if self._has_partial_supplier_confirmation(errors):
            recovery_case = PurchaseOrderRecoveryService(self.db).analyze_purchase_order(purchase_order.id, agent_run_id)
            recovery_case_id = recovery_case.id
        self.db.add(
            AgentEvent(
                agent_run_id=agent_run_id,
                event_type="ESCALATED",
                message="Purchase order validation failed; recovery analysis is required before retry.",
                metadata_json={"purchase_order_id": purchase_order.id, "recovery_case_id": recovery_case_id, "errors": errors or []},
            )
        )

    @staticmethod
    def _has_partial_supplier_confirmation(errors: list | None) -> bool:
        return any(error.get("code") == "PARTIAL_SUPPLIER_CONFIRMATION" for error in errors or [])

