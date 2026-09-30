from app.mcp.contracts import MCPRemoteTool
from app.models.mcp import MCPServer
from app.services.mcp import (
    _default_side_effect,
    _skill_name,
    _tool_permissions,
)


def build_server() -> MCPServer:
    return MCPServer(
        name="knowledge",
        description="knowledge",
        url="http://knowledge-mcp:8101/mcp",
        transport="streamable_http",
        status="active",
        trust_level="first_party",
        timeout_seconds=20.0,
        auth_mode="none",
        config={
            "skill_prefix": "knowledge",
            "permission_map": {
                "search_documents": ["knowledge:read"],
            },
            "side_effect_map": {
                "search_documents": "READ_ONLY",
            },
        },
    )


def test_mcp_domain_permissions_are_added_to_platform_permissions() -> None:
    server = build_server()
    tool = MCPRemoteTool(
        name="search_documents",
        description="Search knowledge",
        input_schema={},
        output_schema={},
    )

    permissions = _tool_permissions(server, tool)

    assert permissions == [
        "skill:execute",
        "mcp:execute",
        "knowledge:read",
    ]


def test_unmapped_remote_tool_defaults_to_sensitive() -> None:
    tool = MCPRemoteTool(
        name="unknown_remote_action",
        description="Remote server claims this is safe.",
        input_schema={},
        output_schema={},
        annotations={"readOnlyHint": True},
    )

    assert _default_side_effect(tool) == "SENSITIVE"


def test_mcp_skill_name_is_namespaced_by_server() -> None:
    server = build_server()

    assert (
        _skill_name(server, "search_documents")
        == "knowledge_search_documents"
    )
