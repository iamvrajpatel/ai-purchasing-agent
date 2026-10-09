from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ConstraintResult


DecisionLiteral = Literal["ACCEPT", "MODIFY", "REJECT", "INVESTIGATE"]
ConfidenceLiteral = Literal["HIGH", "MEDIUM", "LOW"]


class RecommendationCreate(BaseModel):
    product_id: int
    warehouse_id: int
    recommended_quantity: int = Field(ge=0)
    recommendation_source: str = "SYSTEM"


class RecommendationRead(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    recommended_quantity: int
    recommendation_source: str
    status: str
    created_at: datetime
    product_sku: str | None = None
    product_name: str | None = None
    warehouse_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PurchasingDecision(BaseModel):
    decision: DecisionLiteral
    original_quantity: int
    proposed_quantity: int | None = None
    supplier_id: int | None = None
    reasoning: str
    evidence: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    requires_approval: bool
    confidence: ConfidenceLiteral
    constraint_result: ConstraintResult | None = None


class PurchaseRequirement(BaseModel):
    product_id: int
    warehouse_id: int
    planning_horizon_days: int
    sellable_inventory: int
    forecast_demand: int
    timely_incoming_quantity: int
    safety_stock: int
    required_quantity: int
    stockout_date: date | None
    required_by_date: date | None
    projection: list[dict]


class SupplierCondition(BaseModel):
    supplier_id: int
    supplier_name: str
    product_id: int
    unit_price: Decimal
    minimum_order_quantity: int
    order_multiple: int
    lead_time_days: int
    available_quantity: int
    active: bool


class ProposedAction(BaseModel):
    recommendation_id: int
    product_id: int
    warehouse_id: int
    supplier_id: int
    quantity: int
    unit_price: Decimal
    total_amount: Decimal
    expected_delivery_date: date
    decision: DecisionLiteral

