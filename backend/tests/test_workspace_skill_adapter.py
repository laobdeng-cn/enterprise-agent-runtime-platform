import uuid
from typing import Any

import pytest

from app.models.skill import Skill, SkillVersion
from app.skills.contracts import SkillExecutionContext
from app.skills.errors import SkillExecutionContextError
from app.skills.providers.workspace import WorkspaceSkillAdapter


class FakeWorkspaceCapabilities:
    def __init__(self) -> None:
        self.calls: list[tuple[str, uuid.UUID, dict[str, Any]]] = []

    async def list_entries(
        self,
        run_id: uuid.UUID,
        relative_path: str,
    ) -> list[dict[str, Any]]:
        self.calls.append(("list", run_id, {"path": relative_path}))
        return []

    async def read_text(
        self,
        run_id: uuid.UUID,
        relative_path: str,
    ) -> dict[str, Any]:
        self.calls.append(("read", run_id, {"path": relative_path}))
        return {"path": relative_path, "content": "hello"}

    async def write_text(
        self,
        run_id: uuid.UUID,
        relative_path: str,
        content: str,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "write",
                run_id,
                {"path": relative_path, "content": content},
            )
        )
        return {
            "path": relative_path,
            "size_bytes": len(content.encode()),
            "sha256": "0" * 64,
        }

    async def publish_artifact(
        self,
        run_id: uuid.UUID,
        source_path: str,
        display_name: str | None,
        kind: str,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "publish",
                run_id,
                {
                    "source_path": source_path,
                    "display_name": display_name,
                    "kind": kind,
                },
            )
        )
        return {
            "artifact_id": str(uuid.uuid4()),
            "path": "artifacts/id/report.md",
            "display_name": "report.md",
            "media_type": "text/markdown",
            "size_bytes": 5,
            "sha256": "0" * 64,
        }


def build_workspace_skill(action: str) -> SkillVersion:
    skill = Skill(
        id=uuid.uuid4(),
        name=f"workspace_{action}",
        description="test",
        provider_type="workspace",
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
async def test_workspace_adapter_requires_durable_run_context() -> None:
    adapter = WorkspaceSkillAdapter(FakeWorkspaceCapabilities())

    with pytest.raises(SkillExecutionContextError):
        await adapter.execute(
            build_workspace_skill("list"),
            {"path": "working"},
        )


@pytest.mark.asyncio
async def test_workspace_adapter_routes_write_to_run_workspace() -> None:
    capabilities = FakeWorkspaceCapabilities()
    adapter = WorkspaceSkillAdapter(capabilities)
    run_id = uuid.uuid4()

    result = await adapter.execute(
        build_workspace_skill("write_text"),
        {
            "path": "working/report.md",
            "content": "hello",
        },
        SkillExecutionContext(run_id=run_id),
    )

    assert result["path"] == "working/report.md"
    assert capabilities.calls == [
        (
            "write",
            run_id,
            {
                "path": "working/report.md",
                "content": "hello",
            },
        )
    ]
