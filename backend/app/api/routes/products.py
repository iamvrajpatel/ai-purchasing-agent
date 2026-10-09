from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.purchasing_repository import PurchasingRepository
from app.schemas.product import ProductRead
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
def list_products(db: Session = Depends(get_db)):
    return PurchasingRepository(db).list_products()


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = PurchasingRepository(db).get_product(product_id)
    if not product:
        raise NotFoundError("Product not found")
    return product

