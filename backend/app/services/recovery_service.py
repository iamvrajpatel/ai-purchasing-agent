from sqlalchemy.orm import Session

from app.models import AgentEvent, PurchaseOrder


class RecoveryService:
    def __init__(self, db: Session):
        self.db = db

    def handle_validation_failure(self, agent_run_id: int, purchase_order: PurchaseOrder, errors: list | None) -> None:
        purchase_order.status = "VALIDATION_FAILED"
        self.db.add(
            AgentEvent(
                agent_run_id=agent_run_id,
                event_type="ESCALATED",
                message="Purchase order validation failed; human review is required before retry.",
                metadata_json={"purchase_order_id": purchase_order.id, "errors": errors or []},
            )
        )

