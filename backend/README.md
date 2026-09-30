# Backend

FastAPI control plane and durable execution backend for Enterprise Agent Runtime Platform.

## Current Phase 10 contents

- JWT authentication and RBAC
- versioned Agent / AgentVersion
- versioned Skill / SkillVersion
- DeepSeek Agent Harness
- durable AgentRun / RunStep / ToolCall / Checkpoint / Event persistence
- per-Run Workspace + Artifact persistence
- isolated Docker Python Sandbox
- scoped durable Memory
- token-budgeted Context Engineering
- durable MCPServer / MCPTool registry
- Streamable HTTP MCP client boundary
- MCP health and discovery APIs
- remote JSON Schema validation
- discovered MCP Tool -> SkillVersion synchronization
- platform-owned MCP permission mapping
- platform-owned side-effect classification
- current-principal permission re-check immediately before MCP execution
- first-party Knowledge / Experiment / Enterprise MCP services
- MCP-backed Skills integrated into Context selection and SkillExecutor
- Alembic migrations through 0008

## MCP execution boundary

```text
AgentRun
   |
   v
Context Engineering
   |
   v
selected provider_type=mcp SkillVersion
   |
   v
SkillExecutor
   |
   +--> Skill required_permissions
   |
   v
MCPSkillAdapter
   |
   v
MCPExecutionService
   |
   +--> reload current principal
   +--> re-check durable MCPTool permissions
   +--> active MCP server/tool check
   |
   v
MCPClientRegistry
   |
   v
first-party / approved MCP server
```

MCP servers are capability providers. Authorization remains in the platform.

## MCP API

```text
GET   /api/mcp/servers
POST  /api/mcp/servers
GET   /api/mcp/servers/{server_id}
PATCH /api/mcp/servers/{server_id}
POST  /api/mcp/servers/{server_id}/health
POST  /api/mcp/servers/{server_id}/discover
```

## First-party capability mapping

```text
knowledge
├── search_documents      -> knowledge:read
└── get_document          -> knowledge:read

experiment
├── search_experiments    -> experiment:read
├── get_experiment        -> experiment:read
└── create_experiment     -> experiment:create

enterprise
├── query_inventory       -> inventory:read
├── create_work_order     -> work_order:create
└── submit_approval       -> approval:submit
```

Every MCP capability also requires `skill:execute` and `mcp:execute`.

## Validation

CI executes:

```bash
ruff check app tests
mypy app
pytest
```

Docker Compose integration also validates the three first-party MCP servers, discovery, health, Skill synchronization, permission metadata, a real MCP Skill round trip, MCP participation in Context selection, and all earlier Runtime/Workspace/Sandbox/Memory/Context regressions.

Manual local validation remains deferred until all phases are complete.
