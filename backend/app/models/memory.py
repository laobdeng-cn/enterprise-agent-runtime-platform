import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint(
            "importance >= 0.0 AND importance <= 1.0",
            name="ck_memories_importance_range",
        ),
        CheckConstraint(
            "("
            "(scope = 'USER' AND agent_id IS NULL AND run_id IS NULL) OR "
            "(scope = 'AGENT' AND agent_id IS NOT NULL AND run_id IS NULL) OR "
            "(scope = 'RUN' AND run_id IS NOT NULL)"
            ")",
            name="ck_memories_scope_target",
        ),
        Index("ix_memories_owner_status", "owner_user_id", "status"),
        Index("ix_memories_agent_status", "agent_id", "status"),
        Index("ix_memories_run_status", "run_id", "status"),
        Index("ix_memories_type_status", "memory_type", "status"),
        Index("ix_memories_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    memory_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="ACTIVE",
        index=True,
    )
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(
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
    )
