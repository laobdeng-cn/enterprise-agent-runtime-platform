import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.mcp.client import MCPError, MCPHttpClient
from app.mcp.contracts import MCPCallResult, MCPToolDescriptor
from app.models.mcp import MCPServer
from app.models.skill import Skill, SkillVersion
from app.schemas.mcp import MCPServerCreate, MCPServerUpdate
from app.services.skills import validate_skill_contract


class MCPServerNotFoundError(LookupError):
    pass


class MCPServerConflictError(ValueError):
    pass


class MCPServerDisabledError(PermissionError):
    pass


class MCPToolSyncError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MCPHealthResult:
    status: str
    protocol_version: str | None
    server_info: dict[str, Any]
    error: str | None = None


@dataclass(frozen=True, slots=True)
class MCPDiscoveryResult:
    server: MCPServer
    discovered_tools: int
    synchronized_skills: list[str]
    disabled_skills: list[str]


def _now() -> datetime:
    return datetime.now(UTC)


def _skill_name(server_name: str, tool_name: str) -> str:
    raw = f"mcp_{server_name}_{tool_name}"
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    if len(normalized) <= 64:
        return normalized
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    return normalized[:55].rstrip("_") + "_" + digest


def _tool_policy(
    server: MCPServer,
    tool_name: str,
) -> tuple[list[str], str, int, int]:
    raw = server.permission_mapping.get(tool_name, {})
    mapping = raw if isinstance(raw, dict) else {}

    permissions_raw = mapping.get("required_permissions", [])
    configured = (
        {
            str(item)
            for item in permissions_raw
            if isinstance(item, str) and item.strip()
        }
        if isinstance(permissions_raw, list)
        else set()
    )
    required_permissions = sorted(
        {"skill:execute", "mcp:execute"} | configured
    )

    allowed_side_effects = {
        "READ_ONLY",
        "REVERSIBLE_WRITE",
        "IRREVERSIBLE_WRITE",
        "SENSITIVE",
    }
    side_effect = str(mapping.get("side_effect") or "READ_ONLY")
    if side_effect not in allowed_side_effects:
        raise MCPToolSyncError(
            f"Invalid side_effect mapping for MCP tool '{tool_name}'"
        )

    timeout_raw = mapping.get("timeout_seconds", 30)
    attempts_raw = mapping.get("max_attempts", 1)
    try:
        timeout_seconds = max(1, min(120, int(timeout_raw)))
        max_attempts = max(1, min(3, int(attempts_raw)))
    except (TypeError, ValueError) as exc:
        raise MCPToolSyncError(
            f"Invalid execution policy for MCP tool '{tool_name}'"
        ) from exc

    return (
        required_permissions,
        side_effect,
        timeout_seconds,
        max_attempts,
    )


async def list_mcp_servers(session: AsyncSession) -> list[MCPServer]:
    result = await session.execute(
        select(MCPServer).order_by(MCPServer.name)
    )
    return list(result.scalars().all())


async def get_mcp_server(
    session: AsyncSession,
    server_id: UUID,
) -> MCPServer:
    server = await session.get(MCPServer, server_id)
    if server is None:
        raise MCPServerNotFoundError(
            f"MCP server {server_id} was not found"
        )
    return server


async def create_mcp_server(
    session: AsyncSession,
    payload: MCPServerCreate,
) -> MCPServer:
    server = MCPServer(
        name=payload.name.strip(),
        description=payload.description,
        transport=payload.transport,
        endpoint_url=payload.endpoint_url,
        status=payload.status,
        trust_level=payload.trust_level,
        permission_mapping=dict(payload.permission_mapping),
        tool_cache=[],
        server_info={},
        last_health_status="unknown",
    )
    session.add(server)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise MCPServerConflictError(
            f"MCP server name '{payload.name.strip()}' already exists"
        ) from exc
    await session.refresh(server)
    return server


async def update_mcp_server(
    session: AsyncSession,
    server_id: UUID,
    payload: MCPServerUpdate,
) -> MCPServer:
    server = await get_mcp_server(session, server_id)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(server, key, value)
    await session.commit()
    await session.refresh(server)
    return server


async def check_mcp_server(
    session: AsyncSession,
    server_id: UUID,
    *,
    client: MCPHttpClient | None = None,
) -> MCPHealthResult:
    server = await get_mcp_server(session, server_id)
    mcp_client = client or MCPHttpClient(
        timeout_seconds=settings.mcp_timeout_seconds
    )

    try:
        initialized = await mcp_client.initialize(
            server.endpoint_url,
            protocol_version=settings.mcp_protocol_version,
        )
    except MCPError as exc:
        server.last_health_status = "unhealthy"
        server.last_health_at = _now()
        await session.commit()
        return MCPHealthResult(
            status="unhealthy",
            protocol_version=server.protocol_version,
            server_info=dict(server.server_info),
            error=str(exc),
        )

    server.last_health_status = "healthy"
    server.last_health_at = _now()
    server.protocol_version = initialized.protocol_version
    server.server_info = dict(initialized.server_info)
    await session.commit()
    return MCPHealthResult(
        status="healthy",
        protocol_version=initialized.protocol_version,
        server_info=dict(initialized.server_info),
    )


async def _load_skill_by_name(
    session: AsyncSession,
    name: str,
) -> Skill | None:
    result = await session.execute(
        select(Skill)
        .options(
            selectinload(Skill.versions),
            selectinload(Skill.active_version),
        )
        .where(Skill.name == name)
    )
    return result.scalars().unique().one_or_none()


def _version_matches(
    version: SkillVersion,
    *,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    required_permissions: list[str],
    side_effect: str,
    timeout_seconds: int,
    max_attempts: int,
    provider_config: dict[str, Any],
) -> bool:
    return (
        dict(version.input_schema) == input_schema
        and dict(version.output_schema) == output_schema
        and list(version.required_permissions) == required_permissions
        and version.side_effect == side_effect
        and version.timeout_seconds == timeout_seconds
        and version.max_attempts == max_attempts
        and dict(version.provider_config) == provider_config
    )


async def _sync_tool_as_skill(
    session: AsyncSession,
    server: MCPServer,
    descriptor: MCPToolDescriptor,
) -> str:
    name = _skill_name(server.name, descriptor.name)
    input_schema = dict(descriptor.input_schema or {})
    output_schema = dict(descriptor.output_schema or {})
    validate_skill_contract(input_schema, output_schema)

    (
        required_permissions,
        side_effect,
        timeout_seconds,
        max_attempts,
    ) = _tool_policy(server, descriptor.name)

    provider_config = {
        "server_id": str(server.id),
        "server_name": server.name,
        "tool_name": descriptor.name,
        "transport": server.transport,
    }

    skill = await _load_skill_by_name(session, name)
    if skill is None:
        skill = Skill(
            name=name,
            description=descriptor.description,
            provider_type="mcp",
            status="active",
        )
        session.add(skill)
        await session.flush()
    elif skill.provider_type != "mcp":
        raise MCPToolSyncError(
            f"MCP discovery cannot replace non-MCP Skill '{name}'"
        )
    else:
        skill.description = descriptor.description
        skill.status = "active"

    active = skill.active_version
    if active is not None and _version_matches(
        active,
        input_schema=input_schema,
        output_schema=output_schema,
        required_permissions=required_permissions,
        side_effect=side_effect,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        provider_config=provider_config,
    ):
        return name

    result = await session.execute(
        select(func.max(SkillVersion.version)).where(
            SkillVersion.skill_id == skill.id
        )
    )
    next_version = int(result.scalar_one_or_none() or 0) + 1
    version = SkillVersion(
        skill_id=skill.id,
        version=next_version,
        input_schema=input_schema,
        output_schema=output_schema,
        required_permissions=required_permissions,
        side_effect=side_effect,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        provider_config=provider_config,
    )
    session.add(version)
    await session.flush()
    skill.active_version_id = version.id
    return name


async def discover_mcp_server(
    session: AsyncSession,
    server_id: UUID,
    *,
    client: MCPHttpClient | None = None,
) -> MCPDiscoveryResult:
    server = await get_mcp_server(session, server_id)
    if server.status != "active":
        raise MCPServerDisabledError(
            f"MCP server '{server.name}' is disabled"
        )

    mcp_client = client or MCPHttpClient(
        timeout_seconds=settings.mcp_timeout_seconds
    )
    initialized = await mcp_client.initialize(
        server.endpoint_url,
        protocol_version=settings.mcp_protocol_version,
    )
    descriptors = await mcp_client.list_tools(server.endpoint_url)

    synchronized: list[str] = []
    cache: list[dict[str, Any]] = []
    for descriptor in descriptors:
        skill_name = await _sync_tool_as_skill(
            session,
            server,
            descriptor,
        )
        synchronized.append(skill_name)
        permissions, side_effect, timeout_seconds, max_attempts = (
            _tool_policy(server, descriptor.name)
        )
        cache.append(
            {
                "name": descriptor.name,
                "skill_name": skill_name,
                "description": descriptor.description,
                "input_schema": descriptor.input_schema,
                "output_schema": descriptor.output_schema,
                "annotations": descriptor.annotations,
                "required_permissions": permissions,
                "side_effect": side_effect,
                "timeout_seconds": timeout_seconds,
                "max_attempts": max_attempts,
            }
        )

    previous_names = {
        str(item.get("skill_name"))
        for item in server.tool_cache
        if isinstance(item, dict) and item.get("skill_name")
    }
    current_names = set(synchronized)
    disabled: list[str] = []
    for removed_name in sorted(previous_names - current_names):
        skill = await _load_skill_by_name(session, removed_name)
        if skill is not None and skill.provider_type == "mcp":
            skill.status = "disabled"
            disabled.append(removed_name)

    server.protocol_version = initialized.protocol_version
    server.server_info = dict(initialized.server_info)
    server.tool_cache = cache
    server.last_health_status = "healthy"
    server.last_health_at = _now()
    server.last_discovered_at = _now()
    await session.commit()
    await session.refresh(server)

    return MCPDiscoveryResult(
        server=server,
        discovered_tools=len(descriptors),
        synchronized_skills=sorted(synchronized),
        disabled_skills=disabled,
    )


def _call_output(result: MCPCallResult) -> Any:
    if result.is_error:
        messages = [
            item.text
            for item in result.content
            if item.text
        ]
        raise ValueError(
            "MCP tool reported an error"
            + (": " + " ".join(messages) if messages else "")
        )

    if result.structured_content is not None:
        return result.structured_content

    text_items = [
        item.text
        for item in result.content
        if item.type == "text" and item.text is not None
    ]
    if len(text_items) == 1:
        try:
            return json.loads(text_items[0])
        except json.JSONDecodeError:
            return {"text": text_items[0]}
    return {"content": text_items}


class MCPExecutionService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        client_factory: Callable[[], MCPHttpClient] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.client_factory = client_factory or (
            lambda: MCPHttpClient(
                timeout_seconds=settings.mcp_timeout_seconds
            )
        )

    async def call(
        self,
        *,
        server_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        principal_id: UUID,
        run_id: UUID | None,
    ) -> Any:
        async with self.session_factory() as session:
            server = await get_mcp_server(session, server_id)
            if server.status != "active":
                raise MCPServerDisabledError(
                    f"MCP server '{server.name}' is disabled"
                )

            result = await self.client_factory().call_tool(
                server.endpoint_url,
                tool_name=tool_name,
                arguments=arguments,
                metadata={
                    "principal_id": str(principal_id),
                    "run_id": str(run_id) if run_id else None,
                    "server_id": str(server.id),
                },
            )
            return _call_output(result)


from app.db.session import async_session_maker

mcp_execution_service = MCPExecutionService(
    session_factory=async_session_maker,
)
