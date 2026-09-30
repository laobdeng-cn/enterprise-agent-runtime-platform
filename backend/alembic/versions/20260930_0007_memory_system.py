"""Add durable scoped Memory system.

Revision ID: 20260930_0007
Revises: 20260928_0006
Create Date: 2026-09-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260930_0007"
down_revision: str | None = "20260928_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("memory_type", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "importance >= 0.0 AND importance <= 1.0",
            name="ck_memories_importance_range",
        ),
        sa.CheckConstraint(
            "("
            "(scope = 'USER' AND agent_id IS NULL AND run_id IS NULL) OR "
            "(scope = 'AGENT' AND agent_id IS NOT NULL AND run_id IS NULL) OR "
            "(scope = 'RUN' AND run_id IS NOT NULL)"
            ")",
            name="ck_memories_scope_target",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_memories_owner_user_id", "memories", ["owner_user_id"])
    op.create_index("ix_memories_agent_id", "memories", ["agent_id"])
    op.create_index("ix_memories_run_id", "memories", ["run_id"])
    op.create_index("ix_memories_memory_type", "memories", ["memory_type"])
    op.create_index("ix_memories_scope", "memories", ["scope"])
    op.create_index("ix_memories_status", "memories", ["status"])
    op.create_index("ix_memories_fingerprint", "memories", ["fingerprint"])
    op.create_index("ix_memories_owner_status", "memories", ["owner_user_id", "status"])
    op.create_index("ix_memories_agent_status", "memories", ["agent_id", "status"])
    op.create_index("ix_memories_run_status", "memories", ["run_id", "status"])
    op.create_index("ix_memories_type_status", "memories", ["memory_type", "status"])
    op.create_index("ix_memories_expires_at", "memories", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_memories_expires_at", table_name="memories")
    op.drop_index("ix_memories_type_status", table_name="memories")
    op.drop_index("ix_memories_run_status", table_name="memories")
    op.drop_index("ix_memories_agent_status", table_name="memories")
    op.drop_index("ix_memories_owner_status", table_name="memories")
    op.drop_index("ix_memories_fingerprint", table_name="memories")
    op.drop_index("ix_memories_status", table_name="memories")
    op.drop_index("ix_memories_scope", table_name="memories")
    op.drop_index("ix_memories_memory_type", table_name="memories")
    op.drop_index("ix_memories_run_id", table_name="memories")
    op.drop_index("ix_memories_agent_id", table_name="memories")
    op.drop_index("ix_memories_owner_user_id", table_name="memories")
    op.drop_table("memories")
