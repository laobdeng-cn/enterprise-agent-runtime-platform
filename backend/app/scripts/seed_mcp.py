import asyncio
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_maker, engine
from app.models.mcp import MCPServer

FIRST_PARTY_SERVERS: dict[str, dict[str, Any]] = {
    "knowledge": {
        "description": "Internal knowledge and engineering-document MCP server.",
        "endpoint_url": settings.mcp_knowledge_url,
        "permission_mapping": {
            "search_documents": {
                "required_permissions": ["knowledge:read"],
                "side_effect": "READ_ONLY",
            },
            "get_document": {
                "required_permissions": ["knowledge:read"],
                "side_effect": "READ_ONLY",
            },
        },
    },
    "experiment": {
        "description": "R&D experiment-record MCP server.",
        "endpoint_url": settings.mcp_experiment_url,
        "permission_mapping": {
            "search_experiments": {
                "required_permissions": ["experiment:read"],
                "side_effect": "READ_ONLY",
            },
            "get_experiment": {
                "required_permissions": ["experiment:read"],
                "side_effect": "READ_ONLY",
            },
            "create_experiment": {
                "required_permissions": ["experiment:create"],
                "side_effect": "REVERSIBLE_WRITE",
            },
        },
    },
    "enterprise": {
        "description": "Enterprise inventory and work-order MCP server.",
        "endpoint_url": settings.mcp_enterprise_url,
        "permission_mapping": {
            "query_inventory": {
                "required_permissions": ["inventory:read"],
                "side_effect": "READ_ONLY",
            },
            "create_work_order": {
                "required_permissions": ["work_order:create"],
                "side_effect": "IRREVERSIBLE_WRITE",
            },
            "submit_approval": {
                "required_permissions": ["approval:submit"],
                "side_effect": "SENSITIVE",
            },
        },
    },
}


async def seed() -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(MCPServer))
        existing = {
            server.name: server
            for server in result.scalars().all()
        }

        for name, definition in FIRST_PARTY_SERVERS.items():
            server = existing.get(name)
            if server is None:
                server = MCPServer(
                    name=name,
                    description=str(definition["description"]),
                    transport="HTTP_JSONRPC",
                    endpoint_url=str(definition["endpoint_url"]),
                    status="active",
                    trust_level="internal",
                    permission_mapping=dict(
                        definition["permission_mapping"]
                    ),
                    tool_cache=[],
                    server_info={},
                    last_health_status="unknown",
                )
                session.add(server)
            else:
                server.description = str(definition["description"])
                server.transport = "HTTP_JSONRPC"
                server.endpoint_url = str(definition["endpoint_url"])
                server.status = "active"
                server.trust_level = "internal"
                server.permission_mapping = dict(
                    definition["permission_mapping"]
                )

        await session.commit()


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
