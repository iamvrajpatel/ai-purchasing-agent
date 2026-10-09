from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.types import JSONDict


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_purchase_orders_idempotency_key"),
        CheckConstraint("total_amount >= 0", name="ck_purchase_orders_total_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="PROPOSED", index=True)
    supplier_confirmation_status: Mapped[str | None] = mapped_column(String(40), index=True)
    supplier_response_json: Mapped[dict | None] = mapped_column(JSONDict)
    expected_delivery_date: Mapped[date] = mapped_column(Date, index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    source_recommendation_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_recommendations.id"), index=True)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    external_reference: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    supplier = relationship("Supplier")
    warehouse = relationship("Warehouse")
    source_recommendation = relationship("PurchaseRecommendation")
    agent_run = relationship("AgentRun")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_po_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_po_items_unit_price_non_negative"),
        CheckConstraint("line_total >= 0", name="ck_po_items_line_total_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column()
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    purchase_order = relationship("PurchaseOrder", back_populates="items")
    product = relationship("Product")

