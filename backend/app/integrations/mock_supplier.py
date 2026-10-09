from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.repositories.supplier_repository import SupplierRepository


@dataclass(frozen=True)
class SupplierSubmissionResult:
    status: str
    confirmed_quantity: int
    external_reference: str
    response: dict


class MockSupplierClient:
    """Deterministic supplier adapter used by the local assignment demo."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = SupplierRepository(db)

    def check_availability(self, supplier_id: int, product_id: int) -> dict:
        supplier_product = self.repo.get_supplier_conditions(supplier_id, product_id)
        if not supplier_product:
            return {"status": "UNKNOWN", "available_quantity": None}
        return {"status": "CONFIRMED", "available_quantity": supplier_product.available_quantity}

    def submit_purchase_order(self, supplier_id: int, product_id: int, quantity: int, idempotency_key: str) -> SupplierSubmissionResult:
        supplier_product = self.repo.get_supplier_conditions(supplier_id, product_id)
        if not supplier_product:
            return SupplierSubmissionResult(
                status="UNKNOWN",
                confirmed_quantity=0,
                external_reference=f"mock-{uuid4()}",
                response={"reason": "Supplier product is unavailable", "idempotency_key": idempotency_key},
            )

        confirmed = min(quantity, supplier_product.available_quantity)
        if confirmed == quantity:
            status = "CONFIRMED"
        elif confirmed > 0:
            status = "PARTIALLY_CONFIRMED"
        else:
            status = "REJECTED"

        return SupplierSubmissionResult(
            status=status,
            confirmed_quantity=confirmed,
            external_reference=f"mock-{supplier_id}-{uuid4()}",
            response={
                "requested_quantity": quantity,
                "confirmed_quantity": confirmed,
                "status": status,
                "idempotency_key": idempotency_key,
            },
        )

    def retrieve_confirmation(self, external_reference: str) -> dict:
        return {"external_reference": external_reference, "status": "PENDING" if not external_reference else "CONFIRMED"}

