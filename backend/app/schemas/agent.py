from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.purchasing import PurchasingDecision


class AgentAnalyzeRequest(BaseModel):
    recommendation_id: int


class AgentToolCallRead(BaseModel):
    id: int
    tool_name: str
    input_json: dict
    output_json: dict | None
    success: bool
    duration_ms: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentEventRead(BaseModel):
    id: int
    event_type: str
    message: str
    metadata_json: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentValidationRead(BaseModel):
    id: int
    agent_run_id: int
    purchase_order_id: int | None
    validation_type: str
    status: str
    checks_json: dict
    errors_json: list | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentRunRead(BaseModel):
    id: int
    recommendation_id: int
    status: str
    decision: str | None
    original_quantity: int | None
    proposed_quantity: int | None
    proposed_supplier_id: int | None
    reasoning: str | None
    evidence_snapshot: dict | None
    model_name: str | None
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


class AgentRunDetail(AgentRunRead):
    tool_calls: list[AgentToolCallRead] = []
    events: list[AgentEventRead] = []
    validations: list[AgentValidationRead] = []
    structured_decision: PurchasingDecision | None = None

