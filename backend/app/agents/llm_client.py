import json
from typing import Any

from openai import AsyncOpenAI, OpenAIError

from app.core.config import get_settings
from app.utils.exceptions import AgentConfigurationError, DomainError


class DirectOpenAIClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.openai_api_key:
            raise AgentConfigurationError("OPENAI_API_KEY is required for live agent analysis")
        self.client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            base_url="https://api.openai.com/v1",
            timeout=self.settings.agent_timeout_seconds,
        )

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None, tool_choice: str | dict = "auto") -> dict:
        payload: dict[str, Any] = {"model": self.settings.openai_model, "messages": messages}
        if self.settings.openai_temperature is not None:
            payload["temperature"] = self.settings.openai_temperature
        if tools is not None:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        try:
            response = await self.client.chat.completions.create(**payload)
        except OpenAIError as exc:
            raise DomainError(f"OpenAI API request failed: {exc}") from exc
        message = response.choices[0].message
        return message.model_dump(exclude_none=True)


def parse_json_object(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise DomainError("LLM did not return valid JSON") from exc

