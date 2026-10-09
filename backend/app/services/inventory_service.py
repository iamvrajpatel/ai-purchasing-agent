from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.repositories.inventory_repository import InventoryRepository
from app.repositories.purchasing_repository import PurchasingRepository
from app.schemas.purchasing import PurchaseRequirement
from app.utils.exceptions import NotFoundError, ValidationError


class InventoryService:
    def __init__(self, db: Session):
        self.db = db
        self.inventory_repo = InventoryRepository(db)
        self.purchasing_repo = PurchasingRepository(db)

    def sellable_inventory(self, product_id: int, warehouse_id: int) -> int:
        inventory = self.inventory_repo.get_inventory(product_id, warehouse_id)
        if not inventory:
            raise NotFoundError("Inventory record not found")
        return inventory.sellable_quantity

    def calculate_purchase_requirement(self, product_id: int, warehouse_id: int, planning_horizon_days: int) -> PurchaseRequirement:
        if planning_horizon_days <= 0:
            raise ValidationError("Planning horizon must be positive")
        product = self.purchasing_repo.get_product(product_id)
        if not product:
            raise NotFoundError("Product not found")
        inventory = self.inventory_repo.get_inventory(product_id, warehouse_id)
        if not inventory:
            raise NotFoundError("Inventory record not found")

        today = date.today()
        end_date = today + timedelta(days=planning_horizon_days - 1)
        forecasts = self.inventory_repo.get_forecasts(product_id, warehouse_id, today, end_date)
        forecast_by_date = {forecast.forecast_date: forecast.expected_quantity for forecast in forecasts}
        receipts_by_date = self.inventory_repo.get_confirmed_receipts_by_date(product_id, warehouse_id, end_date)

        if not forecasts:
            raise ValidationError("Demand forecast is unavailable")

        projected = inventory.sellable_quantity
        min_projected = projected
        stockout_date: date | None = None
        required_by_date: date | None = None
        projection: list[dict] = []

        for offset in range(planning_horizon_days):
            current_date = today + timedelta(days=offset)
            receipts = receipts_by_date.get(current_date, 0)
            demand = forecast_by_date.get(current_date, 0)
            projected = projected + receipts - demand
            projection.append(
                {
                    "date": current_date.isoformat(),
                    "receipts": receipts,
                    "forecast_demand": demand,
                    "projected_stock": projected,
                }
            )
            if projected < product.safety_stock and stockout_date is None:
                stockout_date = current_date
                required_by_date = current_date
            min_projected = min(min_projected, projected)

        forecast_demand = sum(forecast.expected_quantity for forecast in forecasts)
        timely_cutoff = stockout_date or end_date
        timely_incoming = sum(qty for day, qty in receipts_by_date.items() if day <= timely_cutoff)
        required_quantity = max(0, forecast_demand + product.safety_stock - inventory.sellable_quantity - timely_incoming)

        return PurchaseRequirement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            planning_horizon_days=planning_horizon_days,
            sellable_inventory=inventory.sellable_quantity,
            forecast_demand=forecast_demand,
            timely_incoming_quantity=timely_incoming,
            safety_stock=product.safety_stock,
            required_quantity=required_quantity,
            stockout_date=stockout_date,
            required_by_date=required_by_date,
            projection=projection,
        )

    def storage_capacity_snapshot(self, warehouse_id: int) -> dict:
        warehouse = self.inventory_repo.warehouse(warehouse_id)
        if not warehouse:
            raise NotFoundError("Warehouse not found")
        occupied_volume = self.inventory_repo.current_warehouse_occupied_volume(warehouse_id)
        available_volume = max(0, warehouse.total_storage_capacity - occupied_volume)
        occupancy_units = self.inventory_repo.current_warehouse_occupancy(warehouse_id)
        return {
            "warehouse_id": warehouse_id,
            "total_storage_capacity": str(warehouse.total_storage_capacity),
            "current_occupied_volume": str(occupied_volume),
            "available_storage_volume": str(available_volume),
            # Backwards-compatible aliases for existing UI/tool traces.
            "current_occupancy_units": occupancy_units,
            "available_storage_units": str(available_volume),
        }

