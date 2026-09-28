# Backend

FastAPI control plane and Agent execution backend for Enterprise Agent Runtime Platform.

## Current Phase 3 contents

- Python 3.12 / FastAPI
- async SQLAlchemy / PostgreSQL
- Redis connectivity
- Alembic migrations
- JWT authentication and RBAC
- versioned `Agent` / `AgentVersion`
- normalized ModelRequest / ModelResponse contracts
- ModelProvider abstraction
- DeepSeek provider adapter
- Provider Registry
- basic Context Package / Context Builder
- Agent Harness runner
- lifecycle hooks
- Agent CRUD/version APIs
- Harness preview API
- pytest, Ruff, and mypy

## Local development

From `backend/`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.scripts.seed_rbac
uvicorn app.main:app --reload
```

For an actual model preview configure:

```text
DEEPSEEK_API_KEY=<your-key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_TIMEOUT_SECONDS=60
```

## Agent API

```text
GET  /api/agents
POST /api/agents
GET  /api/agents/{agent_id}
POST /api/agents/{agent_id}/versions
POST /api/agents/{agent_id}/versions/{version_id}/activate
POST /api/agents/{agent_id}/preview
```

The preview endpoint performs a single model invocation through the Harness. It is not yet a durable AgentRun.

## Harness boundary

```text
API -> Application Service -> AgentHarness -> Provider Registry -> DeepSeekProvider
```

API handlers do not make provider HTTP calls.

## Validation

```bash
pytest
ruff check app tests
mypy app
```

Phase 4 adds Tool / Skill binding. Phase 5 adds durable Run state, steps, checkpoints and retry semantics.
