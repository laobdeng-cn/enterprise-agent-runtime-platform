# Backend

FastAPI control plane and execution backend for Enterprise Agent Runtime Platform.

## Current Phase 9 contents

- JWT authentication and RBAC
- versioned Agent / AgentVersion
- versioned Skill / SkillVersion
- DeepSeek Agent Harness
- durable AgentRun / RunStep / ToolCall / Checkpoint / Event persistence
- per-Run Workspace + Artifact persistence
- isolated Docker Python Sandbox
- Conversation / Task / Long-term / Semantic Memory
- USER / AGENT / RUN Memory scopes
- deterministic Memory relevance retrieval
- explicit Token Budget Manager
- provider-independent token estimation
- AgentVersion-level `context_policy` overrides
- mandatory system/current-user preservation
- deterministic extractive Context compression
- Memory budget + compression
- permission-first relevant Skill selection
- bounded Skill-definition injection
- reserved runtime capacity for tool history
- tool-result history compression before later model rounds
- persisted `ContextTrace` on MODEL_CALL steps
- `run.context_prepared` durable event
- Run Context Inspector API
- Alembic migrations through 0007

## Context Engineering boundary

```text
AgentVersion + AgentRun
      |
      +--> System / User
      +--> Additional Context
      +--> Relevant Memory
      +--> Bound Skills
      |
      v
Token Budget Manager
      |
      +--> Context Compressor
      +--> Permission-aware Skill Selector
      |
      v
ContextPackage + ContextTrace
      |
      v
Agent Harness
      |
      v
DeepSeek
```

System instructions and the current user request are never silently truncated. Memory, additional context, and tool output are non-authoritative and may be compressed or excluded under policy.

## Context Inspector API

```text
GET /api/runs/{run_id}/context
```

A PENDING Run returns a non-mutating `preview`. Once execution has prepared a model call, the endpoint returns the persisted Context plan used by that attempt.

## Validation

CI executes:

```bash
ruff check app tests
mypy app
pytest
```

Docker Compose CI additionally validates Context-policy overrides, preview budgeting, relevant Skill selection, oversized-context compression, persisted ContextTrace metadata, Memory inclusion, the `run.context_prepared` event, and all prior Workspace/Sandbox/Memory regressions.

Manual local validation remains deferred until all phases are complete.
