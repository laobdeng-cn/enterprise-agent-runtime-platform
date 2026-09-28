# Backend

FastAPI control plane and runtime backend for Enterprise Agent Runtime Platform.

## Current Phase 2 contents

- Python 3.12 / FastAPI
- Pydantic Settings
- async SQLAlchemy / PostgreSQL
- Redis connectivity
- Alembic migrations
- User / Role / Permission persistence
- Argon2 password hashing
- JWT access tokens
- current-principal dependency
- reusable RBAC permission dependency
- canonical role/permission seed
- optional bootstrap admin
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

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

The recommended project workflow remains Docker Compose from the repository root.

## Authentication endpoints

```text
POST /api/auth/login
GET  /api/auth/me
```

Admin-only RBAC inspection:

```text
GET /api/rbac/roles
GET /api/rbac/permissions
```

## Bootstrap admin

Set these before running the seed command:

```text
BOOTSTRAP_ADMIN_USERNAME
BOOTSTRAP_ADMIN_PASSWORD
BOOTSTRAP_ADMIN_EMAIL   # optional
```

The user is created only when both username and password are present.

## Tests and lint

```bash
pytest
ruff check app tests
mypy app
```

## Boundary rule

HTTP handlers do not contain Agent orchestration logic. The authenticated current principal and RBAC dependency added in Phase 2 are shared security infrastructure for later Agent, Skill, Run, Workspace and MCP modules.
