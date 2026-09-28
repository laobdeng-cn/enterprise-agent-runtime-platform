# Backend

FastAPI control plane and execution backend for Enterprise Agent Runtime Platform.

## Current Phase 6 contents

- JWT authentication and RBAC
- versioned Agent / AgentVersion
- versioned Skill / SkillVersion
- DeepSeek Agent Harness
- schema-validated Skill execution
- durable AgentRun / RunStep / ToolCall / Checkpoint / Event persistence
- bounded retry and restart recovery
- per-Run Workspace persistence
- boundary-safe filesystem resolver
- persistent input / working / artifacts directories
- workspace quotas and per-file size limits
- Workspace Skill provider
- `workspace_list`
- `workspace_read_text`
- `workspace_write_text`
- `artifact_publish`
- Artifact metadata, SHA-256 and download
- Alembic migrations through 0006

## Workspace boundary

```text
AgentRun
  |
  +--> Workspace
        ├── input/
        ├── working/
        └── artifacts/
```

Agent filesystem Skills receive workspace-relative paths only.

Traversal, absolute paths, NUL bytes and symlink components are rejected before file access.

## APIs

```text
GET /api/runs/{run_id}/workspace
GET /api/runs/{run_id}/workspace/files
GET /api/runs/{run_id}/workspace/text
PUT /api/runs/{run_id}/workspace/text

GET  /api/runs/{run_id}/artifacts
POST /api/runs/{run_id}/artifacts
GET  /api/runs/{run_id}/artifacts/{artifact_id}/download
```

## Validation

CI executes:

```bash
ruff check app tests
mypy app
pytest
```

Docker Compose CI also validates Workspace creation, traversal rejection, artifact publication/download and persistence across backend restart.

Manual local validation remains deferred until all phases are complete.
