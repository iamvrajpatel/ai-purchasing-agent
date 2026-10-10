from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.types import JSONDict


class PurchaseOrderRecoveryCase(Base):
    __tablename__ = "purchase_order_recovery_cases"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", name="uq_recovery_cases_purchase_order_id"),
        CheckConstraint("requested_quantity >= 0", name="ck_recovery_requested_non_negative"),
        CheckConstraint("confirmed_quantity >= 0", name="ck_recovery_confirmed_non_negative"),
        CheckConstraint("shortfall_quantity >= 0", name="ck_recovery_shortfall_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    supplemental_purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)
    decision: Mapped[str | None] = mapped_column(String(40), index=True)
    requested_quantity: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_quantity: Mapped[int] = mapped_column(Integer, default=0)
    shortfall_quantity: Mapped[int] = mapped_column(Integer, default=0)
    reasoning: Mapped[str | None] = mapped_column(Text)
    evidence_json: Mapped[dict | None] = mapped_column(JSONDict)
    risks_json: Mapped[list | None] = mapped_column(JSONDict)
    missing_information_json: Mapped[list | None] = mapped_column(JSONDict)
    proposed_action_json: Mapped[dict | None] = mapped_column(JSONDict)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    purchase_order = relationship("PurchaseOrder", foreign_keys=[purchase_order_id])
    supplemental_purchase_order = relationship("PurchaseOrder", foreign_keys=[supplemental_purchase_order_id])
    agent_run = relationship("AgentRun")
