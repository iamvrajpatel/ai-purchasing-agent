from sqlalchemy.orm import Session

from app.integrations.mock_supplier import MockSupplierClient
from app.services.supplier_service import SupplierService


class SupplierTools:
    def __init__(self, db: Session):
        self.service = SupplierService(db)
        self.client = MockSupplierClient(db)

    def get_supplier_options(self, product_id: int) -> dict:
        return {"suppliers": [row.model_dump(mode="json") for row in self.service.list_options(product_id)]}

    def get_supplier_conditions(self, supplier_id: int, product_id: int) -> dict:
        return self.service.conditions(supplier_id, product_id).model_dump(mode="json")

    def check_supplier_availability(self, supplier_id: int, product_id: int) -> dict:
        return self.client.check_availability(supplier_id, product_id)

