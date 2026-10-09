from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class FrontendSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    backend_api_url: str = "http://localhost:8000"
    frontend_host: str = "0.0.0.0"
    frontend_port: int = 8001
    mock_buyer_user: str = "buyer@example.com"


@lru_cache
def get_settings() -> FrontendSettings:
    return FrontendSettings()

