import uuid

import httpx
import pytest

from app.agents.harness.providers.deepseek import DeepSeekProvider
from app.agents.harness.registry import ModelProviderRegistry
from app.agents.harness.runner import AgentHarness
from app.models.agent import AgentVersion


@pytest.mark.asyncio
async def test_harness_executes_versioned_agent_through_deepseek_adapter() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode("utf-8")
        assert "You are a concise enterprise assistant." in body
        assert "untrusted context" in body
        assert "Summarize the issue" in body

        return httpx.Response(
            200,
            json={
                "id": "deepseek-test-1",
                "model": "deepseek-chat",
                "choices": [
                    {
                        "message": {"content": "Issue summarized."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 5,
                    "total_tokens": 25,
                },
            },
        )

    registry = ModelProviderRegistry()
    registry.register(
        "deepseek",
        lambda: DeepSeekProvider(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            transport=httpx.MockTransport(handler),
        ),
    )
    harness = AgentHarness(providers=registry)
    version = AgentVersion(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        version=3,
        system_instructions="You are a concise enterprise assistant.",
        model_provider="deepseek",
        model_name="deepseek-chat",
        temperature=0.2,
        max_tokens=1024,
        context_policy={},
        created_by_user_id=uuid.uuid4(),
    )

    result = await harness.run(
        agent_id=version.agent_id,
        version=version,
        user_input="Summarize the issue",
        additional_context=["untrusted context"],
    )

    assert result.agent_version == 3
    assert result.provider == "deepseek"
    assert result.content == "Issue summarized."
    assert result.usage.total_tokens == 25
    assert result.metadata["response_id"] == "deepseek-test-1"
