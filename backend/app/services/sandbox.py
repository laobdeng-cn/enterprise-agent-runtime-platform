import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from docker import DockerClient  # type: ignore[import-untyped]
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.runtime import RunEvent, RunStep
from app.sandbox.contracts import (
    SandboxArtifactResponse,
    SandboxExecutionResponse,
    SandboxLimits,
    SandboxStatus,
)
from app.sandbox.docker_runtime import DockerSandboxManager
from app.sandbox.errors import SandboxOutputPolicyError
from app.services.runtime import get_run
from app.services.workspaces import (
    get_workspace,
    publish_artifact,
    workspace_storage,
)
from app.workspace.errors import (
    WorkspaceError,
)
from app.workspace.storage import ARTIFACT_EXTENSIONS


def _now() -> datetime:
    return datetime.now(UTC)


async def _next_sequence(
    session: AsyncSession,
    model: type[RunStep] | type[RunEvent],
    run_id: UUID,
) -> int:
    result = await session.execute(
        select(func.max(model.sequence)).where(model.run_id == run_id)
    )
    return int(result.scalar_one_or_none() or 0) + 1


async def _latest_running_model_step(
    session: AsyncSession,
    run_id: UUID,
) -> UUID | None:
    result = await session.execute(
        select(RunStep.id)
        .where(
            RunStep.run_id == run_id,
            RunStep.step_type == "MODEL_CALL",
            RunStep.status == "RUNNING",
        )
        .order_by(RunStep.sequence.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _append_event(
    session: AsyncSession,
    run_id: UUID,
    event_type: str,
    data: dict[str, Any],
) -> None:
    session.add(
        RunEvent(
            run_id=run_id,
            sequence=await _next_sequence(session, RunEvent, run_id),
            event_type=event_type,
            data=data,
        )
    )


class SandboxExecutionService:
    def __init__(
        self,
        *,
        manager: DockerSandboxManager,
        session_factory: async_sessionmaker[AsyncSession],
        max_artifacts: int,
    ) -> None:
        self.manager = manager
        self.session_factory = session_factory
        self.max_artifacts = max_artifacts

    async def execute_python(
        self,
        run_id: UUID,
        code: str,
        *,
        publish_outputs: bool = True,
        created_by: str = "agent",
    ) -> SandboxExecutionResponse:
        execution_id = uuid.uuid4()

        async with self.session_factory() as session:
            run = await get_run(session, run_id, for_update=True)
            workspace = await get_workspace(session, run_id)
            parent_step_id = await _latest_running_model_step(session, run_id)
            step = RunStep(
                run_id=run_id,
                sequence=await _next_sequence(session, RunStep, run_id),
                step_type="SANDBOX_EXECUTION",
                status="RUNNING",
                attempt=run.attempt,
                parent_step_id=parent_step_id,
                input_data={
                    "execution_id": str(execution_id),
                    "language": "python",
                    "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
                    "code_bytes": len(code.encode("utf-8")),
                    "publish_outputs": publish_outputs,
                    "image": self.manager.image,
                    "security": self.manager.container_security_config(),
                },
            )
            session.add(step)
            await session.flush()
            await _append_event(
                session,
                run_id,
                "sandbox.started",
                {
                    "execution_id": str(execution_id),
                    "step_id": str(step.id),
                },
            )
            await session.commit()

            output_relative_path = (
                f"working/sandbox/{execution_id}/output"
            )
            output_dir = workspace_storage.prepare_directory(
                workspace.storage_key,
                output_relative_path,
                allowed_roots={"working"},
                mode=0o777,
            )
            input_dir = workspace_storage.resolve(
                workspace.storage_key,
                "input",
                allowed_roots={"input"},
                must_exist=True,
            )
            working_dir = workspace_storage.resolve(
                workspace.storage_key,
                "working",
                allowed_roots={"working"},
                must_exist=True,
            )

            try:
                raw = await self.manager.execute_python(
                    run_id=run_id,
                    execution_id=execution_id,
                    code=code,
                    input_dir=input_dir,
                    working_dir=working_dir,
                    output_dir=output_dir,
                    output_relative_path=output_relative_path,
                )
            except Exception as exc:
                await self._mark_infrastructure_failure(
                    session,
                    step.id,
                    run_id,
                    execution_id,
                    exc,
                )
                self._cleanup_output(
                    workspace.storage_key,
                    output_relative_path,
                )
                raise

            if raw.status != SandboxStatus.SUCCEEDED:
                self._cleanup_output(
                    workspace.storage_key,
                    output_relative_path,
                )
                response = SandboxExecutionResponse(
                    execution_id=raw.execution_id,
                    run_id=run_id,
                    status=raw.status,
                    exit_code=raw.exit_code,
                    stdout=raw.stdout,
                    stderr=raw.stderr,
                    duration_ms=raw.duration_ms,
                    timed_out=raw.timed_out,
                    stdout_truncated=raw.stdout_truncated,
                    stderr_truncated=raw.stderr_truncated,
                    artifacts=[],
                )
                await self._finish_step(
                    session,
                    step.id,
                    response,
                    succeeded=False,
                )
                await _append_event(
                    session,
                    run_id,
                    (
                        "sandbox.timed_out"
                        if raw.status == SandboxStatus.TIMED_OUT
                        else "sandbox.failed"
                    ),
                    {
                        "execution_id": str(execution_id),
                        "exit_code": raw.exit_code,
                        "timed_out": raw.timed_out,
                    },
                )
                await session.commit()
                return response

            try:
                files = self._validate_outputs(
                    workspace.storage_key,
                    output_relative_path,
                    max_file_bytes=workspace.max_file_bytes,
                    quota_bytes=workspace.quota_bytes,
                    publish_outputs=publish_outputs,
                )
            except Exception as exc:
                self._cleanup_output(
                    workspace.storage_key,
                    output_relative_path,
                )
                await self._mark_policy_failure(
                    session,
                    step.id,
                    run_id,
                    execution_id,
                    exc,
                )
                raise

            artifact_responses: list[SandboxArtifactResponse] = []
            if publish_outputs:
                for path in files:
                    source_path = workspace_storage.relative_path(
                        workspace.storage_key,
                        path,
                    )
                    artifact = await publish_artifact(
                        session,
                        workspace,
                        source_path=source_path,
                        display_name=path.name,
                        kind="sandbox_output",
                        created_by=created_by,
                        source_step_id=step.id,
                    )
                    artifact_responses.append(
                        SandboxArtifactResponse(
                            artifact_id=artifact.id,
                            path=artifact.relative_path,
                            display_name=artifact.display_name,
                            media_type=artifact.media_type,
                            size_bytes=artifact.size_bytes,
                            sha256=artifact.sha256,
                        )
                    )

            response = SandboxExecutionResponse(
                execution_id=raw.execution_id,
                run_id=run_id,
                status=raw.status,
                exit_code=raw.exit_code,
                stdout=raw.stdout,
                stderr=raw.stderr,
                duration_ms=raw.duration_ms,
                timed_out=raw.timed_out,
                stdout_truncated=raw.stdout_truncated,
                stderr_truncated=raw.stderr_truncated,
                artifacts=artifact_responses,
            )
            await self._finish_step(
                session,
                step.id,
                response,
                succeeded=True,
            )
            await _append_event(
                session,
                run_id,
                "sandbox.completed",
                {
                    "execution_id": str(execution_id),
                    "exit_code": raw.exit_code,
                    "artifacts": len(artifact_responses),
                },
            )
            await session.commit()
            return response

    def _validate_outputs(
        self,
        storage_key: str,
        output_relative_path: str,
        *,
        max_file_bytes: int,
        quota_bytes: int,
        publish_outputs: bool,
    ) -> list[Path]:
        try:
            files = workspace_storage.collect_files(
                storage_key,
                output_relative_path,
                allowed_roots={"working"},
            )
            if len(files) > self.max_artifacts:
                raise SandboxOutputPolicyError(
                    f"Sandbox produced {len(files)} files; limit is {self.max_artifacts}"
                )

            output_bytes = 0
            for path in files:
                size = path.stat().st_size
                if size > max_file_bytes:
                    raise SandboxOutputPolicyError(
                        f"Sandbox output '{path.name}' exceeds {max_file_bytes} bytes"
                    )
                if path.suffix.lower() not in ARTIFACT_EXTENSIONS:
                    raise SandboxOutputPolicyError(
                        f"Sandbox output type '{path.suffix or '<none>'}' is not allowed"
                    )
                output_bytes += size

            used_bytes = workspace_storage.total_bytes(storage_key)
            if used_bytes > quota_bytes:
                raise SandboxOutputPolicyError(
                    f"Workspace quota exceeded: {used_bytes} > {quota_bytes} bytes"
                )

            if publish_outputs and used_bytes + output_bytes > quota_bytes:
                raise SandboxOutputPolicyError(
                    "Publishing sandbox outputs would exceed the workspace quota"
                )
            return files
        except WorkspaceError as exc:
            raise SandboxOutputPolicyError(str(exc)) from exc

    async def _finish_step(
        self,
        session: AsyncSession,
        step_id: UUID,
        response: SandboxExecutionResponse,
        *,
        succeeded: bool,
    ) -> None:
        step = await session.get(RunStep, step_id)
        if step is None:
            return
        step.status = "COMPLETED" if succeeded else "FAILED"
        step.output_data = response.model_dump(mode="json")
        step.completed_at = _now()

    async def _mark_infrastructure_failure(
        self,
        session: AsyncSession,
        step_id: UUID,
        run_id: UUID,
        execution_id: UUID,
        exc: Exception,
    ) -> None:
        step = await session.get(RunStep, step_id)
        error = {
            "code": getattr(exc, "code", "SANDBOX_EXECUTION_INFRASTRUCTURE"),
            "message": str(exc),
            "type": exc.__class__.__name__,
        }
        if step is not None:
            step.status = "FAILED"
            step.error_data = error
            step.completed_at = _now()
        await _append_event(
            session,
            run_id,
            "sandbox.infrastructure_failed",
            {
                "execution_id": str(execution_id),
                "error": error,
            },
        )
        await session.commit()

    async def _mark_policy_failure(
        self,
        session: AsyncSession,
        step_id: UUID,
        run_id: UUID,
        execution_id: UUID,
        exc: Exception,
    ) -> None:
        step = await session.get(RunStep, step_id)
        error = {
            "code": getattr(exc, "code", "SANDBOX_OUTPUT_POLICY"),
            "message": str(exc),
            "type": exc.__class__.__name__,
        }
        if step is not None:
            step.status = "FAILED"
            step.error_data = error
            step.completed_at = _now()
        await _append_event(
            session,
            run_id,
            "sandbox.output_rejected",
            {
                "execution_id": str(execution_id),
                "error": error,
            },
        )
        await session.commit()

    @staticmethod
    def _cleanup_output(
        storage_key: str,
        output_relative_path: str,
    ) -> None:
        try:
            workspace_storage.remove_tree(
                storage_key,
                output_relative_path,
                allowed_roots={"working"},
            )
        except WorkspaceError:
            pass


sandbox_limits = SandboxLimits(
    cpu_limit=settings.sandbox_cpu_limit,
    memory_limit_mb=settings.sandbox_memory_limit_mb,
    timeout_seconds=settings.sandbox_timeout_seconds,
    pids_limit=settings.sandbox_pids_limit,
    tmpfs_mb=settings.sandbox_tmpfs_mb,
    max_output_bytes=settings.sandbox_max_output_bytes,
    max_code_bytes=settings.sandbox_max_code_bytes,
)

sandbox_manager = DockerSandboxManager(
    client=DockerClient(
        base_url=settings.docker_host,
        version=settings.docker_api_version,
        timeout=max(10, int(settings.sandbox_timeout_seconds) + 10),
    ),
    image=settings.sandbox_image,
    build_context=Path(settings.sandbox_build_context),
    limits=sandbox_limits,
)

sandbox_execution_service = SandboxExecutionService(
    manager=sandbox_manager,
    session_factory=async_session_maker,
    max_artifacts=settings.sandbox_max_artifacts,
)
