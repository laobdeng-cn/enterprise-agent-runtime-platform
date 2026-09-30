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
)
from app.services.mcp import (
    MCPServerConflictError,
    MCPServerDisabledError,
    MCPServerNotFoundError,
    MCPToolSyncError,
    check_mcp_server,
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
        transport=server.transport,
        endpoint_url=server.endpoint_url,
        status=server.status,
        trust_level=server.trust_level,
        permission_mapping=dict(server.permission_mapping),
        tool_cache=list(server.tool_cache),
        protocol_version=server.protocol_version,
        server_info=dict(server.server_info),
        last_health_status=server.last_health_status,
        last_health_at=server.last_health_at,
        last_discovered_at=server.last_discovered_at,
        created_at=server.created_at,
        updated_at=server.updated_at,
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MCPServerNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, MCPServerDisabledError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if isinstance(exc, MCPServerConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if isinstance(exc, MCPToolSyncError):
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
    _: MCPManager,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MCPServerResponse:
    try:
        server = await create_mcp_server(session, payload)
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
        result = await check_mcp_server(session, server_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return MCPHealthResponse(
        server_id=server_id,
        status=result.status,
        protocol_version=result.protocol_version,
        server_info=result.server_info,
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
        result = await discover_mcp_server(
            session,
            server_id,
        )
    except Exception as exc:
        raise _http_error(exc) from exc

    return MCPDiscoveryResponse(
        server=to_server_response(result.server),
        discovered_tools=result.discovered_tools,
        synchronized_skills=result.synchronized_skills,
        disabled_skills=result.disabled_skills,
    )
