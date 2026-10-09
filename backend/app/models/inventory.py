from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", name="uq_inventory_product_warehouse"),
        CheckConstraint("on_hand_quantity >= 0", name="ck_inventory_on_hand_non_negative"),
        CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_non_negative"),
        CheckConstraint("damaged_quantity >= 0", name="ck_inventory_damaged_non_negative"),
        CheckConstraint("reserved_quantity + damaged_quantity <= on_hand_quantity", name="ck_inventory_valid_stock_state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    on_hand_quantity: Mapped[int] = mapped_column(default=0)
    reserved_quantity: Mapped[int] = mapped_column(default=0)
    damaged_quantity: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    product = relationship("Product", back_populates="inventory_records")
    warehouse = relationship("Warehouse", back_populates="inventory_records")

    @property
    def sellable_quantity(self) -> int:
        return max(0, self.on_hand_quantity - self.reserved_quantity - self.damaged_quantity)

