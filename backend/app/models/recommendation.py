from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PurchaseRecommendation(Base):
    __tablename__ = "purchase_recommendations"
    __table_args__ = (
        CheckConstraint("recommended_quantity >= 0", name="ck_recommendations_qty_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    recommended_quantity: Mapped[int] = mapped_column()
    recommendation_source: Mapped[str] = mapped_column(String(120), default="SYSTEM")
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product")
    warehouse = relationship("Warehouse")
    agent_runs = relationship("AgentRun", back_populates="recommendation")

