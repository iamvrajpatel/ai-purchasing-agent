from sqlalchemy.orm import Session

from app.repositories.inventory_repository import InventoryRepository
from app.services.inventory_service import InventoryService
from app.utils.exceptions import NotFoundError


class InventoryTools:
    def __init__(self, db: Session):
        self.db = db
        self.repo = InventoryRepository(db)
        self.service = InventoryService(db)

    def get_inventory(self, product_id: int, warehouse_id: int) -> dict:
        inventory = self.repo.get_inventory(product_id, warehouse_id)
        if not inventory:
            raise NotFoundError("Inventory not found")
        return {
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "on_hand_quantity": inventory.on_hand_quantity,
            "reserved_quantity": inventory.reserved_quantity,
            "damaged_quantity": inventory.damaged_quantity,
            "sellable_quantity": inventory.sellable_quantity,
        }

    def get_storage_capacity(self, warehouse_id: int) -> dict:
        return self.service.storage_capacity_snapshot(warehouse_id)

    def calculate_purchase_requirement(self, product_id: int, warehouse_id: int, planning_horizon_days: int) -> dict:
        return self.service.calculate_purchase_requirement(product_id, warehouse_id, planning_horizon_days).model_dump(mode="json")

