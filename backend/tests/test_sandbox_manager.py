from pathlib import Path
from unittest.mock import MagicMock

from app.sandbox.contracts import SandboxLimits
from app.sandbox.docker_runtime import DockerSandboxManager


def build_manager(tmp_path: Path) -> DockerSandboxManager:
    return DockerSandboxManager(
        client=MagicMock(),
        image="test-sandbox:latest",
        build_context=tmp_path,
        limits=SandboxLimits(
            cpu_limit=1.0,
            memory_limit_mb=256,
            timeout_seconds=3.0,
            pids_limit=32,
            tmpfs_mb=16,
            max_output_bytes=64,
            max_code_bytes=1024,
        ),
    )


def test_sandbox_security_config_is_default_deny(tmp_path: Path) -> None:
    manager = build_manager(tmp_path)

    config = manager.container_security_config()

    assert config["network_mode"] == "none"
    assert config["read_only"] is True
    assert config["memory_limit_mb"] == 256
    assert config["cpu_limit"] == 1.0
    assert config["pids_limit"] == 32
    assert config["cap_drop"] == ["ALL"]
    assert config["no_new_privileges"] is True
    assert config["user"] == "65534:65534"
    assert config["tmpfs_mb"] == 16
    assert config["timeout_seconds"] == 3.0


def test_sandbox_output_is_bounded(tmp_path: Path) -> None:
    manager = build_manager(tmp_path)
    payload = b"x" * 256

    text, truncated = manager._decode_and_bound(payload)

    assert truncated is True
    assert "sandbox output truncated" in text
    assert text.startswith("x")
    assert text.endswith("x")
