from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.harness.contracts import HarnessResult
from app.agents.harness.runner import AgentHarness
from app.models.agent import Agent, AgentVersion
from app.models.identity import User
from app.models.skill import SkillVersion
from app.schemas.agent import AgentCreate, AgentVersionCreate
from app.services.auth import permission_codes
from app.services.skills import resolve_active_skill_versions


class AgentNotFoundError(LookupError):
    pass


class AgentVersionNotFoundError(LookupError):
    pass


class AgentConflictError(ValueError):
    pass


class AgentHasNoActiveVersionError(ValueError):
    pass


async def list_agents(session: AsyncSession) -> list[Agent]:
    statement = (
        select(Agent)
        .options(
            selectinload(Agent.versions)
            .selectinload(AgentVersion.bound_skill_versions)
            .selectinload(SkillVersion.skill),
            selectinload(Agent.active_version)
            .selectinload(AgentVersion.bound_skill_versions)
            .selectinload(SkillVersion.skill),
        )
        .order_by(Agent.name)
    )
    result = await session.execute(statement)
    return list(result.scalars().unique().all())


async def get_agent(session: AsyncSession, agent_id: UUID) -> Agent:
    statement = (
        select(Agent)
        .options(
            selectinload(Agent.versions)
            .selectinload(AgentVersion.bound_skill_versions)
            .selectinload(SkillVersion.skill),
            selectinload(Agent.active_version)
            .selectinload(AgentVersion.bound_skill_versions)
            .selectinload(SkillVersion.skill),
        )
        .where(Agent.id == agent_id)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(statement)
    agent = result.scalar_one_or_none()
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} was not found")
    return agent


async def create_agent(
    session: AsyncSession,
    principal: User,
    payload: AgentCreate,
) -> Agent:
    bound_skills = await resolve_active_skill_versions(
        session,
        payload.skills,
    )
    agent = Agent(
        name=payload.name.strip(),
        description=payload.description,
        status="active",
        created_by_user_id=principal.id,
    )
    session.add(agent)

    try:
        await session.flush()
        version = AgentVersion(
            agent_id=agent.id,
            version=1,
            system_instructions=payload.system_instructions,
            model_provider=payload.model_provider,
            model_name=payload.model_name,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            context_policy=dict(payload.context_policy),
            created_by_user_id=principal.id,
            bound_skill_versions=bound_skills,
        )
        session.add(version)
        await session.flush()

        agent.active_version_id = version.id
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AgentConflictError(
            f"Agent name '{payload.name.strip()}' already exists"
        ) from exc

    return await get_agent(session, agent.id)


async def create_agent_version(
    session: AsyncSession,
    principal: User,
    agent_id: UUID,
    payload: AgentVersionCreate,
) -> Agent:
    agent = await get_agent(session, agent_id)
    bound_skills = await resolve_active_skill_versions(
        session,
        payload.skills,
    )

    max_version_result = await session.execute(
        select(func.max(AgentVersion.version)).where(
            AgentVersion.agent_id == agent.id
        )
    )
    max_version = max_version_result.scalar_one_or_none() or 0

    version = AgentVersion(
        agent_id=agent.id,
        version=max_version + 1,
        system_instructions=payload.system_instructions,
        model_provider=payload.model_provider,
        model_name=payload.model_name,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        context_policy=dict(payload.context_policy),
        created_by_user_id=principal.id,
        bound_skill_versions=bound_skills,
    )
    session.add(version)
    await session.flush()

    agent.active_version_id = version.id
    await session.commit()
    return await get_agent(session, agent.id)


async def activate_agent_version(
    session: AsyncSession,
    agent_id: UUID,
    version_id: UUID,
) -> Agent:
    agent = await get_agent(session, agent_id)
    result = await session.execute(
        select(AgentVersion).where(
            AgentVersion.id == version_id,
            AgentVersion.agent_id == agent.id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise AgentVersionNotFoundError(
            f"Agent version {version_id} was not found for Agent {agent_id}"
        )

    agent.active_version_id = version.id
    await session.commit()
    return await get_agent(session, agent.id)


async def invoke_active_agent(
    session: AsyncSession,
    harness: AgentHarness,
    agent_id: UUID,
    *,
    principal: User,
    user_input: str,
    additional_context: list[str],
) -> HarnessResult:
    agent = await get_agent(session, agent_id)
    version = agent.active_version
    if version is None:
        raise AgentHasNoActiveVersionError(
            f"Agent {agent_id} has no active version"
        )

    return await harness.run(
        agent_id=agent.id,
        version=version,
        user_input=user_input,
        additional_context=additional_context,
        granted_permissions=permission_codes(principal),
    )
