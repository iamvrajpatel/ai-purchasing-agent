from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ApprovalRequest
from app.repositories.purchasing_repository import PurchasingRepository
from app.schemas.purchasing import ProposedAction
from app.utils.exceptions import AuthorizationError, NotFoundError, ValidationError


class ApprovalService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.repo = PurchasingRepository(db)

    def ensure_approval_path(self, agent_run_id: int, proposed_action: ProposedAction, requires_human: bool) -> ApprovalRequest | None:
        existing = self.repo.approvals_for_run(agent_run_id)
        if existing:
            return existing[0]
        if not requires_human:
            return None
        approval = ApprovalRequest(
            agent_run_id=agent_run_id,
            proposed_action_json=proposed_action.model_dump(mode="json"),
            status="PENDING",
        )
        self.db.add(approval)
        return approval

    def ensure_approval_paths(self, agent_run_id: int, proposed_actions: list[ProposedAction], requires_human: bool) -> list[ApprovalRequest]:
        existing = self.repo.approvals_for_run(agent_run_id)
        if existing:
            return existing
        if not requires_human:
            return []
        approvals: list[ApprovalRequest] = []
        for action in proposed_actions:
            approval = ApprovalRequest(
                agent_run_id=agent_run_id,
                proposed_action_json=action.model_dump(mode="json"),
                status="PENDING",
            )
            self.db.add(approval)
            approvals.append(approval)
        return approvals

    def approve(self, approval_id: int, buyer_identity: str) -> ApprovalRequest:
        self._assert_buyer(buyer_identity)
        approval = self.db.get(ApprovalRequest, approval_id)
        if not approval:
            raise NotFoundError("Approval request not found")
        if approval.status != "PENDING":
            raise ValidationError("Approval request is not pending")
        approval.status = "APPROVED"
        approval.approved_by = buyer_identity
        approval.approved_at = datetime.now(timezone.utc)
        if not any(row.status == "PENDING" for row in self.repo.approvals_for_run(approval.agent_run_id) if row.id != approval.id):
            approval.agent_run.status = "APPROVED"
        else:
            approval.agent_run.status = "AWAITING_APPROVAL"
        return approval

    def reject(self, approval_id: int, buyer_identity: str) -> ApprovalRequest:
        self._assert_buyer(buyer_identity)
        approval = self.db.get(ApprovalRequest, approval_id)
        if not approval:
            raise NotFoundError("Approval request not found")
        if approval.status != "PENDING":
            raise ValidationError("Approval request is not pending")
        approval.status = "REJECTED"
        approval.approved_by = buyer_identity
        approval.approved_at = datetime.now(timezone.utc)
        approval.agent_run.status = "REJECTED"
        return approval

    def _assert_buyer(self, buyer_identity: str) -> None:
        if buyer_identity != self.settings.mock_buyer_user:
            raise AuthorizationError("Only the configured buyer can approve or reject proposals")

