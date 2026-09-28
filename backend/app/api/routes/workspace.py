from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.db.session import get_db
from app.models.identity import User
from app.models.workspace import Artifact
from app.schemas.workspace import (
    ArtifactPublishRequest,
    ArtifactResponse,
    WorkspaceEntryResponse,
    WorkspaceResponse,
    WorkspaceTextResponse,
    WorkspaceTextWriteRequest,
    WorkspaceWriteResult,
)
from app.services.runtime import RunAccessDeniedError, RunNotFoundError, get_run
from app.services.workspaces import (
    get_artifact,
    get_workspace,
    list_artifacts,
    publish_artifact,
    workspace_storage,
)
from app.workspace.errors import (
    UnsafeWorkspacePathError,
    WorkspaceEncodingError,
    WorkspaceError,
    WorkspaceFileNotFoundError,
    WorkspaceFileTooLargeError,
    WorkspaceFileTypeError,
    WorkspaceNotFoundError,
    WorkspaceQuotaExceededError,
)

router = APIRouter(tags=["workspace"])

WorkspaceReader = Annotated[
    User,
    Depends(require_permissions("run:read", "workspace:read")),
]
WorkspaceWriter = Annotated[
    User,
    Depends(require_permissions("run:read", "workspace:write")),
]
ArtifactReader = Annotated[
    User,
    Depends(require_permissions("run:read", "artifact:read")),
]
ArtifactCreator = Annotated[
    User,
    Depends(require_permissions("run:read", "artifact:create")),
]


def to_artifact_response(artifact: Artifact) -> ArtifactResponse:
    return ArtifactResponse(
        id=artifact.id,
        workspace_id=artifact.workspace_id,
        relative_path=artifact.relative_path,
        display_name=artifact.display_name,
        kind=artifact.kind,
        media_type=artifact.media_type,
        size_bytes=artifact.size_bytes,
        sha256=artifact.sha256,
        created_by=artifact.created_by,
        source_step_id=artifact.source_step_id,
        created_at=artifact.created_at,
    )


def _workspace_http_error(exc: Exception) -> HTTPException:
    if isinstance(
        exc,
        (RunNotFoundError, WorkspaceNotFoundError, WorkspaceFileNotFoundError),
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, RunAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    if isinstance(
        exc,
        (
            UnsafeWorkspacePathError,
            WorkspaceEncodingError,
            WorkspaceFileTypeError,
            WorkspaceFileTooLargeError,
            WorkspaceQuotaExceededError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": getattr(exc, "code", "WORKSPACE_ERROR"),
                "message": str(exc),
            },
        )
    if isinstance(exc, WorkspaceError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": exc.code,
                "message": str(exc),
            },
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Workspace operation failed",
    )


@router.get(
    "/api/runs/{run_id}/workspace",
    response_model=WorkspaceResponse,
)
async def workspace_show(
    run_id: UUID,
    principal: WorkspaceReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceResponse:
    try:
        await get_run(session, run_id, principal=principal)
        workspace = await get_workspace(session, run_id)
        used_bytes = workspace_storage.total_bytes(workspace.storage_key)
    except Exception as exc:
        raise _workspace_http_error(exc) from exc

    return WorkspaceResponse(
        id=workspace.id,
        run_id=workspace.run_id,
        status=workspace.status,
        quota_bytes=workspace.quota_bytes,
        max_file_bytes=workspace.max_file_bytes,
        used_bytes=used_bytes,
        created_at=workspace.created_at,
    )


@router.get(
    "/api/runs/{run_id}/workspace/files",
    response_model=list[WorkspaceEntryResponse],
)
async def workspace_files(
    run_id: UUID,
    principal: WorkspaceReader,
    session: Annotated[AsyncSession, Depends(get_db)],
    path: Annotated[str, Query(min_length=1, max_length=1024)] = "working",
) -> list[WorkspaceEntryResponse]:
    try:
        await get_run(session, run_id, principal=principal)
        workspace = await get_workspace(session, run_id)
        entries = workspace_storage.list_entries(
            workspace.storage_key,
            path,
        )
    except Exception as exc:
        raise _workspace_http_error(exc) from exc
    return [WorkspaceEntryResponse.model_validate(item) for item in entries]


@router.get(
    "/api/runs/{run_id}/workspace/text",
    response_model=WorkspaceTextResponse,
)
async def workspace_read_text(
    run_id: UUID,
    path: Annotated[str, Query(min_length=1, max_length=1024)],
    principal: WorkspaceReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceTextResponse:
    try:
        await get_run(session, run_id, principal=principal)
        workspace = await get_workspace(session, run_id)
        content = workspace_storage.read_text(
            workspace.storage_key,
            path,
            max_file_bytes=workspace.max_file_bytes,
        )
    except Exception as exc:
        raise _workspace_http_error(exc) from exc
    return WorkspaceTextResponse(path=path, content=content)


@router.put(
    "/api/runs/{run_id}/workspace/text",
    response_model=WorkspaceWriteResult,
)
async def workspace_write_text(
    run_id: UUID,
    payload: WorkspaceTextWriteRequest,
    principal: WorkspaceWriter,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceWriteResult:
    try:
        await get_run(session, run_id, principal=principal)
        workspace = await get_workspace(session, run_id)
        result = workspace_storage.write_text(
            workspace.storage_key,
            payload.path,
            payload.content,
            max_file_bytes=workspace.max_file_bytes,
            quota_bytes=workspace.quota_bytes,
            allowed_roots={"input", "working"},
        )
    except Exception as exc:
        raise _workspace_http_error(exc) from exc
    return WorkspaceWriteResult.model_validate(result)


@router.get(
    "/api/runs/{run_id}/artifacts",
    response_model=list[ArtifactResponse],
)
async def artifacts_index(
    run_id: UUID,
    principal: ArtifactReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ArtifactResponse]:
    try:
        await get_run(session, run_id, principal=principal)
        workspace = await get_workspace(session, run_id)
        artifacts = await list_artifacts(session, workspace.id)
    except Exception as exc:
        raise _workspace_http_error(exc) from exc
    return [to_artifact_response(item) for item in artifacts]


@router.post(
    "/api/runs/{run_id}/artifacts",
    response_model=ArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def artifacts_publish(
    run_id: UUID,
    payload: ArtifactPublishRequest,
    principal: ArtifactCreator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ArtifactResponse:
    try:
        await get_run(session, run_id, principal=principal)
        workspace = await get_workspace(session, run_id)
        artifact = await publish_artifact(
            session,
            workspace,
            source_path=payload.source_path,
            display_name=payload.display_name,
            kind=payload.kind,
            created_by="user",
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise _workspace_http_error(exc) from exc
    return to_artifact_response(artifact)


@router.get("/api/runs/{run_id}/artifacts/{artifact_id}/download")
async def artifact_download(
    run_id: UUID,
    artifact_id: UUID,
    principal: ArtifactReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    try:
        await get_run(session, run_id, principal=principal)
        workspace = await get_workspace(session, run_id)
        artifact = await get_artifact(session, workspace.id, artifact_id)
        path = workspace_storage.artifact_path(
            workspace.storage_key,
            artifact.relative_path,
        )
    except Exception as exc:
        raise _workspace_http_error(exc) from exc

    return FileResponse(
        path=path,
        media_type=artifact.media_type,
        filename=artifact.display_name,
    )
