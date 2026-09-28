import uuid
from typing import Any

import pytest

from app.agents.harness.contracts import ModelToolCall
from app.models.skill import Skill, SkillVersion
from app.skills.errors import SkillRetryableProviderError
from app.skills.executor import SkillExecutor
from app.skills.local_handlers import LOCAL_SKILL_HANDLERS
from app.skills.providers.base import SkillProviderAdapter
from app.skills.providers.local import LocalSkillAdapter
from app.skills.registry import SkillProviderRegistry


def build_math_skill(*, max_attempts: int = 1) -> SkillVersion:
    skill = Skill(
        id=uuid.uuid4(),
        name="math_add",
        description="Add two values.",
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
        max_attempts=max_attempts,
        provider_config={"handler": "math_add"},
    )


@pytest.mark.asyncio
async def test_skill_executor_validates_and_executes_local_skill() -> None:
    providers = SkillProviderRegistry()
    providers.register("local", LocalSkillAdapter(LOCAL_SKILL_HANDLERS))
    executor = SkillExecutor(providers)
    version = build_math_skill()

    result = await executor.execute(
        ModelToolCall(
            id="call-1",
            name="math_add",
            arguments={"left": 2, "right": 3},
        ),
        bound_versions=[version],
        granted_permissions={"skill:execute"},
    )

    assert result.ok is True
    assert result.output == {"result": 5.0}
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_skill_executor_rejects_invalid_arguments() -> None:
    providers = SkillProviderRegistry()
    providers.register("local", LocalSkillAdapter(LOCAL_SKILL_HANDLERS))
    executor = SkillExecutor(providers)
    version = build_math_skill()

    result = await executor.execute(
        ModelToolCall(
            id="call-2",
            name="math_add",
            arguments={"left": 2, "unexpected": 3},
        ),
        bound_versions=[version],
        granted_permissions={"skill:execute"},
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "SKILL_INPUT_VALIDATION"


@pytest.mark.asyncio
async def test_skill_executor_enforces_permission_metadata() -> None:
    providers = SkillProviderRegistry()
    providers.register("local", LocalSkillAdapter(LOCAL_SKILL_HANDLERS))
    executor = SkillExecutor(providers)
    version = build_math_skill()

    result = await executor.execute(
        ModelToolCall(
            id="call-3",
            name="math_add",
            arguments={"left": 2, "right": 3},
        ),
        bound_versions=[version],
        granted_permissions=set(),
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "SKILL_PERMISSION_DENIED"


class FlakyAdapter(SkillProviderAdapter):
    def __init__(self) -> None:
        self.attempts = 0

    async def execute(
        self,
        version: SkillVersion,
        arguments: dict[str, Any],
    ) -> Any:
        self.attempts += 1
        if self.attempts == 1:
            raise SkillRetryableProviderError("transient")
        return {"result": float(arguments["left"]) + float(arguments["right"])}


@pytest.mark.asyncio
async def test_skill_executor_retries_only_retryable_failures() -> None:
    adapter = FlakyAdapter()
    providers = SkillProviderRegistry()
    providers.register("local", adapter)
    executor = SkillExecutor(providers)
    version = build_math_skill(max_attempts=2)

    result = await executor.execute(
        ModelToolCall(
            id="call-4",
            name="math_add",
            arguments={"left": 4, "right": 5},
        ),
        bound_versions=[version],
        granted_permissions={"skill:execute"},
    )

    assert result.ok is True
    assert result.output == {"result": 9.0}
    assert result.attempts == 2
    assert adapter.attempts == 2
