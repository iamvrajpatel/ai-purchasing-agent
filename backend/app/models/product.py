from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("unit_volume >= 0", name="ck_products_unit_volume_non_negative"),
        CheckConstraint("safety_stock >= 0", name="ck_products_safety_stock_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(120), index=True)
    unit_volume: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("1"))
    safety_stock: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    inventory_records = relationship("Inventory", back_populates="product")
    supplier_products = relationship("SupplierProduct", back_populates="product")

