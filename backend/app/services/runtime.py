import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.harness.contracts import HarnessResult, MemoryContextItem
from app.agents.harness.errors import ProviderError
from app.agents.harness.runner import AgentHarness
from app.core.config import settings
from app.models.agent import AgentVersion
from app.models.identity import User
from app.models.runtime import AgentRun, RunCheckpoint, RunEvent, RunStep, ToolCall
from app.models.skill import SkillVersion
from app.runtime.retry import RuntimeRetryPolicy
from app.runtime.state_machine import (
    InvalidRunTransitionError,
    RunState,
    ensure_transition,
    is_terminal,
    parse_run_state,
)
from app.schemas.runtime import RunCreate
from app.services.agents import AgentHasNoActiveVersionError, get_agent
from app.services.auth import get_user_by_id, permission_codes
from app.services.memory import memory_retriever
from app.services.workspaces import create_workspace
from app.skills.contracts import SkillExecutionContext


class RunNotFoundError(LookupError):
    pass


class RunAccessDeniedError(PermissionError):
    pass


class RunExecutionError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _has_admin_access(principal: User) -> bool:
    return "admin:manage" in permission_codes(principal)


def _assert_access(run: AgentRun, principal: User) -> None:
    if run.created_by_user_id != principal.id and not _has_admin_access(principal):
        raise RunAccessDeniedError(f"Run {run.id} is not accessible to this principal")


def _transition(run: AgentRun, target: RunState) -> None:
    current = parse_run_state(run.status)
    ensure_transition(current, target)
    run.status = target.value
    run.state_version += 1
    if target in {
        RunState.COMPLETED,
        RunState.FAILED,
        RunState.CANCELLED,
    }:
        run.completed_at = _now()


async def _next_sequence(
    session: AsyncSession,
    model: type[RunStep] | type[RunCheckpoint] | type[RunEvent],
    run_id: UUID,
) -> int:
    result = await session.execute(
        select(func.max(model.sequence)).where(model.run_id == run_id)
    )
    return int(result.scalar_one_or_none() or 0) + 1


async def _append_event(
    session: AsyncSession,
    run: AgentRun,
    event_type: str,
    data: dict[str, Any] | None = None,
) -> RunEvent:
    event = RunEvent(
        run_id=run.id,
        sequence=await _next_sequence(session, RunEvent, run.id),
        event_type=event_type,
        data=dict(data or {}),
    )
    session.add(event)
    return event


async def _append_checkpoint(
    session: AsyncSession,
    run: AgentRun,
    *,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> RunCheckpoint:
    checkpoint = RunCheckpoint(
        run_id=run.id,
        sequence=await _next_sequence(session, RunCheckpoint, run.id),
        state=run.status,
        kind=kind,
        payload=dict(payload or {}),
    )
    session.add(checkpoint)
    return checkpoint


async def _append_step(
    session: AsyncSession,
    run: AgentRun,
    *,
    step_type: str,
    status: str,
    attempt: int,
    input_data: dict[str, Any] | None = None,
) -> RunStep:
    step = RunStep(
        run_id=run.id,
        sequence=await _next_sequence(session, RunStep, run.id),
        step_type=step_type,
        status=status,
        attempt=attempt,
        input_data=dict(input_data or {}),
    )
    session.add(step)
    await session.flush()
    return step


def _run_options() -> tuple[Any, ...]:
    return (
        selectinload(AgentRun.steps),
        selectinload(AgentRun.tool_calls),
        selectinload(AgentRun.checkpoints),
        selectinload(AgentRun.events),
    )


async def get_run(
    session: AsyncSession,
    run_id: UUID,
    *,
    principal: User | None = None,
    for_update: bool = False,
) -> AgentRun:
    statement = (
        select(AgentRun)
        .options(*_run_options())
        .where(AgentRun.id == run_id)
        .execution_options(populate_existing=True)
    )
    if for_update:
        statement = statement.with_for_update()

    result = await session.execute(statement)
    run = result.scalar_one_or_none()
    if run is None:
        raise RunNotFoundError(f"Run {run_id} was not found")
    if principal is not None:
        _assert_access(run, principal)
    return run


async def list_runs(
    session: AsyncSession,
    principal: User,
) -> list[AgentRun]:
    statement = select(AgentRun).options(*_run_options()).order_by(
        AgentRun.created_at.desc()
    )
    if not _has_admin_access(principal):
        statement = statement.where(AgentRun.created_by_user_id == principal.id)
    result = await session.execute(statement)
    return list(result.scalars().unique().all())


async def create_run(
    session: AsyncSession,
    principal: User,
    payload: RunCreate,
) -> AgentRun:
    agent = await get_agent(session, payload.agent_id)
    version = agent.active_version
    if version is None:
        raise AgentHasNoActiveVersionError(
            f"Agent {agent.id} has no active version"
        )

    permissions = sorted(permission_codes(principal))
    run = AgentRun(
        agent_id=agent.id,
        agent_version_id=version.id,
        created_by_user_id=principal.id,
        status=RunState.PENDING.value,
        input_text=payload.input,
        additional_context=list(payload.additional_context),
        permission_snapshot=permissions,
        max_attempts=payload.max_attempts,
    )
    session.add(run)
    await session.flush()
    await create_workspace(session, run.id)

    input_step = await _append_step(
        session,
        run,
        step_type="INPUT",
        status="COMPLETED",
        attempt=0,
        input_data={
            "input": payload.input,
            "additional_context_count": len(payload.additional_context),
        },
    )
    input_step.output_data = {
        "agent_id": str(agent.id),
        "agent_version_id": str(version.id),
    }
    input_step.completed_at = _now()

    await _append_checkpoint(
        session,
        run,
        kind="run_created",
        payload={
            "agent_version_id": str(version.id),
            "input": payload.input,
            "additional_context": list(payload.additional_context),
        },
    )
    await _append_event(
        session,
        run,
        "run.created",
        {
            "status": run.status,
            "agent_id": str(agent.id),
            "agent_version_id": str(version.id),
        },
    )
    await session.commit()
    return await get_run(session, run.id, principal=principal)


async def _load_agent_version(
    session: AsyncSession,
    version_id: UUID,
) -> AgentVersion:
    result = await session.execute(
        select(AgentVersion)
        .options(
            selectinload(AgentVersion.bound_skill_versions).selectinload(
                SkillVersion.skill
            )
        )
        .where(AgentVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise RunExecutionError(
            f"AgentVersion {version_id} referenced by Run no longer exists"
        )
    return version


def _normalize_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ProviderError):
        return {
            "code": exc.code,
            "retryable": exc.retryable,
            "message": str(exc),
            "type": exc.__class__.__name__,
        }
    return {
        "code": "RUNTIME_EXECUTION_ERROR",
        "retryable": bool(getattr(exc, "retryable", False)),
        "message": f"Runtime execution failed with {exc.__class__.__name__}",
        "type": exc.__class__.__name__,
    }


async def _persist_tool_calls(
    session: AsyncSession,
    run: AgentRun,
    step: RunStep,
    result: HarnessResult,
) -> None:
    for raw in result.tool_results:
        metadata_raw = raw.get("metadata")
        metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
        skill_version_raw = metadata.get("skill_version_id")
        skill_version_id: UUID | None = None
        if skill_version_raw:
            try:
                skill_version_id = UUID(str(skill_version_raw))
            except ValueError:
                skill_version_id = None

        error_raw = raw.get("error")
        error_data = error_raw if isinstance(error_raw, dict) else None
        output = raw.get("output")
        result_data = {"output": output} if raw.get("ok") else None
        arguments_raw = raw.get("arguments")
        arguments = arguments_raw if isinstance(arguments_raw, dict) else {}

        tool_call = ToolCall(
            run_id=run.id,
            step_id=step.id,
            skill_version_id=skill_version_id,
            provider_call_id=str(raw.get("call_id") or ""),
            skill_name=str(raw.get("skill_name") or ""),
            arguments=arguments,
            result_data=result_data,
            error_data=error_data,
            status="SUCCEEDED" if raw.get("ok") else "FAILED",
            attempts=int(raw.get("attempts") or 1),
            duration_ms=float(raw.get("duration_ms") or 0.0),
        )
        session.add(tool_call)


async def _finalize_success(
    session: AsyncSession,
    run: AgentRun,
    result: HarnessResult,
    *,
    persist_tool_calls: bool,
    model_step: RunStep | None = None,
) -> None:
    if model_step is not None:
        model_step.status = "COMPLETED"
        model_step.output_data = result.model_dump(mode="json")
        model_step.completed_at = _now()
        if persist_tool_calls:
            await _persist_tool_calls(session, run, model_step, result)

    final_step = await _append_step(
        session,
        run,
        step_type="FINAL",
        status="COMPLETED",
        attempt=run.attempt,
        input_data={"source": "harness_result"},
    )
    final_step.output_data = {
        "content": result.content,
        "provider": result.provider,
        "model": result.model,
        "usage": result.usage.model_dump(),
    }
    final_step.completed_at = _now()

    _transition(run, RunState.COMPLETED)
    run.result_data = result.model_dump(mode="json")
    run.error_data = None
    run.pause_requested = False

    await _append_checkpoint(
        session,
        run,
        kind="completed",
        payload={"result": result.model_dump(mode="json")},
    )
    await _append_event(
        session,
        run,
        "run.completed",
        {
            "status": run.status,
            "attempt": run.attempt,
            "tool_calls": len(result.tool_results),
        },
    )
    await session.commit()


async def _latest_checkpoint(
    session: AsyncSession,
    run_id: UUID,
) -> RunCheckpoint | None:
    result = await session.execute(
        select(RunCheckpoint)
        .where(RunCheckpoint.run_id == run_id)
        .order_by(RunCheckpoint.sequence.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def execute_run(
    session: AsyncSession,
    harness: AgentHarness,
    run_id: UUID,
    *,
    principal: User,
    resume: bool = False,
) -> AgentRun:
    run = await get_run(
        session,
        run_id,
        principal=principal,
        for_update=True,
    )
    state = parse_run_state(run.status)

    if resume:
        if state != RunState.PAUSED:
            raise InvalidRunTransitionError(
                f"Run {run.id} is {run.status}; only PAUSED Runs can resume"
            )
        checkpoint = await _latest_checkpoint(session, run.id)
        if (
            checkpoint is not None
            and checkpoint.kind == "post_harness_result"
            and isinstance(checkpoint.payload.get("pending_result"), dict)
        ):
            _transition(run, RunState.RUNNING)
            run.pause_requested = False
            await _append_event(
                session,
                run,
                "run.resumed",
                {"from_checkpoint": checkpoint.sequence},
            )
            result = HarnessResult.model_validate(
                checkpoint.payload["pending_result"]
            )
            await _finalize_success(
                session,
                run,
                result,
                persist_tool_calls=False,
            )
            return await get_run(session, run.id, principal=principal)
    elif state != RunState.PENDING:
        raise InvalidRunTransitionError(
            f"Run {run.id} is {run.status}; only PENDING Runs can start"
        )

    retry_policy = RuntimeRetryPolicy(max_attempts=run.max_attempts)
    paused_execution_allowed = resume

    while True:
        run = await get_run(
            session,
            run.id,
            principal=principal,
            for_update=True,
        )
        state = parse_run_state(run.status)

        if state == RunState.CANCELLED:
            await session.commit()
            return await get_run(session, run.id, principal=principal)

        if state == RunState.PAUSED and not paused_execution_allowed:
            await session.commit()
            return await get_run(session, run.id, principal=principal)

        if state not in {
            RunState.PENDING,
            RunState.PAUSED,
            RunState.RETRYING,
        }:
            raise InvalidRunTransitionError(
                f"Run {run.id} cannot execute from {run.status}"
            )

        _transition(run, RunState.RUNNING)
        paused_execution_allowed = False
        run.attempt += 1
        run.pause_requested = False
        if run.started_at is None:
            run.started_at = _now()

        model_step = await _append_step(
            session,
            run,
            step_type="MODEL_CALL",
            status="RUNNING",
            attempt=run.attempt,
            input_data={
                "agent_version_id": str(run.agent_version_id),
                "attempt": run.attempt,
            },
        )
        await _append_checkpoint(
            session,
            run,
            kind="before_harness",
            payload={
                "attempt": run.attempt,
                "model_step_id": str(model_step.id),
            },
        )
        await _append_event(
            session,
            run,
            "run.running",
            {
                "attempt": run.attempt,
                "state_version": run.state_version,
            },
        )
        await session.commit()

        version = await _load_agent_version(session, run.agent_version_id)
        execution_principal = await get_user_by_id(
            session,
            run.created_by_user_id,
        )
        if execution_principal is None or not execution_principal.is_active:
            error = {
                "code": "EXECUTION_PRINCIPAL_UNAVAILABLE",
                "retryable": False,
                "message": "Run creator is unavailable or inactive",
            }
            run = await get_run(session, run.id, for_update=True)
            persisted_principal_step = await session.get(RunStep, model_step.id)
            if persisted_principal_step is not None:
                persisted_principal_step.status = "FAILED"
                persisted_principal_step.error_data = error
                persisted_principal_step.completed_at = _now()
            _transition(run, RunState.FAILED)
            run.error_data = error
            await _append_checkpoint(session, run, kind="failed", payload={"error": error})
            await _append_event(session, run, "run.failed", error)
            await session.commit()
            return await get_run(session, run.id, principal=principal)

        try:
            ranked_memories = await memory_retriever.retrieve_for_run(
                session,
                run=run,
                principal_id=execution_principal.id,
                query=run.input_text,
                limit=settings.memory_context_limit,
            )
            relevant_memory = [
                MemoryContextItem(
                    id=item.memory.id,
                    memory_type=item.memory.memory_type,
                    scope=item.memory.scope,
                    content=item.memory.content,
                    score=item.score,
                    importance=item.memory.importance,
                    source=item.memory.source,
                )
                for item in ranked_memories
            ]

            persisted_memory_step = await session.get(
                RunStep,
                model_step.id,
            )
            if persisted_memory_step is not None:
                persisted_memory_step.input_data = {
                    **persisted_memory_step.input_data,
                    "memory_ids": [
                        str(item.id)
                        for item in relevant_memory
                    ],
                    "memory_count": len(relevant_memory),
                }
            await session.commit()

            result = await harness.run(
                agent_id=run.agent_id,
                version=version,
                user_input=run.input_text,
                additional_context=list(run.additional_context),
                granted_permissions=permission_codes(execution_principal),
                skill_context=SkillExecutionContext(
                    run_id=run.id,
                    principal_id=execution_principal.id,
                ),
                relevant_memory=relevant_memory,
            )
        except Exception as exc:
            error = _normalize_error(exc)
            run = await get_run(session, run.id, for_update=True)
            persisted_step = await session.get(RunStep, model_step.id)
            if persisted_step is not None:
                persisted_step.status = "FAILED"
                persisted_step.error_data = error
                persisted_step.completed_at = _now()

            if parse_run_state(run.status) == RunState.CANCELLED:
                await session.commit()
                return await get_run(session, run.id, principal=principal)

            retryable = bool(error.get("retryable"))
            if retry_policy.should_retry(
                attempt=run.attempt,
                retryable=retryable,
            ):
                _transition(run, RunState.RETRYING)
                run.error_data = error
                await _append_checkpoint(
                    session,
                    run,
                    kind="retrying",
                    payload={
                        "attempt": run.attempt,
                        "error": error,
                    },
                )
                await _append_event(
                    session,
                    run,
                    "run.retrying",
                    {
                        "attempt": run.attempt,
                        "next_attempt": run.attempt + 1,
                        "error": error,
                    },
                )
                await session.commit()
                await asyncio.sleep(
                    retry_policy.delay_seconds(attempt=run.attempt)
                )
                continue

            _transition(run, RunState.FAILED)
            run.error_data = error
            await _append_checkpoint(
                session,
                run,
                kind="failed",
                payload={"error": error},
            )
            await _append_event(session, run, "run.failed", error)
            await session.commit()
            return await get_run(session, run.id, principal=principal)

        run = await get_run(session, run.id, for_update=True)
        persisted_step = await session.get(RunStep, model_step.id)
        if persisted_step is not None:
            persisted_step.status = "COMPLETED"
            persisted_step.output_data = result.model_dump(mode="json")
            persisted_step.completed_at = _now()
            await _persist_tool_calls(session, run, persisted_step, result)

        state = parse_run_state(run.status)
        if state == RunState.CANCELLED or run.cancel_requested:
            if state != RunState.CANCELLED:
                _transition(run, RunState.CANCELLED)
            await _append_checkpoint(
                session,
                run,
                kind="cancelled_after_execution",
                payload={"discarded_result": result.model_dump(mode="json")},
            )
            await _append_event(
                session,
                run,
                "run.cancelled",
                {"result_discarded": True},
            )
            await session.commit()
            return await get_run(session, run.id, principal=principal)

        if state == RunState.PAUSED or run.pause_requested:
            if state != RunState.PAUSED:
                _transition(run, RunState.PAUSED)
            run.pause_requested = False
            await _append_checkpoint(
                session,
                run,
                kind="post_harness_result",
                payload={"pending_result": result.model_dump(mode="json")},
            )
            await _append_event(
                session,
                run,
                "run.paused",
                {"checkpointed_result": True},
            )
            await session.commit()
            return await get_run(session, run.id, principal=principal)

        await _finalize_success(
            session,
            run,
            result,
            persist_tool_calls=False,
        )
        return await get_run(session, run.id, principal=principal)


async def pause_run(
    session: AsyncSession,
    run_id: UUID,
    *,
    principal: User,
) -> AgentRun:
    run = await get_run(session, run_id, principal=principal, for_update=True)
    state = parse_run_state(run.status)
    if state not in {RunState.RUNNING, RunState.RETRYING}:
        raise InvalidRunTransitionError(
            f"Run {run.id} cannot pause from {run.status}"
        )

    _transition(run, RunState.PAUSED)
    run.pause_requested = True
    await _append_checkpoint(
        session,
        run,
        kind="pause_requested",
        payload={"requested_by": str(principal.id)},
    )
    await _append_event(
        session,
        run,
        "run.pause_requested",
        {"requested_by": str(principal.id)},
    )
    await session.commit()
    return await get_run(session, run.id, principal=principal)


async def cancel_run(
    session: AsyncSession,
    run_id: UUID,
    *,
    principal: User,
) -> AgentRun:
    run = await get_run(session, run_id, principal=principal, for_update=True)
    state = parse_run_state(run.status)
    if is_terminal(state):
        raise InvalidRunTransitionError(
            f"Run {run.id} is already terminal: {run.status}"
        )

    _transition(run, RunState.CANCELLED)
    run.cancel_requested = True
    await _append_checkpoint(
        session,
        run,
        kind="cancelled",
        payload={"requested_by": str(principal.id)},
    )
    await _append_event(
        session,
        run,
        "run.cancelled",
        {"requested_by": str(principal.id)},
    )
    await session.commit()
    return await get_run(session, run.id, principal=principal)


async def list_events_since(
    session: AsyncSession,
    run_id: UUID,
    *,
    principal: User,
    after_sequence: int,
) -> list[RunEvent]:
    run = await get_run(session, run_id, principal=principal)
    result = await session.execute(
        select(RunEvent)
        .where(
            RunEvent.run_id == run.id,
            RunEvent.sequence > after_sequence,
        )
        .order_by(RunEvent.sequence)
    )
    return list(result.scalars().all())


async def recover_incomplete_runs(session: AsyncSession) -> int:
    result = await session.execute(
        select(AgentRun).where(
            AgentRun.status.in_(
                [RunState.RUNNING.value, RunState.RETRYING.value]
            )
        )
    )
    runs = list(result.scalars().all())
    recovered = 0

    for run in runs:
        state = parse_run_state(run.status)
        ensure_transition(state, RunState.PAUSED)
        run.status = RunState.PAUSED.value
        run.state_version += 1
        run.pause_requested = False

        step_result = await session.execute(
            select(RunStep).where(
                RunStep.run_id == run.id,
                RunStep.status == "RUNNING",
            )
        )
        for step in step_result.scalars().all():
            step.status = "INTERRUPTED"
            step.error_data = {
                "code": "RUNTIME_RESTART",
                "retryable": True,
                "message": "Execution was interrupted by runtime restart",
            }
            step.completed_at = _now()

        await _append_checkpoint(
            session,
            run,
            kind="runtime_recovered",
            payload={
                "previous_state": state.value,
                "resume_required": True,
            },
        )
        await _append_event(
            session,
            run,
            "run.recovered",
            {
                "previous_state": state.value,
                "status": RunState.PAUSED.value,
            },
        )
        recovered += 1

    if recovered:
        await session.commit()
    return recovered
