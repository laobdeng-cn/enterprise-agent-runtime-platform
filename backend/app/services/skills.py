from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.harness.contracts import ModelToolCall
from app.models.skill import Skill, SkillVersion
from app.schemas.skill import SkillCreate, SkillVersionCreate
from app.skills.contracts import SkillExecutionContext, SkillExecutionResult
from app.skills.executor import SkillExecutor


class SkillNotFoundError(LookupError):
    pass


class SkillVersionNotFoundError(LookupError):
    pass


class SkillConflictError(ValueError):
    pass


class SkillBindingError(ValueError):
    pass


class SkillSchemaError(ValueError):
    pass


async def list_skills(session: AsyncSession) -> list[Skill]:
    statement = (
        select(Skill)
        .options(
            selectinload(Skill.versions),
            selectinload(Skill.active_version),
        )
        .order_by(Skill.name)
    )
    result = await session.execute(statement)
    return list(result.scalars().unique().all())


async def get_skill(session: AsyncSession, skill_id: UUID) -> Skill:
    statement = (
        select(Skill)
        .options(
            selectinload(Skill.versions),
            selectinload(Skill.active_version),
        )
        .where(Skill.id == skill_id)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(statement)
    skill = result.scalar_one_or_none()
    if skill is None:
        raise SkillNotFoundError(f"Skill {skill_id} was not found")
    return skill


def validate_skill_contract(
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
) -> None:
    try:
        Draft202012Validator.check_schema(input_schema)
        Draft202012Validator.check_schema(output_schema)
    except SchemaError as exc:
        raise SkillSchemaError(str(exc.message)) from exc


async def create_skill(
    session: AsyncSession,
    payload: SkillCreate,
) -> Skill:
    validate_skill_contract(payload.input_schema, payload.output_schema)

    skill = Skill(
        name=payload.name.strip(),
        description=payload.description,
        provider_type=payload.provider_type,
        status="active",
    )
    session.add(skill)

    try:
        await session.flush()
        version = SkillVersion(
            skill_id=skill.id,
            version=1,
            input_schema=dict(payload.input_schema),
            output_schema=dict(payload.output_schema),
            required_permissions=list(payload.required_permissions),
            side_effect=payload.side_effect,
            timeout_seconds=payload.timeout_seconds,
            max_attempts=payload.max_attempts,
            provider_config=dict(payload.provider_config),
        )
        session.add(version)
        await session.flush()
        skill.active_version_id = version.id
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise SkillConflictError(
            f"Skill name '{payload.name.strip()}' already exists"
        ) from exc

    return await get_skill(session, skill.id)


async def create_skill_version(
    session: AsyncSession,
    skill_id: UUID,
    payload: SkillVersionCreate,
) -> Skill:
    validate_skill_contract(payload.input_schema, payload.output_schema)
    skill = await get_skill(session, skill_id)

    result = await session.execute(
        select(func.max(SkillVersion.version)).where(
            SkillVersion.skill_id == skill.id
        )
    )
    max_version = result.scalar_one_or_none() or 0

    version = SkillVersion(
        skill_id=skill.id,
        version=max_version + 1,
        input_schema=dict(payload.input_schema),
        output_schema=dict(payload.output_schema),
        required_permissions=list(payload.required_permissions),
        side_effect=payload.side_effect,
        timeout_seconds=payload.timeout_seconds,
        max_attempts=payload.max_attempts,
        provider_config=dict(payload.provider_config),
    )
    session.add(version)
    await session.flush()
    skill.active_version_id = version.id
    await session.commit()
    return await get_skill(session, skill.id)


async def activate_skill_version(
    session: AsyncSession,
    skill_id: UUID,
    version_id: UUID,
) -> Skill:
    skill = await get_skill(session, skill_id)
    result = await session.execute(
        select(SkillVersion).where(
            SkillVersion.id == version_id,
            SkillVersion.skill_id == skill.id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise SkillVersionNotFoundError(
            f"Skill version {version_id} was not found for Skill {skill_id}"
        )

    skill.active_version_id = version.id
    await session.commit()
    return await get_skill(session, skill.id)


async def resolve_active_skill_versions(
    session: AsyncSession,
    skill_names: list[str],
) -> list[SkillVersion]:
    ordered_names = list(dict.fromkeys(name.strip() for name in skill_names if name.strip()))
    if not ordered_names:
        return []

    statement = (
        select(Skill)
        .options(
            selectinload(Skill.active_version).selectinload(SkillVersion.skill)
        )
        .where(
            Skill.name.in_(ordered_names),
            Skill.status == "active",
        )
    )
    result = await session.execute(statement)
    skills = {skill.name: skill for skill in result.scalars().unique().all()}

    missing = [
        name
        for name in ordered_names
        if name not in skills or skills[name].active_version is None
    ]
    if missing:
        raise SkillBindingError(
            "Unknown, disabled, or unversioned Skills: " + ", ".join(missing)
        )

    resolved: list[SkillVersion] = []
    for name in ordered_names:
        active_version = skills[name].active_version
        if active_version is None:
            raise SkillBindingError(
                f"Skill '{name}' has no active version"
            )
        resolved.append(active_version)
    return resolved


async def execute_active_skill(
    session: AsyncSession,
    executor: SkillExecutor,
    skill_id: UUID,
    *,
    arguments: dict[str, Any],
    granted_permissions: set[str],
    principal_id: UUID,
) -> SkillExecutionResult:
    skill = await get_skill(session, skill_id)
    version = skill.active_version
    if version is None:
        raise SkillVersionNotFoundError(
            f"Skill {skill_id} has no active version"
        )

    return await executor.execute(
        ModelToolCall(
            id=f"manual-{skill.id}",
            name=skill.name,
            arguments=arguments,
        ),
        bound_versions=[version],
        granted_permissions=granted_permissions,
        execution_context=SkillExecutionContext(
            principal_id=principal_id,
        ),
    )
