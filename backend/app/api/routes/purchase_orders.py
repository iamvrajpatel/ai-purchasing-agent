from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.models import AgentValidation, PurchaseOrder
from app.schemas.purchase_order import PurchaseOrderDetail, PurchaseOrderRead
from app.schemas.recovery import RecoveryCaseDetail
from app.services.purchase_order_recovery_service import PurchaseOrderRecoveryService
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])
recovery_router = APIRouter(prefix="/recovery-cases", tags=["recovery-cases"])


def buyer_identity(x_buyer_user: str | None = Header(default=None)) -> str:
    return x_buyer_user or get_settings().mock_buyer_user


@router.get("", response_model=list[PurchaseOrderRead])
def list_purchase_orders(db: Session = Depends(get_db)):
    return list(db.scalars(select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc())))


@router.get("/{purchase_order_id}", response_model=PurchaseOrderDetail)
def get_purchase_order(purchase_order_id: int, db: Session = Depends(get_db)):
    row = db.scalar(select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(PurchaseOrder.id == purchase_order_id))
    if not row:
        raise NotFoundError("Purchase order not found")
    detail = PurchaseOrderDetail.model_validate(row)
    validations = list(
        db.scalars(select(AgentValidation).where(AgentValidation.purchase_order_id == purchase_order_id).order_by(AgentValidation.created_at))
    )
    detail.validations = [
        {
            "validation_type": validation.validation_type,
            "status": validation.status,
            "checks": validation.checks_json,
            "errors": validation.errors_json,
        }
        for validation in validations
    ]
    recovery_case = PurchaseOrderRecoveryService(db).get_for_purchase_order(purchase_order_id)
    if recovery_case:
        detail.recovery_case = PurchaseOrderRecoveryService(db).to_detail(recovery_case)
    return detail


@router.get("/{purchase_order_id}/recovery", response_model=RecoveryCaseDetail)
def get_recovery_case(purchase_order_id: int, db: Session = Depends(get_db)):
    service = PurchaseOrderRecoveryService(db)
    recovery_case = service.get_for_purchase_order(purchase_order_id)
    if not recovery_case:
        raise NotFoundError("Recovery case not found")
    return service.to_detail(recovery_case)


@router.post("/{purchase_order_id}/recovery/analyze", response_model=RecoveryCaseDetail)
def analyze_recovery_case(purchase_order_id: int, db: Session = Depends(get_db)):
    service = PurchaseOrderRecoveryService(db)
    recovery_case = service.analyze_purchase_order(purchase_order_id)
    db.commit()
    db.refresh(recovery_case)
    return service.to_detail(recovery_case)


@recovery_router.post("/{recovery_case_id}/approve", response_model=RecoveryCaseDetail)
def approve_recovery_case(recovery_case_id: int, buyer: str = Depends(buyer_identity), db: Session = Depends(get_db)):
    service = PurchaseOrderRecoveryService(db)
    recovery_case = service.approve(recovery_case_id, buyer)
    db.commit()
    db.refresh(recovery_case)
    return service.to_detail(recovery_case)


@recovery_router.post("/{recovery_case_id}/execute")
def execute_recovery_case(recovery_case_id: int, db: Session = Depends(get_db)):
    service = PurchaseOrderRecoveryService(db)
    purchase_order = service.execute(recovery_case_id)
    db.commit()
    return {"purchase_order_id": purchase_order.id, "status": purchase_order.status}

