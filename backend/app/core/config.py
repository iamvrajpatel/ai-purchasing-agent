from functools import lru_cache
from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_name: str = "AI Purchasing Agent API"
    database_url: str = "postgresql+psycopg://app_user:change_me@localhost:5432/ai_purchasing"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_temperature: float = 0
    agent_max_tool_calls: int = 8
    agent_timeout_seconds: int = 60

    planning_horizon_days: int = 14
    purchase_auto_approval_limit: Decimal = Field(default=Decimal("20000"))
    require_supplier_switch_approval: bool = True
    mock_buyer_user: str = "buyer@example.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()

