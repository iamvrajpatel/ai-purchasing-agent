from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ApprovalRead(BaseModel):
    id: int
    agent_run_id: int
    proposed_action_json: dict
    status: str
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderItemRead(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    line_total: Decimal

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderRead(BaseModel):
    id: int
    supplier_id: int
    warehouse_id: int
    status: str
    supplier_confirmation_status: str | None
    expected_delivery_date: date
    total_amount: Decimal
    source_recommendation_id: int | None
    agent_run_id: int | None
    idempotency_key: str
    external_reference: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderDetail(PurchaseOrderRead):
    supplier_response_json: dict | None
    items: list[PurchaseOrderItemRead]
    validations: list[dict] = []

