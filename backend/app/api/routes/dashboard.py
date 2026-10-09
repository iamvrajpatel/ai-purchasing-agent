from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AgentEvent, AgentRun, ApprovalRequest, PurchaseOrder, PurchaseRecommendation
from app.schemas.common import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)):
    total_recommendations = db.scalar(select(func.count(PurchaseRecommendation.id))) or 0
    pending_recommendations = db.scalar(select(func.count(PurchaseRecommendation.id)).where(PurchaseRecommendation.status == "PENDING")) or 0
    completed_agent_decisions = db.scalar(select(func.count(AgentRun.id)).where(AgentRun.decision.is_not(None))) or 0
    pending_approvals = db.scalar(select(func.count(ApprovalRequest.id)).where(ApprovalRequest.status == "PENDING")) or 0
    escalations = db.scalar(select(func.count(AgentEvent.id)).where(AgentEvent.event_type == "ESCALATED")) or 0
    recent_pos = list(db.scalars(select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).limit(5)))
    recent_events = list(db.scalars(select(AgentEvent).order_by(AgentEvent.created_at.desc()).limit(8)))
    return DashboardSummary(
        total_recommendations=total_recommendations,
        pending_recommendations=pending_recommendations,
        completed_agent_decisions=completed_agent_decisions,
        pending_approvals=pending_approvals,
        escalations=escalations,
        recent_purchase_orders=[
            {"id": po.id, "status": po.status, "total_amount": str(po.total_amount), "supplier_status": po.supplier_confirmation_status}
            for po in recent_pos
        ],
        recent_agent_activity=[
            {"agent_run_id": event.agent_run_id, "event_type": event.event_type, "message": event.message, "created_at": event.created_at.isoformat()}
            for event in recent_events
        ],
    )

