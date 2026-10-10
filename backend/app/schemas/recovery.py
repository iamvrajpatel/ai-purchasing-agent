from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


RecoveryDecisionLiteral = Literal["SOURCE_REMAINDER", "NO_ACTION_REQUIRED", "ESCALATE"]


class RecoveryProposedAction(BaseModel):
    purchase_order_id: int
    product_id: int
    warehouse_id: int
    supplier_id: int
    quantity: int
    unit_price: Decimal
    total_amount: Decimal
    expected_delivery_date: date
    decision: Literal["SOURCE_REMAINDER"]


class RecoveryCaseDetail(BaseModel):
    id: int
    purchase_order_id: int
    agent_run_id: int | None
    supplemental_purchase_order_id: int | None
    status: str
    decision: str | None
    requested_quantity: int
    confirmed_quantity: int
    shortfall_quantity: int
    reasoning: str | None
    evidence: dict
    risks: list
    missing_information: list
    proposed_action: dict | None
    approval: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
