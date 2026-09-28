# 11 — Phase 5 Durable Agent Runtime

## Status

**Implemented**

Phase 5 promotes model/tool execution into a durable Run domain. A Run is now a persisted state machine with ordered steps, checkpoints, tool-call records, restart recovery, bounded retry, and reconnectable SSE events.

## Durable domain model

```text
AgentRun
├── RunStep[]
├── ToolCall[]
├── RunCheckpoint[]
└── RunEvent[]
```

### AgentRun

A Run persists:

- Agent and concrete AgentVersion IDs;
- creator;
- current lifecycle state;
- input and additional context;
- permission snapshot for audit;
- execution attempt / maximum attempts;
- state version;
- pause/cancel request flags;
- normalized result or error;
- lifecycle timestamps.

The runtime always executes the concrete `agent_version_id` captured when the Run is created.

### RunStep

Ordered step records include:

- sequence;
- type;
- status;
- attempt;
- input/output/error payloads;
- start/end timestamps.

Phase 5 emits `INPUT`, `MODEL_CALL`, and `FINAL` steps. Later phases can add plan, policy, sandbox, memory, approval, workflow and review steps without changing the Run API.

### ToolCall

Phase 4 Skill results are persisted per Run with:

- provider call ID;
- Skill name;
- concrete SkillVersion ID when available;
- validated arguments;
- structured output or error;
- attempts;
- duration;
- status.

### RunCheckpoint

A checkpoint stores:

- Run state;
- sequence;
- checkpoint kind;
- sanitized resumable payload.

Current checkpoint kinds include:

- `run_created`
- `before_harness`
- `retrying`
- `pause_requested`
- `post_harness_result`
- `runtime_recovered`
- `completed`
- `failed`
- `cancelled`

### RunEvent

Lifecycle events are persisted separately from transient process memory. SSE consumers can reconnect with `Last-Event-ID` and continue after a known sequence.

## State machine

```text
PENDING
  ├── start ───────────────> RUNNING
  └── cancel ──────────────> CANCELLED

RUNNING
  ├── pause ───────────────> PAUSED
  ├── retryable failure ───> RETRYING
  ├── success ─────────────> COMPLETED
  ├── permanent failure ───> FAILED
  └── cancel ──────────────> CANCELLED

RETRYING
  ├── retry ───────────────> RUNNING
  ├── pause ───────────────> PAUSED
  ├── exhausted ───────────> FAILED
  └── cancel ──────────────> CANCELLED

PAUSED
  ├── resume ──────────────> RUNNING
  └── cancel ──────────────> CANCELLED
```

Invalid transitions are rejected by the runtime state machine. Terminal Runs cannot be restarted in place.

`WAITING_APPROVAL` already exists in the state model but becomes operational in Phase 12.

## Execution flow

```text
POST /api/runs
      |
      v
Persist PENDING Run
      |
      +--> INPUT step
      +--> run_created checkpoint
      +--> run.created event
      |
POST /start
      |
      v
RUNNING
      |
      +--> MODEL_CALL step
      +--> before_harness checkpoint
      |
      v
Agent Harness
      |
      +--> Model
      +--> bound Skills
      |
      v
result / error
      |
      +--> retryable + budget -> RETRYING -> RUNNING
      +--> pause -> PAUSED + checkpoint
      +--> cancel -> CANCELLED
      +--> success -> FINAL -> COMPLETED
      +--> permanent failure -> FAILED
```

## Retry model

Runtime retry is bounded and separate from provider implementation.

```text
RuntimeRetryPolicy
├── max_attempts
├── exponential delay
├── delay cap
└── retryable classification
```

Provider errors from Phase 3 already expose `retryable`.

Examples:

- provider timeout -> retryable;
- upstream 5xx -> retryable;
- rate limit -> retryable;
- invalid credentials -> permanent;
- missing provider configuration -> permanent.

A Run stores every failed MODEL_CALL step rather than hiding retries inside one opaque request.

## Pause and resume

Pause is cooperative.

If a pause request reaches a Run while the Harness is already executing, the current result is durably stored in a `post_harness_result` checkpoint and is not finalized.

Resume can consume that checkpoint and complete without repeating the already-finished Harness execution.

If a process is interrupted before a safe post-execution checkpoint exists, the recovered Run requires explicit resume from the last durable boundary.

## Cancellation

Cancellation:

1. persists `CANCELLED`;
2. sets `cancel_requested`;
3. prevents scheduling another attempt;
4. keeps existing steps/checkpoints/tool calls;
5. discards a late execution result rather than changing the terminal state.

Future sandbox/workflow phases add active cancellation of cancellable external work.

## Restart recovery

PostgreSQL is authoritative. Redis is not used as the only execution state store.

At FastAPI startup:

```text
RUNNING / RETRYING
       |
       v
recover_incomplete_runs()
       |
       v
PAUSED
       |
       +--> runtime_recovered checkpoint
       +--> run.recovered event
       +--> interrupted RUNNING steps marked INTERRUPTED
```

This makes an interrupted Run discoverable and explicitly resumable after backend restart instead of silently losing it.

PENDING, PAUSED and terminal Runs naturally survive restart unchanged.

## Graph-engine boundary

ADR 0003 keeps LangGraph behind the platform runtime abstraction.

Phase 5 defines a stable mapping:

```text
domain AgentRun.id
       |
       v
RuntimeThread.graph_config()
       |
       v
configurable.thread_id
checkpoint_ns = agent-runtime
```

The platform's domain checkpoint is the source of truth in Phase 5. A framework-specific LangGraph checkpointer is intentionally not made the public persistence model. Phase 11 can attach graph execution/checkpointer mechanics to the same Run/thread identity without changing public APIs.

## SSE

```http
GET /api/runs/{run_id}/events
Authorization: Bearer <token>
Accept: text/event-stream
Last-Event-ID: <optional sequence>
```

Events are read from durable `run_events`, not a process-local queue.

Examples:

- `run.created`
- `run.running`
- `run.retrying`
- `run.pause_requested`
- `run.paused`
- `run.recovered`
- `run.completed`
- `run.failed`
- `run.cancelled`

## RBAC

Phase 5 adds:

- `run:read`
- `run:create`
- `run:update`
- `run:cancel`

Non-admin principals can only access Runs they created. Administrators can inspect Runs across principals.

Execution authorization is re-evaluated against the Run creator's current roles before every Harness execution. The stored permission snapshot is audit metadata, not an authorization bypass.

## API

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

Run creation does not automatically execute. This separates acceptance/persistence from execution and makes PENDING state explicit.

## CI coverage

Automated checks validate:

- state-machine allow/deny rules;
- terminal-state detection;
- bounded retry policy;
- stable graph-thread mapping;
- Ruff / mypy / pytest;
- migration 0005;
- Run creation;
- persisted INPUT step;
- initial checkpoint;
- backend restart with the Run still present;
- non-retryable model-provider failure persisted as FAILED;
- persisted MODEL_CALL failure;
- persisted failed checkpoint;
- reconnectable SSE lifecycle events;
- frontend build.

CI does not need a real DeepSeek key. Missing provider configuration is intentionally used to verify durable failure semantics.

## Exit criteria

Phase 5 is complete because:

1. Run state is PostgreSQL-backed.
2. RunStep, ToolCall, Checkpoint and Event are persisted.
3. lifecycle transitions are validated centrally.
4. start/pause/resume/cancel semantics exist.
5. runtime retry is bounded and classified.
6. execution references a concrete AgentVersion.
7. current RBAC is re-evaluated at execution time.
8. SSE events are durable/reconnectable.
9. interrupted active states are recovered to PAUSED on startup.
10. step history and checkpoint history are exposed through the Run API.
