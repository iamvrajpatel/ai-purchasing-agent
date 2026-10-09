from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.purchasing_agent import PurchasingAgent
from app.core.database import get_db
from app.models import AgentRun
from app.repositories.purchasing_repository import PurchasingRepository
from app.schemas.agent import AgentAnalyzeRequest, AgentEventRead, AgentRunDetail, AgentRunRead, AgentValidationRead
from app.schemas.purchasing import PurchasingDecision
from app.services.purchase_order_service import PurchaseOrderService
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/analyze", response_model=AgentRunRead)
async def analyze(payload: AgentAnalyzeRequest, db: Session = Depends(get_db)):
    run = await PurchasingAgent(db).analyze(payload.recommendation_id)
    db.commit()
    db.refresh(run)
    return run


@router.get("/runs", response_model=list[AgentRunRead])
def list_runs(db: Session = Depends(get_db)):
    return list(db.scalars(select(AgentRun).order_by(AgentRun.started_at.desc())))


@router.get("/runs/{run_id}", response_model=AgentRunDetail)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = PurchasingRepository(db).agent_run(run_id)
    if not run:
        raise NotFoundError("Agent run not found")
    detail = AgentRunDetail.model_validate(run)
    if run.evidence_snapshot and run.evidence_snapshot.get("server_validated_decision"):
        detail.structured_decision = PurchasingDecision.model_validate(run.evidence_snapshot["server_validated_decision"])
    return detail


@router.get("/runs/{run_id}/events", response_model=list[AgentEventRead])
def get_run_events(run_id: int, db: Session = Depends(get_db)):
    run = PurchasingRepository(db).agent_run(run_id)
    if not run:
        raise NotFoundError("Agent run not found")
    return sorted(run.events, key=lambda event: event.created_at)


@router.get("/runs/{run_id}/validations", response_model=list[AgentValidationRead])
def get_run_validations(run_id: int, db: Session = Depends(get_db)):
    run = PurchasingRepository(db).agent_run(run_id)
    if not run:
        raise NotFoundError("Agent run not found")
    return run.validations


@router.post("/runs/{run_id}/execute")
def execute_run(run_id: int, db: Session = Depends(get_db)):
    purchase_order = PurchaseOrderService(db).execute_agent_run(run_id)
    db.commit()
    return {"purchase_order_id": purchase_order.id, "status": purchase_order.status}

