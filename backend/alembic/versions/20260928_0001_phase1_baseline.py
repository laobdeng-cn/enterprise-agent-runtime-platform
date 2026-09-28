"""Phase 1 baseline.

Revision ID: 20260928_0001
Revises:
Create Date: 2026-09-28
"""

from collections.abc import Sequence

revision: str = "20260928_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Establish the migration baseline; domain tables begin in Phase 2."""


def downgrade() -> None:
    """Remove no schema objects because the baseline is intentionally empty."""
