import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.workspace import Artifact, Workspace
from app.workspace.errors import WorkspaceNotFoundError
from app.workspace.storage import WorkspaceStorage

workspace_storage = WorkspaceStorage(Path(settings.workspace_root))


async def create_workspace(
    session: AsyncSession,
    run_id: UUID,
) -> Workspace:
    workspace = Workspace(
        run_id=run_id,
        storage_key=str(run_id),
        status="active",
        quota_bytes=settings.workspace_quota_bytes,
        max_file_bytes=settings.workspace_max_file_bytes,
    )
    session.add(workspace)
    await session.flush()
    workspace_storage.initialize(workspace.storage_key)
    return workspace


async def get_workspace(
    session: AsyncSession,
    run_id: UUID,
) -> Workspace:
    result = await session.execute(
        select(Workspace)
        .options(selectinload(Workspace.artifacts))
        .where(Workspace.run_id == run_id)
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise WorkspaceNotFoundError(
            f"Workspace for Run {run_id} was not found"
        )
    return workspace


async def list_artifacts(
    session: AsyncSession,
    workspace_id: UUID,
) -> list[Artifact]:
    result = await session.execute(
        select(Artifact)
        .where(Artifact.workspace_id == workspace_id)
        .order_by(Artifact.created_at)
    )
    return list(result.scalars().all())


async def get_artifact(
    session: AsyncSession,
    workspace_id: UUID,
    artifact_id: UUID,
) -> Artifact:
    result = await session.execute(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.workspace_id == workspace_id,
        )
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise WorkspaceNotFoundError(
            f"Artifact {artifact_id} was not found"
        )
    return artifact


async def publish_artifact(
    session: AsyncSession,
    workspace: Workspace,
    *,
    source_path: str,
    display_name: str | None,
    kind: str,
    created_by: str,
    source_step_id: UUID | None = None,
) -> Artifact:
    artifact_id = uuid.uuid4()
    metadata = workspace_storage.publish_artifact(
        workspace.storage_key,
        source_path,
        artifact_id=artifact_id,
        display_name=display_name or Path(source_path).name,
        max_file_bytes=workspace.max_file_bytes,
        quota_bytes=workspace.quota_bytes,
    )
    artifact = Artifact(
        id=artifact_id,
        workspace_id=workspace.id,
        source_step_id=source_step_id,
        relative_path=str(metadata["relative_path"]),
        display_name=str(metadata["display_name"]),
        kind=kind,
        media_type=str(metadata["media_type"]),
        size_bytes=int(metadata["size_bytes"]),
        sha256=str(metadata["sha256"]),
        created_by=created_by,
    )
    session.add(artifact)
    await session.flush()
    return artifact


class WorkspaceCapabilityService:
    def __init__(
        self,
        *,
        storage: WorkspaceStorage,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.storage = storage
        self.session_factory = session_factory

    async def list_entries(
        self,
        run_id: UUID,
        relative_path: str,
    ) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            workspace = await get_workspace(session, run_id)
            return self.storage.list_entries(
                workspace.storage_key,
                relative_path,
            )

    async def read_text(
        self,
        run_id: UUID,
        relative_path: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as session:
            workspace = await get_workspace(session, run_id)
            content = self.storage.read_text(
                workspace.storage_key,
                relative_path,
                max_file_bytes=workspace.max_file_bytes,
            )
            return {
                "path": relative_path,
                "content": content,
            }

    async def write_text(
        self,
        run_id: UUID,
        relative_path: str,
        content: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as session:
            workspace = await get_workspace(session, run_id)
            return self.storage.write_text(
                workspace.storage_key,
                relative_path,
                content,
                max_file_bytes=workspace.max_file_bytes,
                quota_bytes=workspace.quota_bytes,
                allowed_roots={"working"},
            )

    async def publish_artifact(
        self,
        run_id: UUID,
        source_path: str,
        display_name: str | None,
        kind: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as session:
            workspace = await get_workspace(session, run_id)
            artifact = await publish_artifact(
                session,
                workspace,
                source_path=source_path,
                display_name=display_name,
                kind=kind,
                created_by="agent",
            )
            await session.commit()
            return {
                "artifact_id": str(artifact.id),
                "path": artifact.relative_path,
                "display_name": artifact.display_name,
                "media_type": artifact.media_type,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }


workspace_capabilities = WorkspaceCapabilityService(
    storage=workspace_storage,
    session_factory=async_session_maker,
)
