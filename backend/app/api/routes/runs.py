import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.db.session import async_session_maker, get_db
from app.models.identity import User
from app.models.runtime import AgentRun
from app.runtime.state_machine import InvalidRunTransitionError, is_terminal
from app.schemas.runtime import (
    RunCheckpointResponse,
    RunCreate,
    RunResponse,
    RunStepResponse,
    ToolCallResponse,
)
from app.services.agents import AgentHasNoActiveVersionError, AgentNotFoundError
from app.services.harness import agent_harness
from app.services.runtime import (
    RunAccessDeniedError,
    RunNotFoundError,
    cancel_run,
    create_run,
    execute_run,
    get_run,
    list_events_since,
    list_runs,
    pause_run,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])

RunReader = Annotated[User, Depends(require_permissions("run:read"))]
RunCreator = Annotated[User, Depends(require_permissions("run:create"))]
RunEditor = Annotated[User, Depends(require_permissions("run:update"))]
RunCanceller = Annotated[User, Depends(require_permissions("run:cancel"))]


def to_run_response(run: AgentRun) -> RunResponse:
    return RunResponse(
        id=run.id,
        agent_id=run.agent_id,
        agent_version_id=run.agent_version_id,
        created_by_user_id=run.created_by_user_id,
        status=run.status,
        input=run.input_text,
        additional_context=list(run.additional_context),
        permission_snapshot=list(run.permission_snapshot),
        result_data=run.result_data,
        error_data=run.error_data,
        attempt=run.attempt,
        max_attempts=run.max_attempts,
        state_version=run.state_version,
        pause_requested=run.pause_requested,
        cancel_requested=run.cancel_requested,
        created_at=run.created_at,
        started_at=run.started_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
        steps=[
            RunStepResponse(
                id=step.id,
                sequence=step.sequence,
                step_type=step.step_type,
                status=step.status,
                attempt=step.attempt,
                input_data=dict(step.input_data),
                output_data=step.output_data,
                error_data=step.error_data,
                started_at=step.started_at,
                completed_at=step.completed_at,
            )
            for step in run.steps
        ],
        tool_calls=[
            ToolCallResponse(
                id=call.id,
                provider_call_id=call.provider_call_id,
                skill_name=call.skill_name,
                skill_version_id=call.skill_version_id,
                arguments=dict(call.arguments),
                result_data=call.result_data,
                error_data=call.error_data,
                status=call.status,
                attempts=call.attempts,
                duration_ms=call.duration_ms,
                created_at=call.created_at,
            )
            for call in run.tool_calls
        ],
        checkpoints=[
            RunCheckpointResponse(
                id=checkpoint.id,
                sequence=checkpoint.sequence,
                state=checkpoint.state,
                kind=checkpoint.kind,
                payload=dict(checkpoint.payload),
                created_at=checkpoint.created_at,
            )
            for checkpoint in run.checkpoints
        ],
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, RunNotFoundError | AgentNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, RunAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    if isinstance(exc, (InvalidRunTransitionError, AgentHasNoActiveVersionError)):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Runtime operation failed",
    )


@router.get("", response_model=list[RunResponse])
async def runs_index(
    principal: RunReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[RunResponse]:
    return [
        to_run_response(run)
        for run in await list_runs(session, principal)
    ]


@router.post(
    "",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def runs_create(
    payload: RunCreate,
    principal: RunCreator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RunResponse:
    try:
        run = await create_run(session, principal, payload)
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_run_response(run)


@router.get("/{run_id}", response_model=RunResponse)
async def runs_show(
    run_id: UUID,
    principal: RunReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RunResponse:
    try:
        run = await get_run(session, run_id, principal=principal)
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_run_response(run)


@router.post("/{run_id}/start", response_model=RunResponse)
async def runs_start(
    run_id: UUID,
    principal: RunEditor,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RunResponse:
    try:
        run = await execute_run(
            session,
            agent_harness,
            run_id,
            principal=principal,
            resume=False,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_run_response(run)


@router.post("/{run_id}/pause", response_model=RunResponse)
async def runs_pause(
    run_id: UUID,
    principal: RunEditor,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RunResponse:
    try:
        run = await pause_run(session, run_id, principal=principal)
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_run_response(run)


@router.post("/{run_id}/resume", response_model=RunResponse)
async def runs_resume(
    run_id: UUID,
    principal: RunEditor,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RunResponse:
    try:
        run = await execute_run(
            session,
            agent_harness,
            run_id,
            principal=principal,
            resume=True,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_run_response(run)


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def runs_cancel(
    run_id: UUID,
    principal: RunCanceller,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RunResponse:
    try:
        run = await cancel_run(session, run_id, principal=principal)
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_run_response(run)


@router.get("/{run_id}/events")
async def run_events(
    run_id: UUID,
    principal: RunReader,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    try:
        cursor = int(last_event_id or "0")
    except ValueError:
        cursor = 0

    async def stream() -> AsyncIterator[str]:
        nonlocal cursor
        while True:
            async with async_session_maker() as session:
                try:
                    run = await get_run(
                        session,
                        run_id,
                        principal=principal,
                    )
                    events = await list_events_since(
                        session,
                        run_id,
                        principal=principal,
                        after_sequence=cursor,
                    )
                except (RunNotFoundError, RunAccessDeniedError):
                    payload = json.dumps(
                        {"code": "RUN_STREAM_UNAVAILABLE"},
                        separators=(",", ":"),
                    )
                    yield f"event: error\ndata: {payload}\n\n"
                    return

                for event in events:
                    cursor = event.sequence
                    payload = json.dumps(
                        {
                            "sequence": event.sequence,
                            "type": event.event_type,
                            "data": event.data,
                            "created_at": event.created_at.isoformat(),
                        },
                        separators=(",", ":"),
                    )
                    yield (
                        f"id: {event.sequence}\n"
                        f"event: {event.event_type}\n"
                        f"data: {payload}\n\n"
                    )

                if is_terminal(run.status) and not events:
                    return

            yield ": keep-alive\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
