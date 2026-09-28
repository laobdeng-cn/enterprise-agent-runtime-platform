import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_maker, engine
from app.models.skill import Skill, SkillVersion

SAFE_SKILLS: dict[str, dict[str, Any]] = {
    "system_echo": {
        "description": "Return the provided text as a structured value.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        "provider_config": {"handler": "system_echo"},
    },
    "math_add": {
        "description": "Add two numeric values.",
        "input_schema": {
            "type": "object",
            "properties": {
                "left": {"type": "number"},
                "right": {"type": "number"},
            },
            "required": ["left", "right"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {"result": {"type": "number"}},
            "required": ["result"],
            "additionalProperties": False,
        },
        "provider_config": {"handler": "math_add"},
    },
    "text_stats": {
        "description": "Calculate character, word, and line counts for text.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "characters": {"type": "integer"},
                "words": {"type": "integer"},
                "lines": {"type": "integer"},
            },
            "required": ["characters", "words", "lines"],
            "additionalProperties": False,
        },
        "provider_config": {"handler": "text_stats"},
    },
}


async def seed() -> None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Skill).options(
                selectinload(Skill.versions),
                selectinload(Skill.active_version),
            )
        )
        existing = {skill.name: skill for skill in result.scalars().unique().all()}

        for name, definition in SAFE_SKILLS.items():
            skill = existing.get(name)
            if skill is None:
                skill = Skill(
                    name=name,
                    description=str(definition["description"]),
                    provider_type="local",
                    status="active",
                )
                session.add(skill)
                await session.flush()
            else:
                skill.description = str(definition["description"])
                skill.provider_type = "local"
                skill.status = "active"

            if skill.active_version_id is None:
                next_version = (
                    max((version.version for version in skill.versions), default=0)
                    + 1
                )
                version = SkillVersion(
                    skill_id=skill.id,
                    version=next_version,
                    input_schema=dict(definition["input_schema"]),
                    output_schema=dict(definition["output_schema"]),
                    required_permissions=["skill:execute"],
                    side_effect="READ_ONLY",
                    timeout_seconds=5,
                    max_attempts=1,
                    provider_config=dict(definition["provider_config"]),
                )
                session.add(version)
                await session.flush()
                skill.active_version_id = version.id

        await session.commit()


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
