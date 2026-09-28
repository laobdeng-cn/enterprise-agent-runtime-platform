import hashlib
import mimetypes
import os
import shutil
import stat
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from app.workspace.errors import (
    UnsafeWorkspacePathError,
    WorkspaceEncodingError,
    WorkspaceFileNotFoundError,
    WorkspaceFileTooLargeError,
    WorkspaceFileTypeError,
    WorkspaceQuotaExceededError,
    WorkspaceSymlinkError,
)

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".yaml",
    ".yml",
    ".log",
    ".html",
    ".py",
}

ARTIFACT_EXTENSIONS = TEXT_EXTENSIONS | {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".zip",
}


class WorkspaceStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def initialize(self, storage_key: str) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        root = self.root.resolve(strict=True)
        if self.root.is_symlink():
            raise WorkspaceSymlinkError("Workspace root cannot be a symlink")

        base = root / storage_key
        if base.exists() and base.is_symlink():
            raise WorkspaceSymlinkError("Workspace directory cannot be a symlink")
        base.mkdir(mode=0o750, exist_ok=True)

        for name in ("input", "working", "artifacts"):
            directory = base / name
            if directory.exists() and directory.is_symlink():
                raise WorkspaceSymlinkError(
                    f"Workspace directory '{name}' cannot be a symlink"
                )
            directory.mkdir(mode=0o750, exist_ok=True)
        return base

    def resolve(
        self,
        storage_key: str,
        relative_path: str,
        *,
        allowed_roots: set[str],
        must_exist: bool = False,
    ) -> Path:
        parts = self._validated_parts(relative_path)
        if not parts or parts[0] not in allowed_roots:
            raise UnsafeWorkspacePathError(
                "Path must remain inside an allowed workspace directory"
            )

        base = self.initialize(storage_key).resolve(strict=True)
        candidate = base.joinpath(*parts)
        self._assert_no_symlink_chain(base, candidate)

        try:
            resolved = candidate.resolve(strict=must_exist)
        except FileNotFoundError as exc:
            raise WorkspaceFileNotFoundError(
                f"Workspace path '{relative_path}' does not exist"
            ) from exc
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise UnsafeWorkspacePathError(
                "Resolved path escapes the workspace boundary"
            ) from exc

        if must_exist and not resolved.exists():
            raise WorkspaceFileNotFoundError(
                f"Workspace path '{relative_path}' does not exist"
            )
        return resolved

    def list_entries(
        self,
        storage_key: str,
        relative_path: str,
    ) -> list[dict[str, Any]]:
        path = self.resolve(
            storage_key,
            relative_path,
            allowed_roots={"input", "working", "artifacts"},
            must_exist=True,
        )
        if not path.is_dir():
            raise UnsafeWorkspacePathError("List target must be a directory")

        base = self.initialize(storage_key).resolve(strict=True)
        entries: list[dict[str, Any]] = []
        for child in sorted(path.iterdir(), key=lambda item: item.name):
            info = child.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise WorkspaceSymlinkError(
                    f"Symlink '{child.name}' is not allowed in a workspace"
                )
            relative = child.relative_to(base).as_posix()
            entries.append(
                {
                    "path": relative,
                    "name": child.name,
                    "type": "directory" if child.is_dir() else "file",
                    "size_bytes": info.st_size if child.is_file() else 0,
                }
            )
        return entries

    def read_text(
        self,
        storage_key: str,
        relative_path: str,
        *,
        max_file_bytes: int,
    ) -> str:
        path = self.resolve(
            storage_key,
            relative_path,
            allowed_roots={"input", "working", "artifacts"},
            must_exist=True,
        )
        if not path.is_file():
            raise WorkspaceFileNotFoundError("Workspace target is not a file")
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            raise WorkspaceFileTypeError(
                f"Text read is not allowed for '{path.suffix or '<no extension>'}'"
            )

        size = path.stat().st_size
        if size > max_file_bytes:
            raise WorkspaceFileTooLargeError(
                f"File exceeds the {max_file_bytes} byte read limit"
            )
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise WorkspaceEncodingError("Workspace text must be UTF-8") from exc

    def write_text(
        self,
        storage_key: str,
        relative_path: str,
        content: str,
        *,
        max_file_bytes: int,
        quota_bytes: int,
        allowed_roots: set[str],
    ) -> dict[str, Any]:
        encoded = content.encode("utf-8")
        if len(encoded) > max_file_bytes:
            raise WorkspaceFileTooLargeError(
                f"File exceeds the {max_file_bytes} byte write limit"
            )

        path = self.resolve(
            storage_key,
            relative_path,
            allowed_roots=allowed_roots,
            must_exist=False,
        )
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            raise WorkspaceFileTypeError(
                f"Text write is not allowed for '{path.suffix or '<no extension>'}'"
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        self._assert_no_symlink_chain(
            self.initialize(storage_key).resolve(strict=True),
            path.parent,
        )

        previous_size = path.stat().st_size if path.exists() else 0
        current_size = self.total_bytes(storage_key)
        projected = current_size - previous_size + len(encoded)
        if projected > quota_bytes:
            raise WorkspaceQuotaExceededError(
                f"Workspace quota exceeded: {projected} > {quota_bytes} bytes"
            )

        temp_path = path.parent / f".tmp-{uuid.uuid4().hex}"
        try:
            with temp_path.open("xb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        return {
            "path": self.relative_path(storage_key, path),
            "size_bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }

    def publish_artifact(
        self,
        storage_key: str,
        source_relative_path: str,
        *,
        artifact_id: uuid.UUID,
        display_name: str,
        max_file_bytes: int,
        quota_bytes: int,
    ) -> dict[str, Any]:
        source = self.resolve(
            storage_key,
            source_relative_path,
            allowed_roots={"working"},
            must_exist=True,
        )
        if not source.is_file():
            raise WorkspaceFileNotFoundError("Artifact source is not a file")

        size = source.stat().st_size
        if size > max_file_bytes:
            raise WorkspaceFileTooLargeError(
                f"Artifact exceeds the {max_file_bytes} byte limit"
            )

        suffix = source.suffix.lower()
        if suffix not in ARTIFACT_EXTENSIONS:
            raise WorkspaceFileTypeError(
                f"Artifact type '{suffix or '<no extension>'}' is not allowed"
            )

        safe_name = self._safe_display_name(display_name or source.name)
        if Path(safe_name).suffix.lower() != suffix:
            safe_name = f"{Path(safe_name).stem or 'artifact'}{suffix}"

        current_size = self.total_bytes(storage_key)
        if current_size + size > quota_bytes:
            raise WorkspaceQuotaExceededError(
                "Publishing this artifact would exceed the workspace quota"
            )

        relative = f"artifacts/{artifact_id}/{safe_name}"
        target = self.resolve(
            storage_key,
            relative,
            allowed_roots={"artifacts"},
            must_exist=False,
        )
        target.parent.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(source, target)

        digest = self.sha256_file(target)
        media_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
        return {
            "relative_path": relative,
            "display_name": safe_name,
            "size_bytes": size,
            "sha256": digest,
            "media_type": media_type,
        }

    def artifact_path(self, storage_key: str, relative_path: str) -> Path:
        path = self.resolve(
            storage_key,
            relative_path,
            allowed_roots={"artifacts"},
            must_exist=True,
        )
        if not path.is_file():
            raise WorkspaceFileNotFoundError("Artifact file does not exist")
        return path

    def total_bytes(self, storage_key: str) -> int:
        base = self.initialize(storage_key).resolve(strict=True)
        total = 0
        for path in base.rglob("*"):
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise WorkspaceSymlinkError(
                    "Symlinks are not allowed inside a workspace"
                )
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
        return total

    def relative_path(self, storage_key: str, path: Path) -> str:
        base = self.initialize(storage_key).resolve(strict=True)
        resolved = path.resolve(strict=True)
        try:
            return resolved.relative_to(base).as_posix()
        except ValueError as exc:
            raise UnsafeWorkspacePathError(
                "Path is outside the workspace"
            ) from exc

    @staticmethod
    def sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _validated_parts(relative_path: str) -> tuple[str, ...]:
        if not relative_path or "\\" in relative_path or "\x00" in relative_path:
            raise UnsafeWorkspacePathError("Workspace path is invalid")
        if relative_path.startswith("/"):
            raise UnsafeWorkspacePathError("Absolute paths are not allowed")

        raw_parts = relative_path.split("/")
        if any(part in {"", ".", ".."} for part in raw_parts):
            raise UnsafeWorkspacePathError(
                "Empty, dot, and parent path segments are not allowed"
            )

        pure = PurePosixPath(relative_path)
        if pure.is_absolute() or ".." in pure.parts:
            raise UnsafeWorkspacePathError("Path traversal is not allowed")
        return tuple(pure.parts)

    @staticmethod
    def _safe_display_name(value: str) -> str:
        if (
            not value
            or value in {".", ".."}
            or "/" in value
            or "\\" in value
            or "\x00" in value
        ):
            raise UnsafeWorkspacePathError("Artifact display name is invalid")
        return value[:255]

    @staticmethod
    def _assert_no_symlink_chain(base: Path, candidate: Path) -> None:
        try:
            relative = candidate.relative_to(base)
        except ValueError as exc:
            raise UnsafeWorkspacePathError(
                "Candidate path is outside the workspace"
            ) from exc

        current = base
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise WorkspaceSymlinkError(
                    f"Symlink component '{part}' is not allowed"
                )
            if not current.exists():
                continue
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise WorkspaceSymlinkError(
                    f"Symlink component '{part}' is not allowed"
                )
