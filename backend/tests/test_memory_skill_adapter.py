import uuid
from typing import Any

import pytest

from app.memory.contracts import MemoryScope, MemoryType
from app.models.skill import Skill, SkillVersion
from app.skills.contracts import SkillExecutionContext
from app.skills.errors import SkillExecutionContextError
from app.skills.providers.memory import MemorySkillAdapter


class FakeMemoryCapabilities:
    def __init__(self) -> None:
        self.search_calls: list[dict[str, Any]] = []
        self.write_calls: list[dict[str, Any]] = []

    async def search(
        self,
        *,
        run_id: uuid.UUID,
        principal_id: uuid.UUID,
        query: str,
        memory_types: set[MemoryType] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        self.search_calls.append(
            {
                "run_id": run_id,
                "principal_id": principal_id,
                "query": query,
                "memory_types": memory_types,
                "limit": limit,
            }
        )
        return []

    async def write(
        self,
        *,
        run_id: uuid.UUID,
        principal_id: uuid.UUID,
        memory_type: MemoryType,
        scope: MemoryScope,
        content: str,
        label: str | None,
        importance: float,
        ttl_seconds: int | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        self.write_calls.append(
            {
                "run_id": run_id,
                "principal_id": principal_id,
                "memory_type": memory_type,
                "scope": scope,
                "content": content,
                "label": label,
                "importance": importance,
                "ttl_seconds": ttl_seconds,
                "metadata": metadata,
            }
        )
        return {
            "id": str(uuid.uuid4()),
            "memory_type": memory_type.value,
            "scope": scope.value,
            "status": "ACTIVE",
            "content": content,
            "importance": importance,
            "expires_at": None,
        }


def build_memory_skill(name: str, action: str) -> SkillVersion:
    skill = Skill(
        id=uuid.uuid4(),
        name=name,
        description="memory test",
        provider_type="memory",
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
        side_effect="READ_ONLY",
        timeout_seconds=5,
        max_attempts=1,
        provider_config={"action": action},
    )


@pytest.mark.asyncio
async def test_memory_skill_requires_run_and_principal_context() -> None:
    adapter = MemorySkillAdapter(FakeMemoryCapabilities())

    with pytest.raises(SkillExecutionContextError):
        await adapter.execute(
            build_memory_skill("memory_search", "search"),
            {"query": "runtime"},
        )


@pytest.mark.asyncio
async def test_memory_write_is_bound_to_current_run_principal() -> None:
    capabilities = FakeMemoryCapabilities()
    adapter = MemorySkillAdapter(capabilities)
    run_id = uuid.uuid4()
    principal_id = uuid.uuid4()

    result = await adapter.execute(
        build_memory_skill("memory_write", "write"),
        {
            "memory_type": "LONG_TERM",
            "scope": "AGENT",
            "content": "Prefer concise Markdown reports.",
            "importance": 0.9,
        },
        SkillExecutionContext(
            run_id=run_id,
            principal_id=principal_id,
        ),
    )

    assert result["status"] == "ACTIVE"
    assert capabilities.write_calls[0]["run_id"] == run_id
    assert capabilities.write_calls[0]["principal_id"] == principal_id
    assert capabilities.write_calls[0]["scope"] == MemoryScope.AGENT
