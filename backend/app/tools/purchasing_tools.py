from datetime import date

from sqlalchemy.orm import Session

from app.repositories.purchasing_repository import PurchasingRepository
from app.services.constraint_engine import ConstraintEngine
from app.utils.exceptions import NotFoundError


class PurchasingTools:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PurchasingRepository(db)
        self.constraints = ConstraintEngine(db)

    def get_product_details(self, product_id: int) -> dict:
        product = self.repo.get_product(product_id)
        if not product:
            raise NotFoundError("Product not found")
        return {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "category": product.category,
            "unit_volume": str(product.unit_volume),
            "safety_stock": product.safety_stock,
        }

    def get_open_purchase_orders(self, product_id: int, warehouse_id: int) -> dict:
        orders = self.repo.open_purchase_orders(product_id, warehouse_id)
        return {
            "purchase_orders": [
                {
                    "id": order.id,
                    "status": order.status,
                    "expected_delivery_date": order.expected_delivery_date.isoformat(),
                    "items": [{"product_id": item.product_id, "quantity": item.quantity} for item in order.items],
                }
                for order in orders
            ]
        }

    def get_available_budget(self, warehouse_id: int) -> dict:
        budget = self.repo.current_budget(warehouse_id, PurchasingRepository.budget_period_for(date.today()))
        if not budget:
            raise NotFoundError("Budget not found")
        return {
            "warehouse_id": warehouse_id,
            "budget_period": budget.budget_period,
            "total_budget": str(budget.total_budget),
            "reserved_amount": str(budget.reserved_amount),
            "committed_amount": str(budget.committed_amount),
            "available_budget": str(budget.available_budget),
        }

    def evaluate_purchase_constraints(self, product_id: int, warehouse_id: int, supplier_id: int, quantity: int) -> dict:
        return self.constraints.evaluate(product_id, warehouse_id, supplier_id, quantity).model_dump(mode="json")

