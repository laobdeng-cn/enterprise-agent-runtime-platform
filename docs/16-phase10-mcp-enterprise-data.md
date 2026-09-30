# 16 — Phase 10 MCP + Enterprise Data

## Status

**Implemented**

Phase 10 adds Model Context Protocol connectivity as a governed capability layer. MCP servers provide capabilities and enterprise data; they never become authorization authorities.

## Architecture

```text
Agent / Run
   |
   v
Context Engineering
   |
   +--> selected MCP-backed SkillVersion
   |
   v
SkillExecutor
   |
   +--> RBAC + Skill required_permissions
   |
   v
MCPSkillAdapter
   |
   +--> current-principal permission re-check
   +--> durable MCPTool lookup
   |
   v
MCP Client Registry
   |
   +--> Streamable HTTP
   |
   +--> knowledge-mcp
   +--> experiment-mcp
   +--> enterprise-mcp
```

Remote MCP tools are normalized into the platform's existing Skill model. This means MCP capabilities use the same schema validation, permission checks, Context selection, timeout/retry envelope, and later Policy/Trace/Eval layers as local capabilities.

## Durable registry

Migration `20260930_0008` adds:

```text
mcp_servers
mcp_tools
```

### MCPServer

Stores:

- logical name and description;
- endpoint URL;
- transport;
- active/disabled status;
- trust level;
- timeout;
- authentication mode and secret reference metadata;
- platform-owned connector configuration;
- health state/error/timestamps;
- last discovery time;
- creator identity.

### MCPTool

Stores the latest discovered remote capability contract:

- server;
- remote tool name/description;
- input/output JSON Schema;
- remote annotations;
- centrally assigned required permissions;
- centrally assigned side-effect classification;
- active/stale state;
- synchronized local Skill identity;
- discovery timestamp.

Discovery state survives process restart and remains inspectable even when a remote server later becomes unavailable.

## Discovery and Skill synchronization

Discovery executes:

```text
MCPServer
   |
   v
tools/list
   |
   v
remote tool contract
   |
   +--> validate JSON Schemas
   +--> apply platform permission map
   +--> apply platform side-effect map
   |
   v
MCPTool
   |
   v
Skill / SkillVersion (provider_type=mcp)
```

A discovered capability receives a namespaced local Skill name, for example:

```text
knowledge.search_documents
    -> knowledge_search_documents

experiment.create_experiment
    -> experiment_create_experiment

enterprise.query_inventory
    -> enterprise_query_inventory
```

If the remote contract or platform policy changes, discovery creates a new SkillVersion and activates it. If a previously known remote tool disappears, its MCPTool becomes stale and the corresponding MCP Skill is disabled.

## Authorization boundary

MCP metadata cannot grant permissions.

Every synchronized MCP Skill includes:

```text
skill:execute
mcp:execute
+ domain permission(s)
```

Examples:

| Remote tool | Domain permission | Side effect |
| --- | --- | --- |
| `search_documents` | `knowledge:read` | READ_ONLY |
| `get_document` | `knowledge:read` | READ_ONLY |
| `search_experiments` | `experiment:read` | READ_ONLY |
| `create_experiment` | `experiment:create` | REVERSIBLE_WRITE |
| `query_inventory` | `inventory:read` | READ_ONLY |
| `create_work_order` | `work_order:create` | REVERSIBLE_WRITE |
| `submit_approval` | `approval:submit` | SENSITIVE |

Remote annotations remain descriptive metadata. An unknown tool that lacks a platform side-effect mapping defaults to **SENSITIVE** rather than inheriting a remote claim that it is safe.

Authorization is checked twice:

1. SkillExecutor checks the SkillVersion permission contract.
2. MCPExecutionService reloads the current principal and re-evaluates the persisted MCPTool permissions immediately before the remote call.

The Run's creation-time permission snapshot is not sufficient for execution.

## MCP server API

```text
GET   /api/mcp/servers
POST  /api/mcp/servers
GET   /api/mcp/servers/{server_id}
PATCH /api/mcp/servers/{server_id}

POST  /api/mcp/servers/{server_id}/health
POST  /api/mcp/servers/{server_id}/discover
```

Registry read requires `mcp:read`. Registration/configuration/discovery requires `mcp:manage`.

## Transport

Phase 10 standardizes first-party connectors on Streamable HTTP.

The transport boundary is encapsulated by `MCPClientRegistry`, so the Runtime and SkillExecutor do not depend directly on transport details.

Authentication metadata supports:

```text
auth_mode = none
auth_mode = secret_ref
```

Secret references may be stored, but Phase 10 deliberately executes only `auth_mode=none`. Secret resolution is kept out of MCP configuration and will require a dedicated credential resolver rather than passing raw credentials through Agent context.

## First-party enterprise servers

### Knowledge MCP

Tools:

```text
search_documents
get_document
```

Provides synthetic internal engineering/process documents for the enterprise demo path.

### Experiment MCP

Tools:

```text
search_experiments
get_experiment
create_experiment
```

Provides synthetic materials-R&D experiment history plus candidate experiment creation.

### Enterprise MCP

Tools:

```text
query_inventory
create_work_order
submit_approval
```

Provides synthetic enterprise inventory, work-order, and external approval-system integration.

All Phase 10 datasets are demo data. The architectural purpose is to exercise governed enterprise connectors without pretending that synthetic records are production scientific data.

## Context Engineering integration

MCP tools do not bypass Phase 9.

After discovery, an MCP capability is a normal SkillVersion and enters:

```text
permission filter
   ->
query relevance ranking
   ->
Skill count/token budget
   ->
ContextTrace
   ->
DeepSeek tool definitions
```

A capability not selected by the Context plan is not exposed to the model and is not accepted by the model-round SkillExecutor binding set.

## MCP Server Registry UI

The Vue engineering console shows:

- server name and endpoint;
- health state;
- transport and trust level;
- discovered tool count;
- discovered tool names;
- side-effect classification;
- domain permissions;
- synchronized Skill name;
- Health action;
- Rediscover action for principals with `mcp:manage`.

## Docker Compose

The development stack now contains:

```text
postgres
redis
docker
knowledge-mcp
experiment-mcp
enterprise-mcp
backend
frontend
```

The backend waits for first-party MCP server health before startup and seeds/discovers the three connector registrations.

## Validation

Backend unit tests cover:

- MCP Skill execution context requirements;
- principal/Run propagation into MCP execution;
- domain-permission mapping;
- namespaced Skill naming;
- safe default side-effect classification.

Docker Compose integration validates:

- all three first-party server registrations;
- health checks;
- rediscovery;
- durable discovered-tool metadata;
- platform-owned permission mapping;
- synchronized MCP Skills;
- real MCP Skill execution through the backend;
- knowledge-server round trip;
- MCP Skill participation in Phase 9 Context selection;
- earlier Runtime, Workspace, Sandbox, Memory, and Context regressions.

## Phase boundary

Phase 10 provides governed enterprise capabilities, but it does not yet orchestrate multi-role business processes.

Phase 11 builds Workflow + Multi-Agent orchestration on top of the same durable Run, Skill, MCP, Context, Workspace, and Sandbox primitives.

## Exit criteria

Phase 10 is complete when:

1. MCP servers are durable registry entities.
2. health/discovery is available through protected APIs and UI.
3. discovered remote tools are persisted.
4. remote schemas are validated before Skill synchronization.
5. MCP tools become versioned `provider_type=mcp` Skills.
6. domain permissions and side-effect policy are owned by the platform.
7. current permissions are re-evaluated immediately before an MCP call.
8. first-party knowledge, experiment, and enterprise servers run in Compose.
9. at least one MCP capability completes a real backend-to-MCP round trip.
10. an MCP Skill participates in Context Engineering like any other governed capability.
