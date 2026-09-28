import json
from typing import Any

import httpx

from app.agents.harness.contracts import (
    ModelRequest,
    ModelResponse,
    ModelToolCall,
    TokenUsage,
)
from app.agents.harness.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUpstreamError,
)
from app.agents.harness.providers.base import ModelProvider


class DeepSeekProvider(ModelProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    @property
    def name(self) -> str:
        return "deepseek"

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        if not self.api_key:
            raise ProviderConfigurationError(
                "DEEPSEEK_API_KEY is not configured for model execution"
            )

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [
                message.provider_payload()
                for message in request.messages
            ],
            "stream": False,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]
            payload["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("DeepSeek request timed out") from exc
        except httpx.RequestError as exc:
            raise ProviderUpstreamError(
                f"DeepSeek transport failure: {exc.__class__.__name__}"
            ) from exc

        if response.status_code in {401, 403}:
            raise ProviderAuthenticationError(
                "DeepSeek rejected the configured API credentials"
            )
        if response.status_code == 429:
            raise ProviderRateLimitError("DeepSeek rate limit exceeded")
        if response.status_code >= 500:
            raise ProviderUpstreamError(
                f"DeepSeek upstream returned HTTP {response.status_code}"
            )
        if response.status_code >= 400:
            raise ProviderResponseError(
                f"DeepSeek returned HTTP {response.status_code}"
            )

        try:
            data = response.json()
            first_choice = data["choices"][0]
            message = first_choice["message"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderResponseError(
                "DeepSeek returned an unexpected response shape"
            ) from exc

        content_value = message.get("content")
        content = content_value if isinstance(content_value, str) else ""
        tool_calls = self._parse_tool_calls(message.get("tool_calls") or [])

        if not content and not tool_calls:
            raise ProviderResponseError(
                "DeepSeek response contained neither text nor tool calls"
            )

        usage_data = data.get("usage") or {}
        usage = TokenUsage(
            prompt_tokens=int(usage_data.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage_data.get("completion_tokens", 0) or 0),
            total_tokens=int(usage_data.get("total_tokens", 0) or 0),
        )

        return ModelResponse(
            content=content,
            provider=self.name,
            model=str(data.get("model") or request.model),
            finish_reason=first_choice.get("finish_reason"),
            usage=usage,
            response_id=str(data["id"]) if data.get("id") is not None else None,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _parse_tool_calls(raw_calls: list[Any]) -> list[ModelToolCall]:
        parsed: list[ModelToolCall] = []
        for raw_call in raw_calls:
            try:
                function = raw_call["function"]
                raw_arguments = function.get("arguments") or "{}"
                arguments = (
                    json.loads(raw_arguments)
                    if isinstance(raw_arguments, str)
                    else raw_arguments
                )
                if not isinstance(arguments, dict):
                    raise TypeError("Tool arguments must be an object")
                parsed.append(
                    ModelToolCall(
                        id=str(raw_call["id"]),
                        name=str(function["name"]),
                        arguments=arguments,
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ProviderResponseError(
                    "DeepSeek returned an invalid tool call"
                ) from exc
        return parsed
