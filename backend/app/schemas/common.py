from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ApiError(BaseModel):
    detail: str
    code: str = "ERROR"


class CheckResult(BaseModel):
    name: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    details: str
    metadata: dict = Field(default_factory=dict)


class ConstraintViolation(BaseModel):
    code: str
    severity: Literal["BLOCKING", "WARNING"]
    message: str


class ConstraintResult(BaseModel):
    valid: bool
    checks: list[CheckResult]
    violations: list[ConstraintViolation] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    total_recommendations: int
    pending_recommendations: int
    completed_agent_decisions: int
    pending_approvals: int
    escalations: int
    recent_purchase_orders: list[dict]
    recent_agent_activity: list[dict]
    budgets: list[dict] = Field(default_factory=list)
    pending_approval_exposure: list[dict] = Field(default_factory=list)


class DateRange(BaseModel):
    start_date: date
    end_date: date


class MoneyValue(BaseModel):
    amount: Decimal


class Timestamped(BaseModel):
    created_at: datetime | None = None

