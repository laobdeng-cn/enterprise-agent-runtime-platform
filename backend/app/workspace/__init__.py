"""Run-scoped workspace storage boundary."""

from app.workspace.errors import WorkspaceError
from app.workspace.storage import WorkspaceStorage

__all__ = ["WorkspaceError", "WorkspaceStorage"]
