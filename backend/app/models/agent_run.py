from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.types import JSONDict


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("purchase_recommendations.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="CREATED", index=True)
    decision: Mapped[str | None] = mapped_column(String(40), index=True)
    original_quantity: Mapped[int | None] = mapped_column(Integer)
    proposed_quantity: Mapped[int | None] = mapped_column(Integer)
    proposed_supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    reasoning: Mapped[str | None] = mapped_column(Text)
    evidence_snapshot: Mapped[dict | None] = mapped_column(JSONDict)
    model_name: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    recommendation = relationship("PurchaseRecommendation", back_populates="agent_runs")
    proposed_supplier = relationship("Supplier")
    tool_calls = relationship("AgentToolCall", back_populates="agent_run", cascade="all, delete-orphan")
    events = relationship("AgentEvent", back_populates="agent_run", cascade="all, delete-orphan")
    validations = relationship("AgentValidation", back_populates="agent_run", cascade="all, delete-orphan")


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(120), index=True)
    input_json: Mapped[dict] = mapped_column(JSONDict)
    output_json: Mapped[dict | None] = mapped_column(JSONDict)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent_run = relationship("AgentRun", back_populates="tool_calls")


class AgentValidation(Base):
    __tablename__ = "agent_validations"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    validation_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    checks_json: Mapped[dict] = mapped_column(JSONDict)
    errors_json: Mapped[list | None] = mapped_column(JSONDict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent_run = relationship("AgentRun", back_populates="validations")
    purchase_order = relationship("PurchaseOrder")


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONDict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent_run = relationship("AgentRun", back_populates="events")

