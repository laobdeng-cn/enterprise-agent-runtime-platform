import json
from typing import Any
from uuid import uuid4

import httpx

from app.mcp.contracts import (
    MCPCallResult,
    MCPInitializeResult,
    MCPToolDescriptor,
)


class MCPError(RuntimeError):
    pass


class MCPTransportError(MCPError):
    pass


class MCPProtocolError(MCPError):
    pass


class MCPRemoteError(MCPError):
    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class MCPHttpClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def initialize(
        self,
        endpoint_url: str,
        *,
        protocol_version: str,
    ) -> MCPInitializeResult:
        result = await self._request(
            endpoint_url,
            method="initialize",
            params={
                "protocolVersion": protocol_version,
                "capabilities": {},
                "clientInfo": {
                    "name": "enterprise-agent-runtime-platform",
                    "version": "0.10.0",
                },
            },
        )
        return MCPInitializeResult.model_validate(result)

    async def list_tools(
        self,
        endpoint_url: str,
    ) -> list[MCPToolDescriptor]:
        result = await self._request(
            endpoint_url,
            method="tools/list",
            params={},
        )
        tools_raw = result.get("tools")
        if not isinstance(tools_raw, list):
            raise MCPProtocolError("MCP tools/list response has no tools array")
        return [
            MCPToolDescriptor.model_validate(item)
            for item in tools_raw
        ]

    async def call_tool(
        self,
        endpoint_url: str,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> MCPCallResult:
        params: dict[str, Any] = {
            "name": tool_name,
            "arguments": arguments,
        }
        if metadata:
            params["_meta"] = metadata
        result = await self._request(
            endpoint_url,
            method="tools/call",
            params=params,
        )
        return MCPCallResult.model_validate(result)

    async def _request(
        self,
        endpoint_url: str,
        *,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        request_id = str(uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    endpoint_url,
                    json=payload,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MCPTransportError(
                f"MCP transport failed with {exc.__class__.__name__}"
            ) from exc

        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise MCPProtocolError(
                "MCP server returned invalid JSON"
            ) from exc

        if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
            raise MCPProtocolError("Invalid MCP JSON-RPC envelope")
        if str(body.get("id")) != request_id:
            raise MCPProtocolError("MCP response id does not match request")

        error = body.get("error")
        if isinstance(error, dict):
            raise MCPRemoteError(
                str(error.get("message") or "MCP remote error"),
                code=(
                    int(error["code"])
                    if isinstance(error.get("code"), int)
                    else None
                ),
                data=error.get("data"),
            )

        result = body.get("result")
        if not isinstance(result, dict):
            raise MCPProtocolError("MCP response has no object result")
        return result
