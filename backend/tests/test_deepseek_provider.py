import httpx
import pytest

from app.agents.harness.contracts import ModelMessage, ModelRequest
from app.agents.harness.errors import ProviderRateLimitError
from app.agents.harness.providers.deepseek import DeepSeekProvider


@pytest.mark.asyncio
async def test_deepseek_provider_normalizes_success() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.url.path == "/chat/completions"
        return httpx.Response(
            200,
            json={
                "id": "response-1",
                "model": "deepseek-chat",
                "choices": [
                    {
                        "message": {"content": "normalized answer"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            },
        )

    provider = DeepSeekProvider(
        api_key="test-key",
        base_url="https://api.deepseek.com",
        transport=httpx.MockTransport(handler),
    )
    response = await provider.invoke(
        ModelRequest(
            model="deepseek-chat",
            messages=[ModelMessage(role="user", content="hello")],
        )
    )

    assert response.provider == "deepseek"
    assert response.content == "normalized answer"
    assert response.usage.total_tokens == 14
    assert response.response_id == "response-1"


@pytest.mark.asyncio
async def test_deepseek_provider_normalizes_rate_limit() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "slow down"}})

    provider = DeepSeekProvider(
        api_key="test-key",
        base_url="https://api.deepseek.com",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderRateLimitError) as exc_info:
        await provider.invoke(
            ModelRequest(
                model="deepseek-chat",
                messages=[ModelMessage(role="user", content="hello")],
            )
        )

    assert exc_info.value.retryable is True
