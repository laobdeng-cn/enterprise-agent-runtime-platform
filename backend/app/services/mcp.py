import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.session import async_session_maker
from app.mcp.client import (
    MCPClientRegistry,
    MCPServerUnavailableError,
    mcp_client_registry,
)
from app.mcp.contracts import MCPHealthResult, MCPRemoteTool
from app.models.mcp import MCPServer, MCPTool
from app.models.skill import Skill, SkillVersion
from app.schemas.mcp import MCPServerCreate


class MCPServerNotFoundError(LookupError):
    pass


class MCPServerConflictError(ValueError):
    pass


class MCPDiscoveryError(RuntimeError):
    pass


class MCPExecutionConfigurationError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _server_options() -> tuple[Any, ...]:
    return (
        selectinload(MCPServer.tools).selectinload(MCPTool.skill),
    )


async def list_mcp_servers(session: AsyncSession) -> list[MCPServer]:
    result = await session.execute(
        select(MCPServer)
        .options(*_server_options())
        .order_by(MCPServer.name)
    )
    return list(result.scalars().unique().all())


async def get_mcp_server(
    session: AsyncSession,
    server_id: UUID,
) -> MCPServer:
    result = await session.execute(
        select(MCPServer)
        .options(*_server_options())
        .where(MCPServer.id == server_id)
        .execution_options(populate_existing=True)
    )
    server = result.scalar_one_or_none()
    if server is None:
        raise MCPServerNotFoundError(
            f"MCP server {server_id} was not found"
        )
    return server


async def create_mcp_server(
    session: AsyncSession,
    payload: MCPServerCreate,
    *,
    created_by_user_id: UUID | None,
) -> MCPServer:
    if payload.auth_mode == "secret_ref" and not payload.secret_ref:
        raise ValueError(
            "secret_ref is required when auth_mode='secret_ref'"
        )
    if payload.auth_mode == "none" and payload.secret_ref:
        raise ValueError(
            "secret_ref must be empty when auth_mode='none'"
        )

    server = MCPServer(
        name=payload.name,
        description=payload.description,
        url=str(payload.url),
        transport=payload.transport,
        status="active",
        trust_level=payload.trust_level,
        timeout_seconds=payload.timeout_seconds,
        auth_mode=payload.auth_mode,
        secret_ref=payload.secret_ref,
        config=dict(payload.config),
        created_by_user_id=created_by_user_id,
    )
    session.add(server)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise MCPServerConflictError(
            f"MCP server name '{payload.name}' already exists"
        ) from exc
    return await get_mcp_server(session, server.id)


def _permission_map(server: MCPServer) -> dict[str, list[str]]:
    raw = server.config.get("permission_map")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, list[str]] = {}
    for name, permissions in raw.items():
        if not isinstance(name, str) or not isinstance(permissions, list):
            continue
        result[name] = [
            str(permission)
            for permission in permissions
            if isinstance(permission, str)
        ]
    return result


def _side_effect_map(server: MCPServer) -> dict[str, str]:
    raw = server.config.get("side_effect_map")
    if not isinstance(raw, dict):
        return {}
    valid = {
        "READ_ONLY",
        "REVERSIBLE_WRITE",
        "IRREVERSIBLE_WRITE",
        "SENSITIVE",
    }
    return {
        str(name): str(value)
        for name, value in raw.items()
        if str(value) in valid
    }


def _skill_prefix(server: MCPServer) -> str:
    raw = str(server.config.get("skill_prefix") or server.name)
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    return normalized or "mcp"


def _skill_name(server: MCPServer, tool_name: str) -> str:
    remote = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        tool_name,
    ).strip("_")
    candidate = f"{_skill_prefix(server)}_{remote}"
    if len(candidate) > 64:
        candidate = candidate[:64].rstrip("_")
    return candidate


def _inferred_side_effect(tool: MCPRemoteTool) -> str:
    annotations = tool.annotations
    read_only = bool(
        annotations.get("readOnlyHint")
        or annotations.get("read_only_hint")
    )
    destructive = bool(
        annotations.get("destructiveHint")
        or annotations.get("destructive_hint")
    )
    if read_only:
        return "READ_ONLY"
    if destructive:
        return "IRREVERSIBLE_WRITE"
    return "REVERSIBLE_WRITE"


def _tool_permissions(
    server: MCPServer,
    tool: MCPRemoteTool,
) -> list[str]:
    domain_permissions = _permission_map(server).get(tool.name, [])
    return list(
        dict.fromkeys(
            ["skill:execute", "mcp:execute", *domain_permissions]
        )
    )


async def _sync_skill(
    session: AsyncSession,
    *,
    server: MCPServer,
    tool: MCPRemoteTool,
    required_permissions: list[str],
    side_effect: str,
) -> Skill:
    name = _skill_name(server, tool.name)
    result = await session.execute(
        select(Skill)
        .options(
            selectinload(Skill.versions),
            selectinload(Skill.active_version),
        )
        .where(Skill.name == name)
    )
    skill = result.scalar_one_or_none()

    provider_config = {
        "mcp_server_id": str(server.id),
        "tool_name": tool.name,
    }
    desired = {
        "input_schema": dict(tool.input_schema),
        "output_schema": dict(tool.output_schema),
        "required_permissions": list(required_permissions),
        "side_effect": side_effect,
        "timeout_seconds": max(1, min(120, int(server.timeout_seconds))),
        "max_attempts": 2 if side_effect == "READ_ONLY" else 1,
        "provider_config": provider_config,
    }

    if skill is None:
        skill = Skill(
            name=name,
            description=tool.description,
            provider_type="mcp",
            status="active",
        )
        session.add(skill)
        await session.flush()
        version = SkillVersion(
            skill_id=skill.id,
            version=1,
            **desired,
        )
        session.add(version)
        await session.flush()
        skill.active_version_id = version.id
        return skill

    if skill.provider_type != "mcp":
        raise MCPDiscoveryError(
            f"Discovered MCP Skill '{name}' conflicts with provider "
            f"'{skill.provider_type}'"
        )

    skill.description = tool.description
    skill.status = "active"
    active = skill.active_version
    if active is not None:
        current = {
            "input_schema": dict(active.input_schema),
            "output_schema": dict(active.output_schema),
            "required_permissions": list(active.required_permissions),
            "side_effect": active.side_effect,
            "timeout_seconds": active.timeout_seconds,
            "max_attempts": active.max_attempts,
            "provider_config": dict(active.provider_config),
        }
        if current == desired:
            return skill

    max_version_result = await session.execute(
        select(func.max(SkillVersion.version)).where(
            SkillVersion.skill_id == skill.id
        )
    )
    next_version = int(max_version_result.scalar_one_or_none() or 0) + 1
    version = SkillVersion(
        skill_id=skill.id,
        version=next_version,
        **desired,
    )
    session.add(version)
    await session.flush()
    skill.active_version_id = version.id
    return skill


async def check_mcp_health(
    session: AsyncSession,
    server_id: UUID,
    *,
    client: MCPClientRegistry = mcp_client_registry,
) -> MCPHealthResult:
    server = await get_mcp_server(session, server_id)
    health = await client.health(server)
    server.last_health_status = health.status
    server.last_health_error = health.error
    server.last_health_at = _now()
    await session.commit()
    return health


async def discover_mcp_server(
    session: AsyncSession,
    server_id: UUID,
    *,
    client: MCPClientRegistry = mcp_client_registry,
) -> tuple[MCPServer, list[str], list[str]]:
    server = await get_mcp_server(session, server_id)
    try:
        remote_tools = await client.list_tools(server)
    except MCPServerUnavailableError as exc:
        server.last_health_status = "unavailable"
        server.last_health_error = str(exc)
        server.last_health_at = _now()
        await session.commit()
        raise

    permission_map = _permission_map(server)
    side_effect_map = _side_effect_map(server)
    existing = {
        item.name: item
        for item in server.tools
    }
    discovered_names: set[str] = set()
    activated_skills: list[str] = []

    for remote in remote_tools:
        discovered_names.add(remote.name)
        required_permissions = _tool_permissions(server, remote)
        side_effect = side_effect_map.get(
            remote.name,
            _inferred_side_effect(remote),
        )

        local = existing.get(remote.name)
        if local is None:
            local = MCPTool(
                server_id=server.id,
                name=remote.name,
            )
            session.add(local)

        local.description = remote.description
        local.input_schema = dict(remote.input_schema)
        local.output_schema = dict(remote.output_schema)
        local.annotations = dict(remote.annotations)
        local.required_permissions = required_permissions
        local.side_effect = side_effect
        local.status = "active"
        local.discovered_at = _now()

        skill = await _sync_skill(
            session,
            server=server,
            tool=remote,
            required_permissions=required_permissions,
            side_effect=side_effect,
        )
        await session.flush()
        local.skill_id = skill.id
        activated_skills.append(skill.name)

    stale_tools: list[str] = []
    for name, local in existing.items():
        if name in discovered_names:
            continue
        local.status = "stale"
        stale_tools.append(name)
        if local.skill is not None and local.skill.provider_type == "mcp":
            local.skill.status = "disabled"

    missing_policy_tools = sorted(
        set(permission_map) - discovered_names
    )
    if missing_policy_tools:
        stale_tools.extend(
            f"policy:{name}"
            for name in missing_policy_tools
        )

    server.last_health_status = "ok"
    server.last_health_error = None
    server.last_health_at = _now()
    server.last_discovered_at = _now()
    await session.commit()
    return (
        await get_mcp_server(session, server.id),
        sorted(set(activated_skills)),
        sorted(set(stale_tools)),
    )


class MCPExecutionService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        client: MCPClientRegistry,
    ) -> None:
        self.session_factory = session_factory
        self.client = client

    async def execute(
        self,
        *,
        server_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            server = await get_mcp_server(session, server_id)
            tool = next(
                (
                    item
                    for item in server.tools
                    if item.name == tool_name and item.status == "active"
                ),
                None,
            )
            if tool is None:
                raise MCPExecutionConfigurationError(
                    f"MCP tool '{tool_name}' is not active on '{server.name}'"
                )
            return await self.client.call_tool(
                server,
                tool_name=tool_name,
                arguments=arguments,
            )


mcp_execution_service = MCPExecutionService(
    session_factory=async_session_maker,
    client=mcp_client_registry,
)
