import uuid

import pytest

from app.agents.harness.contracts import (
    ModelRequest,
    ModelResponse,
    ModelToolCall,
    TokenUsage,
)
from app.agents.harness.providers.base import ModelProvider
from app.agents.harness.registry import ModelProviderRegistry
from app.agents.harness.runner import AgentHarness
from app.models.agent import AgentVersion
from app.models.skill import Skill, SkillVersion
from app.skills.executor import SkillExecutor
from app.skills.local_handlers import LOCAL_SKILL_HANDLERS
from app.skills.providers.local import LocalSkillAdapter
from app.skills.registry import SkillProviderRegistry


class ToolCallingProvider(ModelProvider):
    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    @property
    def name(self) -> str:
        return "fake"

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            return ModelResponse(
                content="",
                provider="fake",
                model=request.model,
                finish_reason="tool_calls",
                usage=TokenUsage(
                    prompt_tokens=10,
                    completion_tokens=2,
                    total_tokens=12,
                ),
                tool_calls=[
                    ModelToolCall(
                        id="tool-call-1",
                        name="math_add",
                        arguments={"left": 2, "right": 3},
                    )
                ],
            )

        tool_messages = [
            message
            for message in request.messages
            if message.role == "tool"
        ]
        assert len(tool_messages) == 1
        assert '"ok":true' in (tool_messages[0].content or "")
        assert '"result":5.0' in (tool_messages[0].content or "")

        return ModelResponse(
            content="The result is 5.",
            provider="fake",
            model=request.model,
            finish_reason="stop",
            usage=TokenUsage(
                prompt_tokens=15,
                completion_tokens=5,
                total_tokens=20,
            ),
        )


def build_bound_math_skill() -> SkillVersion:
    skill = Skill(
        id=uuid.uuid4(),
        name="math_add",
        description="Add two numeric values.",
        provider_type="local",
        status="active",
    )
    return SkillVersion(
        id=uuid.uuid4(),
        skill_id=skill.id,
        skill=skill,
        version=1,
        input_schema={
            "type": "object",
            "properties": {
                "left": {"type": "number"},
                "right": {"type": "number"},
            },
            "required": ["left", "right"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {"result": {"type": "number"}},
            "required": ["result"],
            "additionalProperties": False,
        },
        required_permissions=["skill:execute"],
        side_effect="READ_ONLY",
        timeout_seconds=5,
        max_attempts=1,
        provider_config={"handler": "math_add"},
    )


@pytest.mark.asyncio
async def test_harness_returns_skill_result_to_model() -> None:
    model_provider = ToolCallingProvider()
    model_registry = ModelProviderRegistry()
    model_registry.register("fake", lambda: model_provider)

    skill_registry = SkillProviderRegistry()
    skill_registry.register(
        "local",
        LocalSkillAdapter(LOCAL_SKILL_HANDLERS),
    )
    skill_executor = SkillExecutor(skill_registry)

    skill_version = build_bound_math_skill()
    version = AgentVersion(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        version=1,
        system_instructions="Use bound tools when useful.",
        model_provider="fake",
        model_name="fake-model",
        temperature=0.0,
        max_tokens=512,
        context_policy={},
        created_by_user_id=uuid.uuid4(),
        bound_skill_versions=[skill_version],
    )
    harness = AgentHarness(
        providers=model_registry,
        skill_executor=skill_executor,
    )

    result = await harness.run(
        agent_id=version.agent_id,
        version=version,
        user_input="What is 2 + 3?",
        granted_permissions={"skill:execute"},
    )

    assert result.content == "The result is 5."
    assert result.usage.total_tokens == 32
    assert len(result.tool_results) == 1
    assert result.tool_results[0]["ok"] is True
    assert len(model_provider.requests) == 2
    assert [tool.name for tool in model_provider.requests[0].tools] == ["math_add"]
