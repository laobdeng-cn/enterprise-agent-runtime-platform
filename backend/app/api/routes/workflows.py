from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.db.session import get_db
from app.models.identity import User
from app.models.workflow import Workflow, WorkflowRun
from app.schemas.workflow import (
    WorkflowCheckpointResponse,
    WorkflowCreate,
    WorkflowNodeResponse,
    WorkflowNodeRunResponse,
    WorkflowResponse,
    WorkflowRunCreate,
    WorkflowRunResponse,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
)
from app.services.agents import AgentNotFoundError
from app.services.workflows import (
    WorkflowAccessDeniedError,
    WorkflowConflictError,
    WorkflowExecutionError,
    WorkflowNotFoundError,
    WorkflowRunNotFoundError,
    WorkflowValidationError,
    cancel_workflow_run,
    create_workflow,
    create_workflow_run,
    create_workflow_version,
    execute_workflow_run,
    get_workflow,
    get_workflow_run,
    list_workflow_runs,
    list_workflows,
)

router = APIRouter(tags=["workflows"])

WorkflowReader = Annotated[
    User,
    Depends(require_permissions("workflow:read")),
]
WorkflowManager = Annotated[
    User,
    Depends(require_permissions("workflow:manage")),
]
WorkflowExecutor = Annotated[
    User,
    Depends(require_permissions("workflow:execute")),
]


def to_workflow_response(workflow: Workflow) -> WorkflowResponse:
    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        status=workflow.status,
        active_version_id=workflow.active_version_id,
        versions=[
            WorkflowVersionResponse(
                id=version.id,
                version=version.version,
                input_schema=dict(version.input_schema),
                output_schema=dict(version.output_schema),
                concurrency_limit=version.concurrency_limit,
                nodes=[
                    WorkflowNodeResponse(
                        id=node.id,
                        node_key=node.node_key,
                        name=node.name,
                        role=node.role,
                        agent_id=node.agent_id,
                        depends_on=list(node.depends_on),
                        condition=dict(node.condition),
                        instructions=node.instructions,
                        timeout_seconds=node.timeout_seconds,
                        max_attempts=node.max_attempts,
                        position=node.position,
                    )
                    for node in version.nodes
                ],
            )
            for version in workflow.versions
        ],
    )


def to_run_response(run: WorkflowRun) -> WorkflowRunResponse:
    return WorkflowRunResponse(
        id=run.id,
        workflow_id=run.workflow_id,
        workflow_version_id=run.workflow_version_id,
        created_by_user_id=run.created_by_user_id,
        status=run.status,
        input_data=dict(run.input_data),
        permission_snapshot=list(run.permission_snapshot),
        result_data=run.result_data,
        error_data=run.error_data,
        state_version=run.state_version,
        cancel_requested=run.cancel_requested,
        created_at=run.created_at,
        started_at=run.started_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
        node_runs=[
            WorkflowNodeRunResponse(
                id=item.id,
                workflow_node_id=item.workflow_node_id,
                node_key=item.node_key,
                role=item.role,
                position=item.position,
                status=item.status,
                attempt=item.attempt,
                agent_run_id=item.agent_run_id,
                input_data=dict(item.input_data),
                output_data=item.output_data,
                error_data=item.error_data,
                started_at=item.started_at,
                completed_at=item.completed_at,
            )
            for item in run.node_runs
        ],
        checkpoints=[
            WorkflowCheckpointResponse(
                id=item.id,
                sequence=item.sequence,
                state=item.state,
                kind=item.kind,
                payload=dict(item.payload),
                created_at=item.created_at,
            )
            for item in run.checkpoints
        ],
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(
        exc,
        (WorkflowNotFoundError, WorkflowRunNotFoundError, AgentNotFoundError),
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, WorkflowAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    if isinstance(exc, WorkflowConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if isinstance(exc, (WorkflowValidationError, WorkflowExecutionError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Workflow operation failed",
    )


@router.get("/api/workflows", response_model=list[WorkflowResponse])
async def workflows_index(
    _: WorkflowReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[WorkflowResponse]:
    return [
        to_workflow_response(item)
        for item in await list_workflows(session)
    ]


@router.post(
    "/api/workflows",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def workflows_create(
    payload: WorkflowCreate,
    principal: WorkflowManager,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowResponse:
    try:
        workflow = await create_workflow(
            session,
            principal,
            payload,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_workflow_response(workflow)


@router.get(
    "/api/workflows/{workflow_id}",
    response_model=WorkflowResponse,
)
async def workflows_show(
    workflow_id: UUID,
    _: WorkflowReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowResponse:
    try:
        workflow = await get_workflow(session, workflow_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_workflow_response(workflow)


@router.post(
    "/api/workflows/{workflow_id}/versions",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def workflow_versions_create(
    workflow_id: UUID,
    payload: WorkflowVersionCreate,
    principal: WorkflowManager,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowResponse:
    try:
        workflow = await create_workflow_version(
            session,
            principal,
            workflow_id,
            payload,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_workflow_response(workflow)


@router.get(
    "/api/workflow-runs",
    response_model=list[WorkflowRunResponse],
)
async def workflow_runs_index(
    principal: WorkflowReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[WorkflowRunResponse]:
    return [
        to_run_response(item)
        for item in await list_workflow_runs(session, principal)
    ]


@router.post(
    "/api/workflow-runs",
    response_model=WorkflowRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def workflow_runs_create(
    payload: WorkflowRunCreate,
    principal: WorkflowExecutor,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowRunResponse:
    try:
        run = await create_workflow_run(
            session,
            principal,
            payload,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_run_response(run)


@router.get(
    "/api/workflow-runs/{run_id}",
    response_model=WorkflowRunResponse,
)
async def workflow_runs_show(
    run_id: UUID,
    principal: WorkflowReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowRunResponse:
    try:
        run = await get_workflow_run(
            session,
            run_id,
            principal=principal,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_run_response(run)


@router.post(
    "/api/workflow-runs/{run_id}/start",
    response_model=WorkflowRunResponse,
)
async def workflow_runs_start(
    run_id: UUID,
    principal: WorkflowExecutor,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowRunResponse:
    try:
        run = await execute_workflow_run(
            session,
            run_id,
            principal=principal,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_run_response(run)


@router.post(
    "/api/workflow-runs/{run_id}/resume",
    response_model=WorkflowRunResponse,
)
async def workflow_runs_resume(
    run_id: UUID,
    principal: WorkflowExecutor,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowRunResponse:
    try:
        run = await execute_workflow_run(
            session,
            run_id,
            principal=principal,
            resume=True,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_run_response(run)


@router.post(
    "/api/workflow-runs/{run_id}/cancel",
    response_model=WorkflowRunResponse,
)
async def workflow_runs_cancel(
    run_id: UUID,
    principal: WorkflowExecutor,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowRunResponse:
    try:
        run = await cancel_workflow_run(
            session,
            run_id,
            principal=principal,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_run_response(run)
