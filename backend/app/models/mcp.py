import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.identity import User
    from app.models.skill import Skill


class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    transport: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="streamable_http",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        index=True,
    )
    trust_level: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="trusted",
    )
    timeout_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=20.0,
    )
    auth_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="none",
    )
    secret_ref: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_health_status: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    last_health_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    last_health_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tools: Mapped[list["MCPTool"]] = relationship(
        back_populates="server",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="MCPTool.name",
    )
    created_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[created_by_user_id],
        lazy="selectin",
    )


class MCPTool(Base):
    __tablename__ = "mcp_tools"
    __table_args__ = (
        UniqueConstraint(
            "server_id",
            "name",
            name="uq_mcp_tools_server_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    input_schema: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    output_schema: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    annotations: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    required_permissions: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    side_effect: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="READ_ONLY",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        index=True,
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("skills.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    server: Mapped[MCPServer] = relationship(
        back_populates="tools",
        foreign_keys=[server_id],
    )
    skill: Mapped["Skill | None"] = relationship(
        foreign_keys=[skill_id],
        lazy="selectin",
    )
