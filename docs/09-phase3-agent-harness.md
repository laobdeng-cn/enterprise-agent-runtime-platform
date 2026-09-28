# 09 — Phase 3 Agent Harness

## Status

**Implemented**

Phase 3 introduces the stable model-execution boundary used by future Tool, Runtime, Memory, Context Engineering, Workflow, Trace, and Evaluation phases.

## Goals

The Agent Harness separates application/API code from model-provider details.

```text
Protected API
    |
    v
Application Service
    |
    v
Agent Harness
    |
    +--> Context Builder
    +--> Lifecycle Hooks
    +--> Provider Registry
            |
            v
       DeepSeek Provider
```

HTTP handlers never call DeepSeek directly.

## Versioned Agent Model

### Agent

Stable logical identity:

- UUID
- name
- description
- status
- active version
- creator
- timestamps

### AgentVersion

Immutable execution configuration:

- Agent UUID
- integer version
- system instructions
- model provider
- model name
- temperature
- max tokens
- context policy
- creator
- timestamp

A historical execution can therefore refer to the exact AgentVersion that produced it.

Phase 3 automatically activates a newly created version. The API can also explicitly reactivate an older version.

## Model Provider Contract

Providers implement one normalized interface:

```python
async def invoke(request: ModelRequest) -> ModelResponse
```

Normalized request:

- model
- ordered messages
- temperature
- max tokens

Normalized response:

- content
- provider
- model
- finish reason
- token usage
- provider response ID

This prevents DeepSeek-specific response parsing from leaking into application services.

## DeepSeek Adapter

The first provider is `DeepSeekProvider`.

Configuration:

```text
DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_TIMEOUT_SECONDS=60
```

The API key is supplied only through environment configuration and is never persisted in AgentVersion rows.

The provider sends normalized chat-completion requests to:

```text
POST {DEEPSEEK_BASE_URL}/chat/completions
```

## Error Normalization

Provider failures are classified into Harness exceptions:

| Error | Retryable |
| --- | --- |
| `provider_configuration` | no |
| `provider_authentication` | no |
| `provider_rate_limit` | yes |
| `provider_timeout` | yes |
| `provider_upstream` | yes |
| `provider_response` | no |

Phase 5 uses this retryability metadata when durable Run retries are introduced.

## Context Package

The Phase 3 Context Builder assembles:

1. system instructions from the selected AgentVersion;
2. optional additional context;
3. user input.

Additional context is explicitly framed as data rather than higher-priority instructions.

This is intentionally basic. Phase 9 replaces it with budgeted Context Engineering, retrieval selection, compression, and Context Inspector metadata without changing the Harness provider contract.

## Lifecycle Hooks

The Harness exposes:

- `before_model_call`
- `after_model_call`
- `on_model_error`

Phase 3 ships a no-op implementation. Later observability and evaluation phases can attach tracing/metrics hooks without changing model-provider code.

## API

All endpoints are protected by Phase 2 RBAC.

### List Agents

```http
GET /api/agents
```

Requires `agent:read`.

### Create Agent + v1

```http
POST /api/agents
```

Requires `agent:create`.

Example:

```json
{
  "name": "research-assistant",
  "description": "Material research helper",
  "system_instructions": "You are a concise enterprise assistant.",
  "model_provider": "deepseek",
  "model_name": "deepseek-chat",
  "temperature": 0.2
}
```

### Create New Version

```http
POST /api/agents/{agent_id}/versions
```

Requires `agent:update`.

### Activate Version

```http
POST /api/agents/{agent_id}/versions/{version_id}/activate
```

Requires `agent:update`.

### Harness Preview

```http
POST /api/agents/{agent_id}/preview
```

Requires both:

- `agent:read`
- `run:create`

Example:

```json
{
  "input": "Summarize the latest experiment notes.",
  "additional_context": [
    "Experiment A reached 82% yield."
  ]
}
```

This endpoint is deliberately named **preview**. It executes one model call through the Harness but does not create a durable AgentRun. Durable Run semantics begin in Phase 5.

## Frontend

The Phase 3 console can:

- authenticate;
- display the current principal;
- create Agent v1;
- list existing Agents;
- choose an Agent;
- send a basic preview request through the Harness;
- display provider/model/token/duration metadata.

A real DeepSeek preview requires `DEEPSEEK_API_KEY`.

## Testing

Unit tests use `httpx.MockTransport`; CI never requires a real DeepSeek credential.

Tests verify:

- DeepSeek success normalization;
- rate-limit classification;
- versioned Agent execution through the Harness;
- context propagation;
- token-usage normalization.

Docker Compose CI additionally proves:

- migration `0003` applies;
- authenticated admin can create Agent v1;
- Agent can be read back;
- Agent v2 can be created and becomes active;
- frontend/backend/PostgreSQL/Redis remain healthy.

## Exit Criteria

Phase 3 is complete when:

1. Agent and AgentVersion are persisted under Alembic.
2. model-provider calls are hidden behind a stable abstraction.
3. DeepSeek implements that abstraction.
4. model requests/responses and errors are normalized.
5. context assembly occurs inside the Harness boundary.
6. lifecycle hooks exist for future tracing/evaluation.
7. API handlers never call providers directly.
8. a concrete AgentVersion can execute a mocked DeepSeek request through the Harness in automated tests.
9. a locally configured DeepSeek key enables the same path against the real provider.
