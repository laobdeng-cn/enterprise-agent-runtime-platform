# Backend

FastAPI control plane and execution backend for Enterprise Agent Runtime Platform.

## Current Phase 5 contents

- JWT authentication and RBAC
- versioned Agent / AgentVersion
- versioned Skill / SkillVersion
- DeepSeek Agent Harness
- schema-validated Skill execution
- durable AgentRun persistence
- RunStep history
- ToolCall persistence
- RunCheckpoint persistence
- durable RunEvent stream
- explicit lifecycle state machine
- bounded runtime retry
- pause / resume / cancel
- startup recovery for interrupted Runs
- SSE Run events
- Alembic migrations through 0005

## Durable execution boundary

```text
Run API
 -> Durable Runtime
 -> Agent Harness
 -> Model / Skills
 -> persisted result, error, steps, tool calls, checkpoints and events
```

PostgreSQL is authoritative for recovery. Redis is available for later coordination but is not the only copy of Run state.

## Run API

```text
GET  /api/runs
POST /api/runs
GET  /api/runs/{run_id}
POST /api/runs/{run_id}/start
POST /api/runs/{run_id}/pause
POST /api/runs/{run_id}/resume
POST /api/runs/{run_id}/cancel
GET  /api/runs/{run_id}/events
```

## Validation

CI executes:

```bash
ruff check app tests
mypy app
pytest
```

Docker Compose CI additionally validates migration 0005, durable Run creation, restart persistence, normalized execution failure, Run history, checkpoints, and SSE lifecycle events.

Manual local validation remains deferred until all phases are complete.
