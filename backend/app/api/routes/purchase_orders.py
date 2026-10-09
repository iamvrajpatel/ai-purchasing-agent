from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models import AgentValidation, PurchaseOrder
from app.schemas.purchase_order import PurchaseOrderDetail, PurchaseOrderRead
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


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
    return detail

