from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint("reliability_score >= 0 AND reliability_score <= 1", name="ck_supplier_reliability_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    contact_email: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    reliability_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.900"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    products = relationship("SupplierProduct", back_populates="supplier")


class SupplierProduct(Base):
    __tablename__ = "supplier_products"
    __table_args__ = (
        UniqueConstraint("supplier_id", "product_id", name="uq_supplier_products_supplier_product"),
        CheckConstraint("unit_price >= 0", name="ck_supplier_products_unit_price_non_negative"),
        CheckConstraint("minimum_order_quantity >= 0", name="ck_supplier_products_moq_non_negative"),
        CheckConstraint("order_multiple > 0", name="ck_supplier_products_order_multiple_positive"),
        CheckConstraint("lead_time_days >= 0", name="ck_supplier_products_lead_time_non_negative"),
        CheckConstraint("available_quantity >= 0", name="ck_supplier_products_available_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    minimum_order_quantity: Mapped[int] = mapped_column(default=1)
    order_multiple: Mapped[int] = mapped_column(default=1)
    lead_time_days: Mapped[int] = mapped_column(default=1)
    available_quantity: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    supplier = relationship("Supplier", back_populates="products")
    product = relationship("Product", back_populates="supplier_products")

