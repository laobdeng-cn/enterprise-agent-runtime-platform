import asyncio
from pathlib import Path
from time import perf_counter
from uuid import UUID

from docker import DockerClient  # type: ignore[import-untyped]
from docker.errors import (  # type: ignore[import-untyped]
    APIError,
    DockerException,
    ImageNotFound,
)
from docker.models.containers import Container  # type: ignore[import-untyped]

from app.sandbox.contracts import (
    RawSandboxResult,
    SandboxLimits,
    SandboxStatus,
)
from app.sandbox.errors import (
    SandboxCodeTooLargeError,
    SandboxExecutionInfrastructureError,
    SandboxImageError,
    SandboxUnavailableError,
)


class DockerSandboxManager:
    def __init__(
        self,
        *,
        client: DockerClient,
        image: str,
        build_context: Path,
        limits: SandboxLimits,
    ) -> None:
        self.client = client
        self.image = image
        self.build_context = build_context
        self.limits = limits
        self._image_ready = False
        self._image_lock = asyncio.Lock()

    async def close(self) -> None:
        await asyncio.to_thread(self.client.close)

    async def ping(self) -> bool:
        try:
            return bool(await asyncio.to_thread(self.client.ping))
        except DockerException:
            return False

    async def ensure_image(self) -> None:
        if self._image_ready:
            return
        async with self._image_lock:
            if self._image_ready:
                return
            try:
                await asyncio.to_thread(self._ensure_image_sync)
            except DockerException as exc:
                raise SandboxImageError(
                    f"Sandbox image '{self.image}' could not be prepared"
                ) from exc
            self._image_ready = True

    def _ensure_image_sync(self) -> None:
        try:
            self.client.images.get(self.image)
            return
        except ImageNotFound:
            pass

        if self.build_context.is_dir():
            self.client.images.build(
                path=str(self.build_context),
                tag=self.image,
                rm=True,
                forcerm=True,
                pull=True,
            )
            return

        try:
            self.client.images.pull(self.image)
        except DockerException as exc:
            raise SandboxImageError(
                "Sandbox image is missing and no build context is available"
            ) from exc

    async def execute_python(
        self,
        *,
        run_id: UUID,
        execution_id: UUID,
        code: str,
        input_dir: Path,
        working_dir: Path,
        output_dir: Path,
        output_relative_path: str,
    ) -> RawSandboxResult:
        code_bytes = code.encode("utf-8")
        if len(code_bytes) > self.limits.max_code_bytes:
            raise SandboxCodeTooLargeError(
                f"Python code exceeds {self.limits.max_code_bytes} bytes"
            )

        if not await self.ping():
            raise SandboxUnavailableError("Dedicated Docker sandbox daemon is unavailable")
        await self.ensure_image()

        started = perf_counter()
        container: Container | None = None
        timed_out = False

        try:
            container = await asyncio.to_thread(
                self.client.containers.create,
                image=self.image,
                command=["python", "-I", "-c", code],
                name=f"earp-sandbox-{execution_id}",
                detach=True,
                network_mode="none",
                read_only=True,
                mem_limit=f"{self.limits.memory_limit_mb}m",
                memswap_limit=f"{self.limits.memory_limit_mb}m",
                nano_cpus=max(1, int(self.limits.cpu_limit * 1_000_000_000)),
                pids_limit=self.limits.pids_limit,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                user="65534:65534",
                working_dir="/workspace",
                environment={
                    "HOME": "/tmp",
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                volumes={
                    str(input_dir): {
                        "bind": "/workspace/input",
                        "mode": "ro",
                    },
                    str(working_dir): {
                        "bind": "/workspace/working",
                        "mode": "ro",
                    },
                    str(output_dir): {
                        "bind": "/workspace/output",
                        "mode": "rw",
                    },
                },
                tmpfs={
                    "/tmp": (
                        "rw,nosuid,nodev,noexec,"
                        f"size={self.limits.tmpfs_mb}m,mode=1777"
                    )
                },
                labels={
                    "earp.sandbox": "true",
                    "earp.run_id": str(run_id),
                    "earp.execution_id": str(execution_id),
                },
            )
            if container is None:
                raise SandboxExecutionInfrastructureError(
                    "Docker SDK did not return a sandbox container"
                )
            await asyncio.to_thread(container.start)

            deadline = perf_counter() + self.limits.timeout_seconds
            while True:
                await asyncio.to_thread(container.reload)
                if container.status in {"exited", "dead"}:
                    break
                if perf_counter() >= deadline:
                    timed_out = True
                    try:
                        await asyncio.to_thread(container.kill)
                    except APIError:
                        pass
                    break
                await asyncio.sleep(0.1)

            await asyncio.to_thread(container.reload)
            state = container.attrs.get("State") or {}
            exit_code_raw = state.get("ExitCode")
            exit_code = int(exit_code_raw) if exit_code_raw is not None else None

            stdout_raw = await asyncio.to_thread(
                container.logs,
                stdout=True,
                stderr=False,
            )
            stderr_raw = await asyncio.to_thread(
                container.logs,
                stdout=False,
                stderr=True,
            )
            stdout, stdout_truncated = self._decode_and_bound(stdout_raw)
            stderr, stderr_truncated = self._decode_and_bound(stderr_raw)

            if timed_out:
                status = SandboxStatus.TIMED_OUT
            elif exit_code == 0:
                status = SandboxStatus.SUCCEEDED
            else:
                status = SandboxStatus.FAILED

            return RawSandboxResult(
                execution_id=execution_id,
                status=status,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=(perf_counter() - started) * 1000,
                timed_out=timed_out,
                output_relative_path=output_relative_path,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
            )
        except SandboxCodeTooLargeError:
            raise
        except DockerException as exc:
            raise SandboxExecutionInfrastructureError(
                f"Sandbox container failed with {exc.__class__.__name__}"
            ) from exc
        finally:
            if container is not None:
                try:
                    await asyncio.to_thread(container.remove, force=True)
                except DockerException:
                    pass

    def container_security_config(self) -> dict[str, object]:
        return {
            "network_mode": "none",
            "read_only": True,
            "memory_limit_mb": self.limits.memory_limit_mb,
            "cpu_limit": self.limits.cpu_limit,
            "pids_limit": self.limits.pids_limit,
            "cap_drop": ["ALL"],
            "no_new_privileges": True,
            "user": "65534:65534",
            "tmpfs_mb": self.limits.tmpfs_mb,
            "timeout_seconds": self.limits.timeout_seconds,
        }

    def _decode_and_bound(self, payload: bytes) -> tuple[str, bool]:
        limit = self.limits.max_output_bytes
        if len(payload) <= limit:
            return payload.decode("utf-8", errors="replace"), False

        half = max(1, limit // 2)
        bounded = (
            payload[:half]
            + b"\n...[sandbox output truncated]...\n"
            + payload[-half:]
        )
        return bounded.decode("utf-8", errors="replace"), True
