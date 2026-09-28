import uuid
from pathlib import Path

import pytest

from app.workspace.errors import (
    UnsafeWorkspacePathError,
    WorkspaceFileTooLargeError,
    WorkspaceFileTypeError,
    WorkspaceQuotaExceededError,
    WorkspaceSymlinkError,
)
from app.workspace.storage import WorkspaceStorage


def test_workspace_isolation_and_text_io(tmp_path: Path) -> None:
    storage = WorkspaceStorage(tmp_path / "workspaces")
    run_a = str(uuid.uuid4())
    run_b = str(uuid.uuid4())

    storage.initialize(run_a)
    storage.initialize(run_b)

    result = storage.write_text(
        run_a,
        "working/result.md",
        "phase six",
        max_file_bytes=1024,
        quota_bytes=4096,
        allowed_roots={"working"},
    )

    assert result["path"] == "working/result.md"
    assert storage.read_text(
        run_a,
        "working/result.md",
        max_file_bytes=1024,
    ) == "phase six"
    assert storage.list_entries(run_b, "working") == []


@pytest.mark.parametrize(
    "path",
    [
        "../secret.txt",
        "working/../secret.txt",
        "/etc/passwd",
        r"working\escape.txt",
        "working//nested.txt",
    ],
)
def test_workspace_rejects_unsafe_paths(tmp_path: Path, path: str) -> None:
    storage = WorkspaceStorage(tmp_path / "workspaces")
    run_id = str(uuid.uuid4())
    storage.initialize(run_id)

    with pytest.raises(UnsafeWorkspacePathError):
        storage.resolve(
            run_id,
            path,
            allowed_roots={"working"},
            must_exist=False,
        )


def test_workspace_rejects_symlink_escape(tmp_path: Path) -> None:
    storage = WorkspaceStorage(tmp_path / "workspaces")
    run_id = str(uuid.uuid4())
    base = storage.initialize(run_id)

    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    (base / "working" / "leak.txt").symlink_to(outside)

    with pytest.raises(WorkspaceSymlinkError):
        storage.read_text(
            run_id,
            "working/leak.txt",
            max_file_bytes=1024,
        )


def test_workspace_enforces_type_size_and_quota(tmp_path: Path) -> None:
    storage = WorkspaceStorage(tmp_path / "workspaces")
    run_id = str(uuid.uuid4())
    storage.initialize(run_id)

    with pytest.raises(WorkspaceFileTypeError):
        storage.write_text(
            run_id,
            "working/program.exe",
            "no",
            max_file_bytes=1024,
            quota_bytes=4096,
            allowed_roots={"working"},
        )

    with pytest.raises(WorkspaceFileTooLargeError):
        storage.write_text(
            run_id,
            "working/large.txt",
            "x" * 20,
            max_file_bytes=10,
            quota_bytes=4096,
            allowed_roots={"working"},
        )

    storage.write_text(
        run_id,
        "working/first.txt",
        "12345678",
        max_file_bytes=1024,
        quota_bytes=10,
        allowed_roots={"working"},
    )
    with pytest.raises(WorkspaceQuotaExceededError):
        storage.write_text(
            run_id,
            "working/second.txt",
            "abcd",
            max_file_bytes=1024,
            quota_bytes=10,
            allowed_roots={"working"},
        )


def test_workspace_publishes_artifact_inside_artifacts_boundary(
    tmp_path: Path,
) -> None:
    storage = WorkspaceStorage(tmp_path / "workspaces")
    run_id = str(uuid.uuid4())
    storage.initialize(run_id)
    storage.write_text(
        run_id,
        "working/report.md",
        "# Report",
        max_file_bytes=1024,
        quota_bytes=4096,
        allowed_roots={"working"},
    )

    artifact_id = uuid.uuid4()
    metadata = storage.publish_artifact(
        run_id,
        "working/report.md",
        artifact_id=artifact_id,
        display_name="analysis.md",
        max_file_bytes=1024,
        quota_bytes=4096,
    )

    assert metadata["relative_path"] == (
        f"artifacts/{artifact_id}/analysis.md"
    )
    assert metadata["size_bytes"] == len(b"# Report")
    artifact_path = storage.artifact_path(
        run_id,
        str(metadata["relative_path"]),
    )
    assert artifact_path.read_text(encoding="utf-8") == "# Report"
