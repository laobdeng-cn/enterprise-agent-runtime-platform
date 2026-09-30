import asyncio
from time import perf_counter
from typing import Any

from mcp import Client

from app.mcp.contracts import MCPHealthResult, MCPRemoteTool
from app.models.mcp import MCPServer


class MCPClientError(RuntimeError):
    pass


class MCPServerUnavailableError(MCPClientError):
    pass


class MCPRemoteToolError(MCPClientError):
    pass


class MCPClientRegistry:
    """Transport-aware client facade for registered MCP servers."""

    async def list_tools(self, server: MCPServer) -> list[MCPRemoteTool]:
        self._validate_server(server)
        try:
            async with asyncio.timeout(server.timeout_seconds):
                async with Client(server.url) as client:
                    result = await client.list_tools()
        except Exception as exc:
            raise MCPServerUnavailableError(
                f"MCP server '{server.name}' discovery failed with "
                f"{exc.__class__.__name__}"
            ) from exc

        tools: list[MCPRemoteTool] = []
        for tool in result.tools:
            output_schema = getattr(tool, "output_schema", None) or {}
            annotations = getattr(tool, "annotations", None)
            if annotations is None:
                annotations_payload: dict[str, Any] = {}
            elif hasattr(annotations, "model_dump"):
                annotations_payload = annotations.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude_none=True,
                )
            elif isinstance(annotations, dict):
                annotations_payload = dict(annotations)
            else:
                annotations_payload = {}

            tools.append(
                MCPRemoteTool(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=dict(tool.input_schema or {}),
                    output_schema=dict(output_schema),
                    annotations=annotations_payload,
                )
            )
        return tools

    async def health(self, server: MCPServer) -> MCPHealthResult:
        started = perf_counter()
        try:
            tools = await self.list_tools(server)
        except MCPClientError as exc:
            return MCPHealthResult(
                status="unavailable",
                latency_ms=(perf_counter() - started) * 1000,
                tool_count=0,
                error=str(exc),
            )
        return MCPHealthResult(
            status="ok",
            latency_ms=(perf_counter() - started) * 1000,
            tool_count=len(tools),
        )

    async def call_tool(
        self,
        server: MCPServer,
        *,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        self._validate_server(server)
        try:
            async with asyncio.timeout(server.timeout_seconds):
                async with Client(server.url) as client:
                    result = await client.call_tool(
                        tool_name,
                        dict(arguments),
                    )
        except Exception as exc:
            raise MCPServerUnavailableError(
                f"MCP tool '{tool_name}' on '{server.name}' failed with "
                f"{exc.__class__.__name__}"
            ) from exc

        if bool(getattr(result, "is_error", False)):
            raise MCPRemoteToolError(
                self._text_content(result)
                or f"MCP tool '{tool_name}' returned an error"
            )

        structured = getattr(result, "structured_content", None)
        if structured is not None:
            return structured

        return {
            "content": [
                block.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude_none=True,
                )
                if hasattr(block, "model_dump")
                else str(block)
                for block in getattr(result, "content", [])
            ]
        }

    @staticmethod
    def _text_content(result: Any) -> str:
        values: list[str] = []
        for block in getattr(result, "content", []):
            text = getattr(block, "text", None)
            if text:
                values.append(str(text))
        return "\n".join(values)

    @staticmethod
    def _validate_server(server: MCPServer) -> None:
        if server.status != "active":
            raise MCPServerUnavailableError(
                f"MCP server '{server.name}' is not active"
            )
        if server.transport != "streamable_http":
            raise MCPClientError(
                f"Unsupported MCP transport '{server.transport}'"
            )
        if server.auth_mode != "none":
            raise MCPClientError(
                "Phase 10 supports secret references but only auth_mode='none' "
                "is executable until a credential resolver is introduced"
            )


mcp_client_registry = MCPClientRegistry()
