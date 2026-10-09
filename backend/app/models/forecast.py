from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DemandForecast(Base):
    __tablename__ = "demand_forecasts"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", "forecast_date", name="uq_forecast_product_warehouse_date"),
        CheckConstraint("expected_quantity >= 0", name="ck_forecast_expected_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    forecast_date: Mapped[date] = mapped_column(Date, index=True)
    expected_quantity: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product")
    warehouse = relationship("Warehouse")


class DailySale(Base):
    __tablename__ = "daily_sales"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", "sales_date", name="uq_sales_product_warehouse_date"),
        CheckConstraint("units_sold >= 0", name="ck_daily_sales_units_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    sales_date: Mapped[date] = mapped_column(Date, index=True)
    units_sold: Mapped[int] = mapped_column()

    product = relationship("Product")
    warehouse = relationship("Warehouse")

