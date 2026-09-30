"""Add MCP server registry.

Revision ID: 20260930_0008
Revises: 20260930_0007
Create Date: 2026-09-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260930_0008"
down_revision: str | None = "20260930_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("transport", sa.String(length=32), nullable=False),
        sa.Column("endpoint_url", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("trust_level", sa.String(length=16), nullable=False),
        sa.Column("permission_mapping", sa.JSON(), nullable=False),
        sa.Column("tool_cache", sa.JSON(), nullable=False),
        sa.Column("protocol_version", sa.String(length=32), nullable=True),
        sa.Column("server_info", sa.JSON(), nullable=False),
        sa.Column("last_health_status", sa.String(length=16), nullable=False),
        sa.Column("last_health_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_discovered_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_mcp_servers_name"),
    )
    op.create_index(
        "ix_mcp_servers_name",
        "mcp_servers",
        ["name"],
        unique=True,
    )
    op.create_index(
        "ix_mcp_servers_status",
        "mcp_servers",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mcp_servers_status", table_name="mcp_servers")
    op.drop_index("ix_mcp_servers_name", table_name="mcp_servers")
    op.drop_table("mcp_servers")
