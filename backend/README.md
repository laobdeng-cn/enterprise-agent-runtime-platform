# Backend

FastAPI control plane and execution backend for Enterprise Agent Runtime Platform.

## Current Phase 7 contents

- JWT authentication and RBAC
- versioned Agent / AgentVersion
- versioned Skill / SkillVersion
- DeepSeek Agent Harness
- durable AgentRun / RunStep / ToolCall / Checkpoint / Event persistence
- bounded retry and restart recovery
- per-Run Workspace + Artifact persistence
- boundary-safe filesystem resolver and quotas
- Workspace Skills
- dedicated Docker Sandbox daemon integration
- ephemeral Python execution containers
- default-deny network policy
- read-only root filesystem
- non-root execution with dropped Linux capabilities
- CPU / memory / PID / timeout limits
- Run-scoped read-only input and working mounts
- execution-scoped writable output mount
- `python_execute` Skill
- durable `SANDBOX_EXECUTION` RunStep + sandbox events
- output policy validation and Artifact promotion
- automatic sandbox container cleanup
- Alembic migrations through 0006

## Sandbox execution boundary

```text
Run / Agent Harness
      |
      v
SandboxExecutionService
      |
      v
Dedicated Docker daemon
      |
      v
Ephemeral Python container
  ├── input/    RO
  ├── working/  RO
  └── output/   RW
      |
      v
validated Artifact metadata
```

The backend does not execute generated Python in-process and does not provide the sandbox container with a Docker socket.

## Sandbox API

```text
GET  /api/sandbox/health
POST /api/runs/{run_id}/sandbox/python
```

## Validation

CI executes:

```bash
ruff check app tests
mypy app
pytest
```

Docker Compose CI additionally performs real isolated Python execution, verifies Run input access, Artifact generation/download, outbound-network denial, hard timeout, persisted SANDBOX_EXECUTION steps and container cleanup.

Manual local validation remains deferred until all phases are complete.
