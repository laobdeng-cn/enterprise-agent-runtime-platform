from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.db.session import get_db
from app.models.identity import User
from app.sandbox.contracts import (
    SandboxExecuteRequest,
    SandboxExecutionResponse,
)
from app.sandbox.errors import (
    SandboxCodeTooLargeError,
    SandboxExecutionInfrastructureError,
    SandboxImageError,
    SandboxOutputPolicyError,
    SandboxUnavailableError,
)
from app.services.runtime import (
    RunAccessDeniedError,
    RunNotFoundError,
    get_run,
)
from app.services.sandbox import (
    sandbox_execution_service,
    sandbox_manager,
)
from app.workspace.errors import WorkspaceError

router = APIRouter(tags=["sandbox"])

SandboxRunner = Annotated[
    User,
    Depends(
        require_permissions(
            "run:read",
            "sandbox:execute",
            "workspace:read",
            "artifact:create",
        )
    ),
]


def _sandbox_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, RunNotFoundError):
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
            SandboxCodeTooLargeError,
            SandboxOutputPolicyError,
            WorkspaceError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": getattr(exc, "code", "SANDBOX_POLICY"),
                "message": str(exc),
            },
        )
    if isinstance(
        exc,
        (
            SandboxUnavailableError,
            SandboxImageError,
            SandboxExecutionInfrastructureError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": getattr(exc, "code", "SANDBOX_UNAVAILABLE"),
                "message": str(exc),
            },
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Sandbox operation failed",
    )


@router.get("/api/sandbox/health")
async def sandbox_health(_: SandboxRunner) -> dict[str, object]:
    available = await sandbox_manager.ping()
    return {
        "available": available,
        "image": sandbox_manager.image,
        "security": sandbox_manager.container_security_config(),
    }


@router.post(
    "/api/runs/{run_id}/sandbox/python",
    response_model=SandboxExecutionResponse,
)
async def execute_python(
    run_id: UUID,
    payload: SandboxExecuteRequest,
    principal: SandboxRunner,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SandboxExecutionResponse:
    try:
        await get_run(session, run_id, principal=principal)
        return await sandbox_execution_service.execute_python(
            run_id,
            payload.code,
            publish_outputs=payload.publish_artifacts,
            created_by="user",
        )
    except Exception as exc:
        raise _sandbox_http_error(exc) from exc
