from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MCPToolDescriptor(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        alias="inputSchema",
    )
    output_schema: dict[str, Any] = Field(
        default_factory=dict,
        alias="outputSchema",
    )
    annotations: dict[str, Any] = Field(default_factory=dict)


class MCPInitializeResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    protocol_version: str = Field(alias="protocolVersion")
    capabilities: dict[str, Any] = Field(default_factory=dict)
    server_info: dict[str, Any] = Field(
        default_factory=dict,
        alias="serverInfo",
    )


class MCPCallContent(BaseModel):
    type: str
    text: str | None = None


class MCPCallResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    content: list[MCPCallContent] = Field(default_factory=list)
    structured_content: Any = Field(
        default=None,
        alias="structuredContent",
    )
    is_error: bool = Field(default=False, alias="isError")
