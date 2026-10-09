from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Supplier, SupplierProduct


class SupplierRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_suppliers(self) -> list[Supplier]:
        return list(self.db.scalars(select(Supplier).order_by(Supplier.id)))

    def get_supplier(self, supplier_id: int) -> Supplier | None:
        return self.db.get(Supplier, supplier_id)

    def get_supplier_options(self, product_id: int) -> list[SupplierProduct]:
        return list(
            self.db.scalars(
                select(SupplierProduct)
                .join(Supplier)
                .where(SupplierProduct.product_id == product_id, SupplierProduct.active.is_(True), Supplier.status == "ACTIVE")
                .order_by(SupplierProduct.unit_price, SupplierProduct.lead_time_days)
            )
        )

    def get_supplier_conditions(self, supplier_id: int, product_id: int) -> SupplierProduct | None:
        return self.db.scalar(
            select(SupplierProduct).where(
                SupplierProduct.supplier_id == supplier_id,
                SupplierProduct.product_id == product_id,
                SupplierProduct.active.is_(True),
            )
        )

