from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUpstreamError,
)
from app.api.dependencies.auth import require_permissions
from app.db.session import get_db
from app.models.agent import Agent
from app.models.identity import User
from app.schemas.agent import (
    AgentCreate,
    AgentInvokeRequest,
    AgentInvokeResponse,
    AgentResponse,
    AgentVersionCreate,
    AgentVersionResponse,
)
from app.services.agents import (
    AgentConflictError,
    AgentHasNoActiveVersionError,
    AgentNotFoundError,
    AgentVersionNotFoundError,
    activate_agent_version,
    create_agent,
    create_agent_version,
    get_agent,
    invoke_active_agent,
    list_agents,
)
from app.services.harness import agent_harness

router = APIRouter(prefix="/api/agents", tags=["agents"])

AgentReader = Annotated[User, Depends(require_permissions("agent:read"))]
AgentCreator = Annotated[User, Depends(require_permissions("agent:create"))]
AgentEditor = Annotated[User, Depends(require_permissions("agent:update"))]
AgentRunner = Annotated[
    User,
    Depends(require_permissions("agent:read", "run:create")),
]


def to_agent_response(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        status=agent.status,
        active_version_id=agent.active_version_id,
        versions=[
            AgentVersionResponse(
                id=version.id,
                version=version.version,
                system_instructions=version.system_instructions,
                model_provider=version.model_provider,
                model_name=version.model_name,
                temperature=version.temperature,
                max_tokens=version.max_tokens,
                context_policy=dict(version.context_policy),
            )
            for version in agent.versions
        ],
    )


@router.get("", response_model=list[AgentResponse])
async def agents_index(
    _: AgentReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[AgentResponse]:
    agents = await list_agents(session)
    return [to_agent_response(agent) for agent in agents]


@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def agents_create(
    payload: AgentCreate,
    principal: AgentCreator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentResponse:
    try:
        agent = await create_agent(session, principal, payload)
    except AgentConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return to_agent_response(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def agents_show(
    agent_id: UUID,
    _: AgentReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentResponse:
    try:
        agent = await get_agent(session, agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_agent_response(agent)


@router.post(
    "/{agent_id}/versions",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def agent_versions_create(
    agent_id: UUID,
    payload: AgentVersionCreate,
    principal: AgentEditor,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentResponse:
    try:
        agent = await create_agent_version(
            session,
            principal,
            agent_id,
            payload,
        )
    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_agent_response(agent)


@router.post(
    "/{agent_id}/versions/{version_id}/activate",
    response_model=AgentResponse,
)
async def agent_versions_activate(
    agent_id: UUID,
    version_id: UUID,
    _: AgentEditor,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentResponse:
    try:
        agent = await activate_agent_version(session, agent_id, version_id)
    except (AgentNotFoundError, AgentVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_agent_response(agent)


@router.post("/{agent_id}/preview", response_model=AgentInvokeResponse)
async def agent_preview(
    agent_id: UUID,
    payload: AgentInvokeRequest,
    _: AgentRunner,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentInvokeResponse:
    try:
        result = await invoke_active_agent(
            session,
            agent_harness,
            agent_id,
            user_input=payload.input,
            additional_context=payload.additional_context,
        )
    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AgentHasNoActiveVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except ProviderAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except (ProviderRateLimitError, ProviderTimeoutError, ProviderUpstreamError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": exc.code,
                "message": str(exc),
                "retryable": exc.retryable,
            },
        ) from exc
    except ProviderResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return AgentInvokeResponse(
        agent_id=result.agent_id,
        agent_version_id=result.agent_version_id,
        agent_version=result.agent_version,
        content=result.content,
        provider=result.provider,
        model=result.model,
        finish_reason=result.finish_reason,
        usage=result.usage,
        duration_ms=result.duration_ms,
    )
