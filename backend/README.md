# Backend

FastAPI control plane and runtime backend for Enterprise Agent Runtime Platform.

## Phase 1 contents

- Python 3.12 project metadata
- FastAPI application
- dependency-aware `/health`
- independent `/health/live`
- Pydantic Settings
- async SQLAlchemy engine
- PostgreSQL connectivity
- Redis connectivity
- Alembic baseline
- pytest baseline
- Ruff and mypy configuration

## Local development

From `backend/`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

On Windows PowerShell, activate with:

```powershell
.\.venv\Scripts\Activate.ps1
```

The default local configuration expects PostgreSQL on `localhost:5432` and Redis on `localhost:6379`. The recommended project workflow is Docker Compose from the repository root.

## Tests and lint

```bash
pytest
ruff check app tests
mypy app
```

## Boundary rule

HTTP handlers must not contain Agent orchestration logic. API code delegates to application/runtime services. Model providers are accessed through an internal adapter introduced in Phase 3.
