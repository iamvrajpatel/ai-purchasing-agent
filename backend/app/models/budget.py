from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PurchasingBudget(Base):
    __tablename__ = "purchasing_budgets"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "budget_period", name="uq_budget_warehouse_period"),
        CheckConstraint("total_budget >= 0", name="ck_budget_total_non_negative"),
        CheckConstraint("reserved_amount >= 0", name="ck_budget_reserved_non_negative"),
        CheckConstraint("committed_amount >= 0", name="ck_budget_committed_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    budget_period: Mapped[str] = mapped_column(String(32), index=True)
    total_budget: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reserved_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    committed_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    version: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    warehouse = relationship("Warehouse")

    @property
    def available_budget(self) -> Decimal:
        return self.total_budget - self.reserved_amount - self.committed_amount

