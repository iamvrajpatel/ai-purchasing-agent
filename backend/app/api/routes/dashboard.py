from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AgentEvent, AgentRun, ApprovalRequest, PurchaseOrder, PurchaseRecommendation, PurchasingBudget
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
    budgets = list(db.scalars(select(PurchasingBudget).order_by(PurchasingBudget.budget_period.desc(), PurchasingBudget.warehouse_id)))
    pending_rows = list(db.scalars(select(ApprovalRequest).where(ApprovalRequest.status == "PENDING")))
    exposure_by_warehouse: dict[int, dict] = {}
    for approval in pending_rows:
        action = approval.proposed_action_json or {}
        warehouse_id = action.get("warehouse_id")
        if warehouse_id is None:
            continue
        bucket = exposure_by_warehouse.setdefault(
            int(warehouse_id),
            {
                "warehouse_id": int(warehouse_id),
                "warehouse_name": action.get("warehouse_name"),
                "pending_total": "0.00",
                "pending_count": 0,
            },
        )
        bucket["pending_count"] += 1
        bucket["pending_total"] = str((Decimal(bucket["pending_total"]) + Decimal(str(action.get("total_amount", "0")))).quantize(Decimal("0.01")))
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
        budgets=[
            {
                "warehouse_id": budget.warehouse_id,
                "warehouse_name": budget.warehouse.name if budget.warehouse else None,
                "budget_period": budget.budget_period,
                "total_budget": str(budget.total_budget),
                "reserved_amount": str(budget.reserved_amount),
                "committed_amount": str(budget.committed_amount),
                "available_budget": str(budget.available_budget),
                "percent_used": float(((budget.reserved_amount + budget.committed_amount) / budget.total_budget) * 100) if budget.total_budget else 0,
                "status": "RISK" if budget.available_budget <= 0 else "LOW" if budget.total_budget and (budget.available_budget / budget.total_budget) < Decimal("0.15") else "OK",
            }
            for budget in budgets
        ],
        pending_approval_exposure=list(exposure_by_warehouse.values()),
    )

