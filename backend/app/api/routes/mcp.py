from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.db.session import get_db
from app.models.identity import User
from app.models.mcp import MCPServer
from app.schemas.mcp import (
    MCPDiscoveryResponse,
    MCPHealthResponse,
    MCPServerCreate,
    MCPServerResponse,
    MCPServerUpdate,
    MCPToolResponse,
)
from app.services.mcp import (
    MCPDiscoveryError,
    MCPServerConflictError,
    MCPServerNotFoundError,
    check_mcp_health,
    create_mcp_server,
    discover_mcp_server,
    get_mcp_server,
    list_mcp_servers,
    update_mcp_server,
)

router = APIRouter(prefix="/api/mcp/servers", tags=["mcp"])

MCPReader = Annotated[User, Depends(require_permissions("mcp:read"))]
MCPManager = Annotated[User, Depends(require_permissions("mcp:manage"))]


def to_server_response(server: MCPServer) -> MCPServerResponse:
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        description=server.description,
        url=server.url,
        transport=server.transport,
        status=server.status,
        trust_level=server.trust_level,
        timeout_seconds=server.timeout_seconds,
        auth_mode=server.auth_mode,
        secret_ref=server.secret_ref,
        config=dict(server.config),
        last_health_status=server.last_health_status,
        last_health_error=server.last_health_error,
        last_health_at=server.last_health_at,
        last_discovered_at=server.last_discovered_at,
        tools=[
            MCPToolResponse(
                id=tool.id,
                name=tool.name,
                description=tool.description,
                input_schema=dict(tool.input_schema),
                output_schema=dict(tool.output_schema),
                annotations=dict(tool.annotations),
                required_permissions=list(tool.required_permissions),
                side_effect=tool.side_effect,
                status=tool.status,
                skill_id=tool.skill_id,
                skill_name=tool.skill.name if tool.skill is not None else None,
                discovered_at=tool.discovered_at,
            )
            for tool in server.tools
        ],
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MCPServerNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, MCPServerConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if isinstance(exc, (ValueError, MCPDiscoveryError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="MCP operation failed",
    )


@router.get("", response_model=list[MCPServerResponse])
async def mcp_servers_index(
    _: MCPReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MCPServerResponse]:
    return [
        to_server_response(server)
        for server in await list_mcp_servers(session)
    ]


@router.post(
    "",
    response_model=MCPServerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def mcp_servers_create(
    payload: MCPServerCreate,
    principal: MCPManager,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MCPServerResponse:
    try:
        server = await create_mcp_server(
            session,
            payload,
            created_by_user_id=principal.id,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_server_response(server)


@router.get("/{server_id}", response_model=MCPServerResponse)
async def mcp_servers_show(
    server_id: UUID,
    _: MCPReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MCPServerResponse:
    try:
        server = await get_mcp_server(session, server_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_server_response(server)


@router.patch("/{server_id}", response_model=MCPServerResponse)
async def mcp_servers_update(
    server_id: UUID,
    payload: MCPServerUpdate,
    _: MCPManager,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MCPServerResponse:
    try:
        server = await update_mcp_server(
            session,
            server_id,
            payload,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return to_server_response(server)


@router.post("/{server_id}/health", response_model=MCPHealthResponse)
async def mcp_servers_health(
    server_id: UUID,
    _: MCPReader,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MCPHealthResponse:
    try:
        result = await check_mcp_health(session, server_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return MCPHealthResponse(
        server_id=server_id,
        status=result.status,
        latency_ms=result.latency_ms,
        tool_count=result.tool_count,
        error=result.error,
    )


@router.post(
    "/{server_id}/discover",
    response_model=MCPDiscoveryResponse,
)
async def mcp_servers_discover(
    server_id: UUID,
    _: MCPManager,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MCPDiscoveryResponse:
    try:
        server, activated_skills, stale_tools = await discover_mcp_server(
            session,
            server_id,
        )
    except Exception as exc:
        raise _http_error(exc) from exc

    return MCPDiscoveryResponse(
        server=to_server_response(server),
        discovered_tools=len(
            [tool for tool in server.tools if tool.status == "active"]
        ),
        activated_skills=activated_skills,
        stale_tools=stale_tools,
    )
