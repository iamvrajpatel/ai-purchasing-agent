from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.purchasing_repository import PurchasingRepository
from app.schemas.product import WarehouseRead

router = APIRouter(prefix="/warehouses", tags=["warehouses"])


@router.get("", response_model=list[WarehouseRead])
def list_warehouses(db: Session = Depends(get_db)):
    return PurchasingRepository(db).list_warehouses()

