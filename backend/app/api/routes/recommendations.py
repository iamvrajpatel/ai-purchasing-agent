from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import PurchaseRecommendation
from app.repositories.purchasing_repository import PurchasingRepository
from app.schemas.purchasing import RecommendationCreate, RecommendationRead
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _read(row: PurchaseRecommendation) -> RecommendationRead:
    return RecommendationRead(
        id=row.id,
        product_id=row.product_id,
        warehouse_id=row.warehouse_id,
        recommended_quantity=row.recommended_quantity,
        recommendation_source=row.recommendation_source,
        status=row.status,
        created_at=row.created_at,
        product_sku=row.product.sku if row.product else None,
        product_name=row.product.name if row.product else None,
        warehouse_name=row.warehouse.name if row.warehouse else None,
    )


@router.get("", response_model=list[RecommendationRead])
def list_recommendations(db: Session = Depends(get_db)):
    return [_read(row) for row in PurchasingRepository(db).list_recommendations()]


@router.get("/{recommendation_id}", response_model=RecommendationRead)
def get_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    row = PurchasingRepository(db).get_recommendation(recommendation_id)
    if not row:
        raise NotFoundError("Recommendation not found")
    return _read(row)


@router.post("", response_model=RecommendationRead, status_code=201)
def create_recommendation(payload: RecommendationCreate, db: Session = Depends(get_db)):
    row = PurchaseRecommendation(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    row = PurchasingRepository(db).get_recommendation(row.id)
    return _read(row)

