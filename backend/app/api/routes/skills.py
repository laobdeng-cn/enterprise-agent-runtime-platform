from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.db.session import get_db
from app.models.identity import User
from app.models.skill import Skill
from app.schemas.skill import (
    SkillCreate,
    SkillExecuteRequest,
    SkillExecuteResponse,
    SkillResponse,
    SkillVersionCreate,
    SkillVersionResponse,
)
from app.services.auth import permission_codes
from app.services.harness import skill_executor
from app.services.skills import (
    SkillConflictError,
    SkillNotFoundError,
    SkillSchemaError,
    SkillVersionNotFoundError,
    activate_skill_version,
    create_skill,
    create_skill_version,
    execute_active_skill,
    get_skill,
    list_skills,
)

router = APIRouter(prefix="/api/skills", tags=["skills"])

SkillReader = Annotated[User, Depends(require_permissions("skill:read"))]
SkillManager = Annotated[User, Depends(require_permissions("skill:manage"))]
SkillRunner = Annotated[User, Depends(require_permissions("skill:execute"))]


def to_skill_response(skill: Skill) -> SkillResponse:
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        provider_type=skill.provider_type,
        status=skill.status,
        active_version_id=skill.active_version_id,
        versions=[
            SkillVersionResponse(
                id=version.id,
                version=version.version,
                input_schema=dict(version.input_schema),
                output_schema=dict(version.output_schema),
                required_permissions=list(version.required_permissions),
                side_effect=version.side_effect,
                timeout_seconds=version.timeout_seconds,
                max_attempts=version.max_attempts,
                provider_config=dict(version.provider_config),
            )
            for version in skill.versions
        ],
    )


@router.get("", response_model=list[SkillResponse])
async def skills_index(
    _: SkillReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[SkillResponse]:
    return [
        to_skill_response(skill)
        for skill in await list_skills(session)
    ]


@router.post(
    "",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
)
async def skills_create(
    payload: SkillCreate,
    _: SkillManager,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SkillResponse:
    try:
        skill = await create_skill(session, payload)
    except SkillConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except SkillSchemaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return to_skill_response(skill)


@router.get("/{skill_id}", response_model=SkillResponse)
async def skills_show(
    skill_id: UUID,
    _: SkillReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SkillResponse:
    try:
        skill = await get_skill(session, skill_id)
    except SkillNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_skill_response(skill)


@router.post(
    "/{skill_id}/versions",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
)
async def skill_versions_create(
    skill_id: UUID,
    payload: SkillVersionCreate,
    _: SkillManager,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SkillResponse:
    try:
        skill = await create_skill_version(session, skill_id, payload)
    except SkillNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SkillSchemaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return to_skill_response(skill)


@router.post(
    "/{skill_id}/versions/{version_id}/activate",
    response_model=SkillResponse,
)
async def skill_versions_activate(
    skill_id: UUID,
    version_id: UUID,
    _: SkillManager,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SkillResponse:
    try:
        skill = await activate_skill_version(session, skill_id, version_id)
    except (SkillNotFoundError, SkillVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_skill_response(skill)


@router.post("/{skill_id}/execute", response_model=SkillExecuteResponse)
async def skills_execute(
    skill_id: UUID,
    payload: SkillExecuteRequest,
    principal: SkillRunner,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SkillExecuteResponse:
    try:
        result = await execute_active_skill(
            session,
            skill_executor,
            skill_id,
            arguments=payload.arguments,
            granted_permissions=permission_codes(principal),
            principal_id=principal.id,
        )
    except (SkillNotFoundError, SkillVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return SkillExecuteResponse(result=result)
