from sqlalchemy.orm import Session

from app.repositories.supplier_repository import SupplierRepository
from app.schemas.purchasing import SupplierCondition
from app.utils.exceptions import NotFoundError


class SupplierService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SupplierRepository(db)

    def list_options(self, product_id: int) -> list[SupplierCondition]:
        return [self._to_condition(row) for row in self.repo.get_supplier_options(product_id)]

    def conditions(self, supplier_id: int, product_id: int) -> SupplierCondition:
        row = self.repo.get_supplier_conditions(supplier_id, product_id)
        if not row:
            raise NotFoundError("Supplier conditions not found")
        return self._to_condition(row)

    @staticmethod
    def _to_condition(row) -> SupplierCondition:
        return SupplierCondition(
            supplier_id=row.supplier_id,
            supplier_name=row.supplier.name,
            product_id=row.product_id,
            unit_price=row.unit_price,
            minimum_order_quantity=row.minimum_order_quantity,
            order_multiple=row.order_multiple,
            lead_time_days=row.lead_time_days,
            available_quantity=row.available_quantity,
            active=row.active,
        )

