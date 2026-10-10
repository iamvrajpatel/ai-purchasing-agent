from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models import PurchaseOrder
from app.services.inventory_service import InventoryService
from app.services.supplier_service import SupplierService


class RecoveryTools:
    def __init__(self, db: Session):
        self.db = db
        self.inventory_service = InventoryService(db)
        self.supplier_service = SupplierService(db)
        self.settings = get_settings()

    def get_purchase_order_details(self, purchase_order_id: int) -> dict:
        purchase_order = self._purchase_order(purchase_order_id)
        item = purchase_order.items[0] if purchase_order.items else None
        return {
            "id": purchase_order.id,
            "supplier_id": purchase_order.supplier_id,
            "warehouse_id": purchase_order.warehouse_id,
            "status": purchase_order.status,
            "supplier_confirmation_status": purchase_order.supplier_confirmation_status,
            "supplier_response": purchase_order.supplier_response_json,
            "item": {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
                "line_total": str(item.line_total),
            }
            if item
            else None,
        }

    def get_supplier_confirmation_outcome(self, purchase_order_id: int) -> dict:
        purchase_order = self._purchase_order(purchase_order_id)
        response = purchase_order.supplier_response_json or {}
        item = purchase_order.items[0] if purchase_order.items else None
        requested = response.get("requested_quantity") or (item.quantity if item else 0)
        confirmed = response.get("confirmed_quantity") or 0
        return {
            "status": response.get("status") or purchase_order.supplier_confirmation_status,
            "requested_quantity": requested,
            "confirmed_quantity": confirmed,
            "shortfall_quantity": max(0, requested - confirmed),
        }

    def calculate_remaining_shortfall(self, purchase_order_id: int) -> dict:
        return self.get_supplier_confirmation_outcome(purchase_order_id)

    def list_alternate_suppliers(self, purchase_order_id: int, exclude_original_supplier: bool = True) -> dict:
        purchase_order = self._purchase_order(purchase_order_id)
        item = purchase_order.items[0] if purchase_order.items else None
        if not item:
            return {"suppliers": []}
        suppliers = self.supplier_service.list_options(item.product_id)
        if exclude_original_supplier:
            suppliers = [supplier for supplier in suppliers if supplier.supplier_id != purchase_order.supplier_id]
        return {"suppliers": [supplier.model_dump(mode="json") for supplier in suppliers]}

    def calculate_current_requirement_after_confirmation(self, purchase_order_id: int) -> dict:
        purchase_order = self._purchase_order(purchase_order_id)
        item = purchase_order.items[0] if purchase_order.items else None
        if not item:
            return {"error": "Purchase order has no item"}
        outcome = self.get_supplier_confirmation_outcome(purchase_order_id)
        requirement = self.inventory_service.calculate_purchase_requirement(
            item.product_id,
            purchase_order.warehouse_id,
            self.settings.planning_horizon_days,
        )
        return {
            **requirement.model_dump(mode="json"),
            "confirmed_quantity": outcome["confirmed_quantity"],
            "remaining_requirement_after_confirmed": max(0, requirement.required_quantity - outcome["confirmed_quantity"]),
        }

    def _purchase_order(self, purchase_order_id: int) -> PurchaseOrder:
        purchase_order = self.db.scalar(
            select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(PurchaseOrder.id == purchase_order_id)
        )
        if not purchase_order:
            raise ValueError("Purchase order not found")
        return purchase_order
