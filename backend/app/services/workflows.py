import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import async_session_maker
from app.models.identity import User
from app.models.workflow import (
    Workflow,
    WorkflowCheckpoint,
    WorkflowNode,
    WorkflowNodeRun,
    WorkflowRun,
    WorkflowVersion,
)
from app.schemas.runtime import RunCreate
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowNodeDefinition,
    WorkflowRunCreate,
    WorkflowVersionCreate,
)
from app.services.agents import get_agent
from app.services.auth import get_user_by_id, permission_codes
from app.services.harness import agent_harness
from app.services.runtime import create_run, execute_run
from app.workflows.graph import (
    WorkflowGraphError,
    evaluate_condition,
    execution_waves,
)

ROLES = {"PLANNER", "EXECUTOR", "REVIEWER"}
NODE_TERMINAL = {
    "COMPLETED",
    "SKIPPED",
    "BLOCKED",
    "FAILED",
    "CANCELLED",
}


class WorkflowNotFoundError(LookupError):
    pass


class WorkflowRunNotFoundError(LookupError):
    pass


class WorkflowConflictError(ValueError):
    pass


class WorkflowValidationError(ValueError):
    pass


class WorkflowAccessDeniedError(PermissionError):
    pass


class WorkflowExecutionError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _workflow_options() -> tuple[Any, ...]:
    return (
        selectinload(Workflow.versions).selectinload(WorkflowVersion.nodes),
        selectinload(Workflow.active_version).selectinload(
            WorkflowVersion.nodes
        ),
    )


def _run_options() -> tuple[Any, ...]:
    return (
        selectinload(WorkflowRun.node_runs),
        selectinload(WorkflowRun.checkpoints),
    )


def _admin(principal: User) -> bool:
    return "admin:manage" in permission_codes(principal)


def _assert_run_access(run: WorkflowRun, principal: User) -> None:
    if run.created_by_user_id != principal.id and not _admin(principal):
        raise WorkflowAccessDeniedError(
            f"WorkflowRun {run.id} is not accessible to this principal"
        )


def _validate_schema(schema: dict[str, Any], label: str) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise WorkflowValidationError(
            f"Invalid {label} JSON Schema: {exc.message}"
        ) from exc


def _validate_roles(nodes: list[WorkflowNodeDefinition]) -> None:
    invalid = sorted({node.role for node in nodes} - ROLES)
    if invalid:
        raise WorkflowValidationError(
            "Unsupported workflow role(s): " + ", ".join(invalid)
        )


def _dependencies(
    nodes: list[WorkflowNodeDefinition],
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for node in nodes:
        if node.node_key in result:
            raise WorkflowValidationError(
                f"Duplicate workflow node key '{node.node_key}'"
            )
        result[node.node_key] = list(dict.fromkeys(node.depends_on))
    try:
        execution_waves(result)
    except WorkflowGraphError as exc:
        raise WorkflowValidationError(str(exc)) from exc
    return result


def _validate_conditions(
    nodes: list[WorkflowNodeDefinition],
    dependencies: dict[str, list[str]],
) -> None:
    keys = set(dependencies)
    for node in nodes:
        condition = node.condition
        if not condition:
            continue
        source = str(condition.get("source", "workflow_input"))
        if source == "node_output":
            source_node = str(condition.get("node", ""))
            if source_node not in keys:
                raise WorkflowValidationError(
                    f"Node '{node.node_key}' condition references unknown "
                    f"node '{source_node}'"
                )
            if source_node not in dependencies[node.node_key]:
                raise WorkflowValidationError(
                    f"Node '{node.node_key}' condition may reference only "
                    "a direct dependency"
                )
        try:
            evaluate_condition(
                condition,
                workflow_input={},
                node_outputs={},
            )
        except WorkflowGraphError as exc:
            if "requires 'node'" in str(exc):
                raise WorkflowValidationError(str(exc)) from exc
            if "Unsupported" in str(exc):
                raise WorkflowValidationError(str(exc)) from exc


async def _validate_definition(
    session: AsyncSession,
    *,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    nodes: list[WorkflowNodeDefinition],
) -> None:
    _validate_schema(input_schema, "workflow input")
    _validate_schema(output_schema, "workflow output")
    _validate_roles(nodes)
    dependencies = _dependencies(nodes)
    _validate_conditions(nodes, dependencies)

    for node in nodes:
        agent = await get_agent(session, node.agent_id)
        if agent.status != "active" or agent.active_version is None:
            raise WorkflowValidationError(
                f"Workflow node '{node.node_key}' references an inactive "
                "or unversioned Agent"
            )


async def list_workflows(session: AsyncSession) -> list[Workflow]:
    result = await session.execute(
        select(Workflow)
        .options(*_workflow_options())
        .order_by(Workflow.name)
    )
    return list(result.scalars().unique().all())


async def get_workflow(
    session: AsyncSession,
    workflow_id: UUID,
) -> Workflow:
    result = await session.execute(
        select(Workflow)
        .options(*_workflow_options())
        .where(Workflow.id == workflow_id)
        .execution_options(populate_existing=True)
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise WorkflowNotFoundError(
            f"Workflow {workflow_id} was not found"
        )
    return workflow


async def _add_version(
    session: AsyncSession,
    workflow: Workflow,
    *,
    principal: User,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    concurrency_limit: int,
    nodes: list[WorkflowNodeDefinition],
    version_number: int,
) -> WorkflowVersion:
    await _validate_definition(
        session,
        input_schema=input_schema,
        output_schema=output_schema,
        nodes=nodes,
    )
    version = WorkflowVersion(
        workflow_id=workflow.id,
        version=version_number,
        input_schema=dict(input_schema),
        output_schema=dict(output_schema),
        concurrency_limit=concurrency_limit,
        created_by_user_id=principal.id,
    )
    session.add(version)
    await session.flush()

    for position, definition in enumerate(nodes):
        agent = await get_agent(session, definition.agent_id)
        if agent.active_version is None:
            raise WorkflowValidationError(
                f"Workflow node '{definition.node_key}' has no "
                "active AgentVersion to pin"
            )
        session.add(
            WorkflowNode(
                workflow_version_id=version.id,
                node_key=definition.node_key,
                name=definition.name,
                role=definition.role,
                agent_id=definition.agent_id,
                agent_version_id=agent.active_version.id,
                depends_on=list(dict.fromkeys(definition.depends_on)),
                condition=dict(definition.condition),
                instructions=definition.instructions,
                timeout_seconds=definition.timeout_seconds,
                max_attempts=definition.max_attempts,
                position=position,
            )
        )
    await session.flush()
    workflow.active_version_id = version.id
    return version


async def create_workflow(
    session: AsyncSession,
    principal: User,
    payload: WorkflowCreate,
) -> Workflow:
    workflow = Workflow(
        name=payload.name.strip(),
        description=payload.description,
        status="active",
        created_by_user_id=principal.id,
    )
    session.add(workflow)
    try:
        await session.flush()
        await _add_version(
            session,
            workflow,
            principal=principal,
            input_schema=payload.input_schema,
            output_schema=payload.output_schema,
            concurrency_limit=payload.concurrency_limit,
            nodes=payload.nodes,
            version_number=1,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise WorkflowConflictError(
            f"Workflow name '{payload.name.strip()}' already exists"
        ) from exc
    except Exception:
        await session.rollback()
        raise
    return await get_workflow(session, workflow.id)


async def create_workflow_version(
    session: AsyncSession,
    principal: User,
    workflow_id: UUID,
    payload: WorkflowVersionCreate,
) -> Workflow:
    workflow = await get_workflow(session, workflow_id)
    result = await session.execute(
        select(func.max(WorkflowVersion.version)).where(
            WorkflowVersion.workflow_id == workflow.id
        )
    )
    next_version = int(result.scalar_one_or_none() or 0) + 1
    await _add_version(
        session,
        workflow,
        principal=principal,
        input_schema=payload.input_schema,
        output_schema=payload.output_schema,
        concurrency_limit=payload.concurrency_limit,
        nodes=payload.nodes,
        version_number=next_version,
    )
    await session.commit()
    return await get_workflow(session, workflow.id)


async def _next_checkpoint_sequence(
    session: AsyncSession,
    workflow_run_id: UUID,
) -> int:
    result = await session.execute(
        select(func.max(WorkflowCheckpoint.sequence)).where(
            WorkflowCheckpoint.workflow_run_id == workflow_run_id
        )
    )
    return int(result.scalar_one_or_none() or 0) + 1


async def _checkpoint(
    session: AsyncSession,
    run: WorkflowRun,
    *,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        WorkflowCheckpoint(
            workflow_run_id=run.id,
            sequence=await _next_checkpoint_sequence(session, run.id),
            state=run.status,
            kind=kind,
            payload=dict(payload or {}),
        )
    )


async def get_workflow_run(
    session: AsyncSession,
    run_id: UUID,
    *,
    principal: User | None = None,
) -> WorkflowRun:
    result = await session.execute(
        select(WorkflowRun)
        .options(*_run_options())
        .where(WorkflowRun.id == run_id)
        .execution_options(populate_existing=True)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise WorkflowRunNotFoundError(
            f"WorkflowRun {run_id} was not found"
        )
    if principal is not None:
        _assert_run_access(run, principal)
    return run


async def list_workflow_runs(
    session: AsyncSession,
    principal: User,
) -> list[WorkflowRun]:
    statement = (
        select(WorkflowRun)
        .options(*_run_options())
        .order_by(WorkflowRun.created_at.desc())
    )
    if not _admin(principal):
        statement = statement.where(
            WorkflowRun.created_by_user_id == principal.id
        )
    result = await session.execute(statement)
    return list(result.scalars().unique().all())


async def create_workflow_run(
    session: AsyncSession,
    principal: User,
    payload: WorkflowRunCreate,
) -> WorkflowRun:
    workflow = await get_workflow(session, payload.workflow_id)
    version = workflow.active_version
    if version is None:
        raise WorkflowValidationError(
            f"Workflow {workflow.id} has no active version"
        )

    validator = Draft202012Validator(version.input_schema)
    errors = sorted(
        validator.iter_errors(payload.input_data),
        key=lambda item: list(item.path),
    )
    if errors:
        raise WorkflowValidationError(
            "Workflow input validation failed: "
            + "; ".join(error.message for error in errors[:5])
        )

    run = WorkflowRun(
        workflow_id=workflow.id,
        workflow_version_id=version.id,
        created_by_user_id=principal.id,
        status="PENDING",
        input_data=dict(payload.input_data),
        permission_snapshot=sorted(permission_codes(principal)),
    )
    session.add(run)
    await session.flush()

    for node in version.nodes:
        session.add(
            WorkflowNodeRun(
                workflow_run_id=run.id,
                workflow_node_id=node.id,
                node_key=node.node_key,
                role=node.role,
                position=node.position,
                status="PENDING",
                input_data={},
            )
        )
    await _checkpoint(
        session,
        run,
        kind="workflow_created",
        payload={"workflow_version_id": str(version.id)},
    )
    await session.commit()
    return await get_workflow_run(
        session,
        run.id,
        principal=principal,
    )


async def _load_version(
    session: AsyncSession,
    version_id: UUID,
) -> WorkflowVersion:
    result = await session.execute(
        select(WorkflowVersion)
        .options(selectinload(WorkflowVersion.nodes))
        .where(WorkflowVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise WorkflowExecutionError(
            f"WorkflowVersion {version_id} no longer exists"
        )
    return version


async def _load_node(
    session: AsyncSession,
    node_id: UUID,
) -> WorkflowNode:
    result = await session.execute(
        select(WorkflowNode).where(WorkflowNode.id == node_id)
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise WorkflowExecutionError(
            f"WorkflowNode {node_id} no longer exists"
        )
    return node


def _node_outputs(run: WorkflowRun) -> dict[str, dict[str, Any]]:
    return {
        item.node_key: dict(item.output_data or {})
        for item in run.node_runs
        if item.status == "COMPLETED"
    }


def _build_node_prompt(
    *,
    run: WorkflowRun,
    node: WorkflowNode,
) -> tuple[str, dict[str, Any]]:
    outputs = _node_outputs(run)
    dependencies = {
        key: outputs.get(key)
        for key in node.depends_on
        if key in outputs
    }
    payload = {
        "workflow_input": dict(run.input_data),
        "node_key": node.node_key,
        "role": node.role,
        "instructions": node.instructions,
        "dependency_outputs": dependencies,
    }
    prompt = (
        f"You are executing the {node.role} role in a controlled workflow.\n"
        f"Node: {node.node_key} ({node.name})\n"
        "Follow the node instructions and use only the capabilities exposed "
        "by your Agent version. Do not invent new workflow nodes.\n"
        f"Node instructions:\n{node.instructions or 'Complete the assigned role.'}\n"
        "Workflow state:\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
    return prompt, payload


async def _persist_node_failure(
    node_run_id: UUID,
    *,
    error: dict[str, Any],
    terminal: bool,
) -> None:
    async with async_session_maker() as session:
        node_run = await session.get(WorkflowNodeRun, node_run_id)
        if node_run is None:
            return
        node_run.error_data = error
        node_run.status = "FAILED" if terminal else "PENDING"
        if terminal:
            node_run.completed_at = _now()
        await session.commit()


async def _execute_node(
    workflow_run_id: UUID,
    node_run_id: UUID,
    principal_id: UUID,
    semaphore: asyncio.Semaphore,
) -> None:
    async with semaphore:
        async with async_session_maker() as session:
            run = await get_workflow_run(session, workflow_run_id)
            node_run = await session.get(WorkflowNodeRun, node_run_id)
            if node_run is None or node_run.status in NODE_TERMINAL:
                return
            node = await _load_node(session, node_run.workflow_node_id)
            prompt, input_data = _build_node_prompt(run=run, node=node)
            node_run.status = "RUNNING"
            node_run.started_at = node_run.started_at or _now()
            node_run.input_data = input_data
            await session.commit()

        for attempt in range(1, node.max_attempts + 1):
            async with async_session_maker() as child_session:
                principal = await get_user_by_id(
                    child_session,
                    principal_id,
                )
                if principal is None or not principal.is_active:
                    await _persist_node_failure(
                        node_run_id,
                        error={
                            "code": "WORKFLOW_PRINCIPAL_UNAVAILABLE",
                            "retryable": False,
                        },
                        terminal=True,
                    )
                    return

                async with async_session_maker() as update_session:
                    current = await update_session.get(
                        WorkflowNodeRun,
                        node_run_id,
                    )
                    if current is None:
                        return
                    current.attempt = attempt
                    await update_session.commit()

                try:
                    child_run = await create_run(
                        child_session,
                        principal,
                        RunCreate(
                            agent_id=node.agent_id,
                            agent_version_id=node.agent_version_id,
                            input=prompt,
                            additional_context=[
                                f"workflow_run_id={workflow_run_id}",
                                f"workflow_node_key={node.node_key}",
                                f"workflow_role={node.role}",
                            ],
                            max_attempts=1,
                        ),
                    )
                    async with async_session_maker() as update_session:
                        current = await update_session.get(
                            WorkflowNodeRun,
                            node_run_id,
                        )
                        if current is not None:
                            current.agent_run_id = child_run.id
                            await update_session.commit()

                    async with asyncio.timeout(node.timeout_seconds):
                        result = await execute_run(
                            child_session,
                            agent_harness,
                            child_run.id,
                            principal=principal,
                        )
                except TimeoutError:
                    error = {
                        "code": "WORKFLOW_NODE_TIMEOUT",
                        "retryable": True,
                        "attempt": attempt,
                    }
                    if attempt < node.max_attempts:
                        await _persist_node_failure(
                            node_run_id,
                            error=error,
                            terminal=False,
                        )
                        continue
                    await _persist_node_failure(
                        node_run_id,
                        error=error,
                        terminal=True,
                    )
                    return
                except Exception as exc:
                    error = {
                        "code": "WORKFLOW_NODE_EXECUTION_ERROR",
                        "retryable": False,
                        "type": exc.__class__.__name__,
                    }
                    await _persist_node_failure(
                        node_run_id,
                        error=error,
                        terminal=True,
                    )
                    return

                if result.status == "COMPLETED":
                    async with async_session_maker() as update_session:
                        current = await update_session.get(
                            WorkflowNodeRun,
                            node_run_id,
                        )
                        if current is None:
                            return
                        current.status = "COMPLETED"
                        current.output_data = {
                            "content": (
                                result.result_data or {}
                            ).get("content"),
                            "agent_run_id": str(result.id),
                            "result": dict(result.result_data or {}),
                        }
                        current.error_data = None
                        current.completed_at = _now()
                        await update_session.commit()
                    return

                error = dict(
                    result.error_data
                    or {
                        "code": "WORKFLOW_CHILD_RUN_FAILED",
                        "retryable": False,
                    }
                )
                retryable = bool(error.get("retryable"))
                if retryable and attempt < node.max_attempts:
                    await _persist_node_failure(
                        node_run_id,
                        error=error,
                        terminal=False,
                    )
                    continue
                await _persist_node_failure(
                    node_run_id,
                    error=error,
                    terminal=True,
                )
                return


async def _mark_blocked_nodes(
    session: AsyncSession,
    run: WorkflowRun,
) -> None:
    for node_run in run.node_runs:
        if node_run.status == "PENDING":
            node_run.status = "BLOCKED"
            node_run.error_data = {
                "code": "UPSTREAM_NODE_FAILED",
                "retryable": False,
            }
            node_run.completed_at = _now()


async def execute_workflow_run(
    session: AsyncSession,
    run_id: UUID,
    *,
    principal: User,
    resume: bool = False,
) -> WorkflowRun:
    run = await get_workflow_run(
        session,
        run_id,
        principal=principal,
    )
    if resume:
        if run.status != "PAUSED":
            raise WorkflowExecutionError(
                f"WorkflowRun {run.id} is {run.status}; only PAUSED can resume"
            )
    elif run.status != "PENDING":
        raise WorkflowExecutionError(
            f"WorkflowRun {run.id} is {run.status}; only PENDING can start"
        )

    version = await _load_version(session, run.workflow_version_id)
    dependencies = {
        node.node_key: list(node.depends_on)
        for node in version.nodes
    }
    waves = execution_waves(dependencies)

    run.status = "RUNNING"
    run.state_version += 1
    run.cancel_requested = False
    run.started_at = run.started_at or _now()
    await _checkpoint(
        session,
        run,
        kind="workflow_started" if not resume else "workflow_resumed",
        payload={"waves": waves},
    )
    await session.commit()

    nodes_by_key = {node.node_key: node for node in version.nodes}
    semaphore = asyncio.Semaphore(version.concurrency_limit)

    for wave_index, wave in enumerate(waves, start=1):
        run = await get_workflow_run(
            session,
            run.id,
            principal=principal,
        )
        if run.cancel_requested:
            run.status = "CANCELLED"
            run.state_version += 1
            run.completed_at = _now()
            for item in run.node_runs:
                if item.status == "PENDING":
                    item.status = "CANCELLED"
                    item.completed_at = _now()
            await _checkpoint(
                session,
                run,
                kind="workflow_cancelled",
            )
            await session.commit()
            return await get_workflow_run(
                session,
                run.id,
                principal=principal,
            )

        current = {item.node_key: item for item in run.node_runs}
        outputs = _node_outputs(run)
        ready_ids: list[UUID] = []

        for key in wave:
            node_run = current[key]
            if node_run.status in {"COMPLETED", "SKIPPED"}:
                continue
            node = nodes_by_key[key]
            dependency_states = {
                dep: current[dep].status
                for dep in node.depends_on
            }
            if any(
                state in {"FAILED", "BLOCKED", "CANCELLED"}
                for state in dependency_states.values()
            ):
                node_run.status = "BLOCKED"
                node_run.error_data = {
                    "code": "UPSTREAM_NODE_FAILED",
                    "dependencies": dependency_states,
                }
                node_run.completed_at = _now()
                continue

            try:
                should_run = evaluate_condition(
                    dict(node.condition),
                    workflow_input=dict(run.input_data),
                    node_outputs=outputs,
                )
            except WorkflowGraphError as exc:
                node_run.status = "FAILED"
                node_run.error_data = {
                    "code": "WORKFLOW_CONDITION_ERROR",
                    "message": str(exc),
                    "retryable": False,
                }
                node_run.completed_at = _now()
                continue

            if not should_run:
                node_run.status = "SKIPPED"
                node_run.output_data = {"reason": "condition_false"}
                node_run.completed_at = _now()
                continue
            ready_ids.append(node_run.id)

        await session.commit()

        if ready_ids:
            await asyncio.gather(
                *[
                    _execute_node(
                        run.id,
                        node_run_id,
                        run.created_by_user_id,
                        semaphore,
                    )
                    for node_run_id in ready_ids
                ]
            )

        run = await get_workflow_run(
            session,
            run.id,
            principal=principal,
        )
        await _checkpoint(
            session,
            run,
            kind="wave_completed",
            payload={
                "wave": wave_index,
                "nodes": {
                    item.node_key: item.status
                    for item in run.node_runs
                },
            },
        )

        if any(item.status == "FAILED" for item in run.node_runs):
            await _mark_blocked_nodes(session, run)
            run.status = "FAILED"
            run.state_version += 1
            run.error_data = {
                "code": "WORKFLOW_NODE_FAILED",
                "failed_nodes": [
                    item.node_key
                    for item in run.node_runs
                    if item.status == "FAILED"
                ],
            }
            run.completed_at = _now()
            await _checkpoint(
                session,
                run,
                kind="workflow_failed",
                payload=dict(run.error_data),
            )
            await session.commit()
            return await get_workflow_run(
                session,
                run.id,
                principal=principal,
            )
        await session.commit()

    run = await get_workflow_run(
        session,
        run.id,
        principal=principal,
    )
    outputs = _node_outputs(run)
    reviewers = [
        item
        for item in run.node_runs
        if item.role == "REVIEWER" and item.status == "COMPLETED"
    ]
    reviewers.sort(key=lambda item: item.position)
    final_output = (
        dict(reviewers[-1].output_data or {})
        if reviewers
        else (
            dict(run.node_runs[-1].output_data or {})
            if run.node_runs
            else {}
        )
    )
    result_data = {
        "outputs": outputs,
        "final": final_output,
    }

    validator = Draft202012Validator(version.output_schema)
    errors = list(validator.iter_errors(result_data))
    if errors:
        run.status = "FAILED"
        run.error_data = {
            "code": "WORKFLOW_OUTPUT_SCHEMA_ERROR",
            "message": errors[0].message,
        }
    else:
        run.status = "COMPLETED"
        run.result_data = result_data
        run.error_data = None

    run.state_version += 1
    run.completed_at = _now()
    await _checkpoint(
        session,
        run,
        kind=(
            "workflow_completed"
            if run.status == "COMPLETED"
            else "workflow_failed"
        ),
        payload={"result": result_data},
    )
    await session.commit()
    return await get_workflow_run(
        session,
        run.id,
        principal=principal,
    )


async def cancel_workflow_run(
    session: AsyncSession,
    run_id: UUID,
    *,
    principal: User,
) -> WorkflowRun:
    run = await get_workflow_run(
        session,
        run_id,
        principal=principal,
    )
    if run.status in {"COMPLETED", "FAILED", "CANCELLED"}:
        return run
    run.cancel_requested = True
    if run.status in {"PENDING", "PAUSED"}:
        run.status = "CANCELLED"
        run.state_version += 1
        run.completed_at = _now()
        for item in run.node_runs:
            if item.status == "PENDING":
                item.status = "CANCELLED"
                item.completed_at = _now()
        await _checkpoint(
            session,
            run,
            kind="workflow_cancelled",
        )
    await session.commit()
    return await get_workflow_run(
        session,
        run.id,
        principal=principal,
    )


async def recover_incomplete_workflow_runs(
    session: AsyncSession,
) -> int:
    result = await session.execute(
        select(WorkflowRun)
        .options(*_run_options())
        .where(WorkflowRun.status == "RUNNING")
    )
    runs = list(result.scalars().unique().all())
    for run in runs:
        run.status = "PAUSED"
        run.state_version += 1
        for item in run.node_runs:
            if item.status == "RUNNING":
                item.status = "PENDING"
                item.error_data = {
                    "code": "WORKFLOW_PROCESS_RESTART",
                    "retryable": True,
                }
        await _checkpoint(
            session,
            run,
            kind="recovered_after_restart",
            payload={
                "node_statuses": {
                    item.node_key: item.status
                    for item in run.node_runs
                }
            },
        )
    if runs:
        await session.commit()
    return len(runs)
