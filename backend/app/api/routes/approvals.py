from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.repositories.purchasing_repository import PurchasingRepository
from app.schemas.purchase_order import ApprovalRead
from app.services.approval_service import ApprovalService
from app.services.purchase_order_service import PurchaseOrderService

router = APIRouter(prefix="/approvals", tags=["approvals"])


def buyer_identity(x_buyer_user: str | None = Header(default=None)) -> str:
    return x_buyer_user or get_settings().mock_buyer_user


@router.get("", response_model=list[ApprovalRead])
def approvals(db: Session = Depends(get_db)):
    return PurchasingRepository(db).approvals()


@router.post("/{approval_id}/approve", response_model=ApprovalRead)
def approve(approval_id: int, buyer: str = Depends(buyer_identity), db: Session = Depends(get_db)):
    approval = ApprovalService(db).approve(approval_id, buyer)
    db.commit()
    db.refresh(approval)
    return approval


@router.post("/{approval_id}/reject", response_model=ApprovalRead)
def reject(approval_id: int, buyer: str = Depends(buyer_identity), db: Session = Depends(get_db)):
    approval = ApprovalService(db).reject(approval_id, buyer)
    db.commit()
    db.refresh(approval)
    return approval


@router.post("/{approval_id}/execute")
def execute_approval(approval_id: int, db: Session = Depends(get_db)):
    purchase_order = PurchaseOrderService(db).execute_approval(approval_id)
    db.commit()
    return {"approval_id": approval_id, "purchase_order_id": purchase_order.id, "status": purchase_order.status}

