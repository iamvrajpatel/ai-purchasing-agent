from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.supplier_repository import SupplierRepository
from app.schemas.product import SupplierRead
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierRead])
def list_suppliers(db: Session = Depends(get_db)):
    return SupplierRepository(db).list_suppliers()


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: int, db: Session = Depends(get_db)):
    supplier = SupplierRepository(db).get_supplier(supplier_id)
    if not supplier:
        raise NotFoundError("Supplier not found")
    return supplier

