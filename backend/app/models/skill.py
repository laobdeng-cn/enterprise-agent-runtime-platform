import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    Column,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

agent_version_skills = Table(
    "agent_version_skills",
    Base.metadata,
    Column(
        "agent_version_id",
        Uuid(as_uuid=True),
        ForeignKey("agent_versions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "skill_version_id",
        Uuid(as_uuid=True),
        ForeignKey("skill_versions.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)


class Skill(Base):
    __tablename__ = "skills"

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
    provider_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="local",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
    )
    active_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "skill_versions.id",
            name="fk_skills_active_version_id",
            use_alter=True,
            ondelete="SET NULL",
        ),
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

    versions: Mapped[list["SkillVersion"]] = relationship(
        back_populates="skill",
        foreign_keys="SkillVersion.skill_id",
        cascade="all, delete-orphan",
        order_by="SkillVersion.version",
        lazy="selectin",
    )
    active_version: Mapped["SkillVersion | None"] = relationship(
        foreign_keys=[active_version_id],
        post_update=True,
        lazy="selectin",
    )


class SkillVersion(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint(
            "skill_id",
            "version",
            name="uq_skill_versions_skill_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
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
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=20,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    provider_config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    skill: Mapped[Skill] = relationship(
        back_populates="versions",
        foreign_keys=[skill_id],
    )
    agent_versions: Mapped[list["AgentVersion"]] = relationship(
        "AgentVersion",
        secondary=agent_version_skills,
        back_populates="bound_skill_versions",
        lazy="selectin",
    )
