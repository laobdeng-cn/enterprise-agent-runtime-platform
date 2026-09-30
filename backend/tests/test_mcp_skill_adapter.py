import uuid
from typing import Any

import pytest

from app.models.skill import Skill, SkillVersion
from app.skills.contracts import SkillExecutionContext
from app.skills.errors import SkillExecutionContextError
from app.skills.providers.mcp import MCPSkillAdapter


class FakeMCPExecution:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(
        self,
        *,
        server_id: uuid.UUID,
        tool_name: str,
        arguments: dict[str, Any],
        principal_id: uuid.UUID,
        run_id: uuid.UUID | None,
    ) -> Any:
        self.calls.append(
            {
                "server_id": server_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "principal_id": principal_id,
                "run_id": run_id,
            }
        )
        return {"ok": True, "matches": [{"id": "kb-1"}]}


def build_mcp_skill(server_id: uuid.UUID) -> SkillVersion:
    skill = Skill(
        id=uuid.uuid4(),
        name="knowledge_search_documents",
        description="Search approved internal knowledge.",
        provider_type="mcp",
        status="active",
    )
    return SkillVersion(
        id=uuid.uuid4(),
        skill_id=skill.id,
        skill=skill,
        version=1,
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        output_schema={},
        required_permissions=[
            "skill:execute",
            "mcp:execute",
            "knowledge:read",
        ],
        side_effect="READ_ONLY",
        timeout_seconds=20,
        max_attempts=1,
        provider_config={
            "mcp_server_id": str(server_id),
            "tool_name": "search_documents",
        },
    )


@pytest.mark.asyncio
async def test_mcp_skill_requires_authenticated_execution_context() -> None:
    adapter = MCPSkillAdapter(FakeMCPExecution())

    with pytest.raises(SkillExecutionContextError):
        await adapter.execute(
            build_mcp_skill(uuid.uuid4()),
            {"query": "perovskite"},
        )


@pytest.mark.asyncio
async def test_mcp_skill_binds_call_to_current_principal_and_run() -> None:
    server_id = uuid.uuid4()
    principal_id = uuid.uuid4()
    run_id = uuid.uuid4()
    execution = FakeMCPExecution()
    adapter = MCPSkillAdapter(execution)

    output = await adapter.execute(
        build_mcp_skill(server_id),
        {"query": "perovskite"},
        SkillExecutionContext(
            principal_id=principal_id,
            run_id=run_id,
        ),
    )

    assert output["ok"] is True
    assert execution.calls == [
        {
            "server_id": server_id,
            "tool_name": "search_documents",
            "arguments": {"query": "perovskite"},
            "principal_id": principal_id,
            "run_id": run_id,
        }
    ]
