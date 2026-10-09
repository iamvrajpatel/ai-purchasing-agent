from datetime import date

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DemandForecast, Inventory, Product, PurchaseOrder, PurchaseOrderItem, Warehouse


class InventoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_inventory(self, product_id: int, warehouse_id: int) -> Inventory | None:
        return self.db.scalar(
            select(Inventory).where(Inventory.product_id == product_id, Inventory.warehouse_id == warehouse_id)
        )

    def get_forecasts(self, product_id: int, warehouse_id: int, start_date: date, end_date: date) -> list[DemandForecast]:
        return list(
            self.db.scalars(
                select(DemandForecast)
                .where(
                    DemandForecast.product_id == product_id,
                    DemandForecast.warehouse_id == warehouse_id,
                    DemandForecast.forecast_date >= start_date,
                    DemandForecast.forecast_date <= end_date,
                )
                .order_by(DemandForecast.forecast_date)
            )
        )

    def get_confirmed_receipts_by_date(self, product_id: int, warehouse_id: int, until_date: date) -> dict[date, int]:
        rows = self.db.execute(
            select(PurchaseOrder.expected_delivery_date, func.coalesce(func.sum(PurchaseOrderItem.quantity), 0))
            .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .where(
                PurchaseOrderItem.product_id == product_id,
                PurchaseOrder.warehouse_id == warehouse_id,
                PurchaseOrder.status.in_(["OPEN", "EXECUTED", "CONFIRMED"]),
                PurchaseOrder.expected_delivery_date <= until_date,
            )
            .group_by(PurchaseOrder.expected_delivery_date)
        ).all()
        return {row[0]: int(row[1]) for row in rows}

    def warehouse(self, warehouse_id: int) -> Warehouse | None:
        return self.db.get(Warehouse, warehouse_id)

    def current_warehouse_occupied_volume(self, warehouse_id: int) -> Decimal:
        value = self.db.scalar(
            select(func.coalesce(func.sum(Inventory.on_hand_quantity * Product.unit_volume), 0))
            .join(Product, Product.id == Inventory.product_id)
            .where(Inventory.warehouse_id == warehouse_id)
        )
        return Decimal(value or 0)

    def current_warehouse_occupancy(self, warehouse_id: int) -> int:
        return int(
            self.db.scalar(select(func.coalesce(func.sum(Inventory.on_hand_quantity), 0)).where(Inventory.warehouse_id == warehouse_id))
            or 0
        )

