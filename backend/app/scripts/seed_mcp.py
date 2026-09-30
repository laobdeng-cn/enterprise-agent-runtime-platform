import asyncio
import logging

from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_maker, engine
from app.models.mcp import MCPServer
from app.services.mcp import discover_mcp_server

logger = logging.getLogger(__name__)

FIRST_PARTY_SERVERS = [
    {
        "name": "knowledge",
        "description": "Approved internal knowledge search and document access.",
        "url": settings.mcp_knowledge_url,
        "config": {
            "skill_prefix": "knowledge",
            "permission_map": {
                "search_documents": ["knowledge:read"],
                "get_document": ["knowledge:read"],
            },
            "side_effect_map": {
                "search_documents": "READ_ONLY",
                "get_document": "READ_ONLY",
            },
        },
    },
    {
        "name": "experiment",
        "description": "Authorized R&D experiment data and candidate creation.",
        "url": settings.mcp_experiment_url,
        "config": {
            "skill_prefix": "experiment",
            "permission_map": {
                "search_experiments": ["experiment:read"],
                "get_experiment": ["experiment:read"],
                "create_experiment": ["experiment:create"],
            },
            "side_effect_map": {
                "search_experiments": "READ_ONLY",
                "get_experiment": "READ_ONLY",
                "create_experiment": "REVERSIBLE_WRITE",
            },
        },
    },
    {
        "name": "enterprise",
        "description": "Enterprise inventory, work-order, and approval integrations.",
        "url": settings.mcp_enterprise_url,
        "config": {
            "skill_prefix": "enterprise",
            "permission_map": {
                "query_inventory": ["inventory:read"],
                "create_work_order": ["work_order:create"],
                "submit_approval": ["approval:submit"],
            },
            "side_effect_map": {
                "query_inventory": "READ_ONLY",
                "create_work_order": "REVERSIBLE_WRITE",
                "submit_approval": "SENSITIVE",
            },
        },
    },
]


async def seed() -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(MCPServer))
        existing = {item.name: item for item in result.scalars().all()}

        server_ids = []
        for definition in FIRST_PARTY_SERVERS:
            server = existing.get(definition["name"])
            if server is None:
                server = MCPServer(
                    name=definition["name"],
                    description=definition["description"],
                    url=definition["url"],
                    transport="streamable_http",
                    status="active",
                    trust_level="first_party",
                    timeout_seconds=settings.mcp_timeout_seconds,
                    auth_mode="none",
                    config=definition["config"],
                )
                session.add(server)
                await session.flush()
            else:
                server.description = definition["description"]
                server.url = definition["url"]
                server.transport = "streamable_http"
                server.status = "active"
                server.trust_level = "first_party"
                server.timeout_seconds = settings.mcp_timeout_seconds
                server.auth_mode = "none"
                server.secret_ref = None
                server.config = definition["config"]
            server_ids.append(server.id)

        await session.commit()

        for server_id in server_ids:
            try:
                await discover_mcp_server(session, server_id)
            except Exception:
                logger.exception(
                    "First-party MCP discovery failed for %s; "
                    "registry seed remains available for manual rediscovery",
                    server_id,
                )


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
