import uuid

import pytest

from app.models.skill import Skill, SkillVersion
from app.sandbox.contracts import (
    SandboxExecutionResponse,
    SandboxStatus,
)
from app.skills.contracts import SkillExecutionContext
from app.skills.errors import SkillExecutionContextError
from app.skills.providers.sandbox import SandboxSkillAdapter


class FakeSandboxCapabilities:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, str, bool, str]] = []

    async def execute_python(
        self,
        run_id: uuid.UUID,
        code: str,
        *,
        publish_outputs: bool = True,
        created_by: str = "agent",
    ) -> SandboxExecutionResponse:
        self.calls.append((run_id, code, publish_outputs, created_by))
        return SandboxExecutionResponse(
            execution_id=uuid.uuid4(),
            run_id=run_id,
            status=SandboxStatus.SUCCEEDED,
            exit_code=0,
            stdout="ok\n",
            stderr="",
            duration_ms=10.0,
            timed_out=False,
            artifacts=[],
        )


def build_python_skill() -> SkillVersion:
    skill = Skill(
        id=uuid.uuid4(),
        name="python_execute",
        description="Execute isolated Python.",
        provider_type="sandbox",
        status="active",
    )
    return SkillVersion(
        id=uuid.uuid4(),
        skill_id=skill.id,
        skill=skill,
        version=1,
        input_schema={},
        output_schema={},
        required_permissions=[],
        side_effect="REVERSIBLE_WRITE",
        timeout_seconds=10,
        max_attempts=1,
        provider_config={"action": "python_execute"},
    )


@pytest.mark.asyncio
async def test_sandbox_skill_requires_run_context() -> None:
    adapter = SandboxSkillAdapter(FakeSandboxCapabilities())

    with pytest.raises(SkillExecutionContextError):
        await adapter.execute(
            build_python_skill(),
            {"code": "print('x')"},
        )


@pytest.mark.asyncio
async def test_sandbox_skill_forwards_current_run_context() -> None:
    capabilities = FakeSandboxCapabilities()
    adapter = SandboxSkillAdapter(capabilities)
    run_id = uuid.uuid4()

    result = await adapter.execute(
        build_python_skill(),
        {
            "code": "print('ok')",
            "publish_artifacts": False,
        },
        SkillExecutionContext(run_id=run_id),
    )

    assert result["status"] == "SUCCEEDED"
    assert result["stdout"] == "ok\n"
    assert capabilities.calls == [
        (
            run_id,
            "print('ok')",
            False,
            "agent",
        )
    ]
