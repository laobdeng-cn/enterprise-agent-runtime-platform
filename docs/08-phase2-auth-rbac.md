# 08 — Phase 2 Authentication & RBAC

## Status

**Implemented**

Phase 2 introduces the identity and authorization substrate used by every later runtime capability.

## Security Boundary

```text
Credentials
    |
    v
Password Verification (Argon2)
    |
    v
JWT Access Token
    |
    v
Current Principal
    |
    v
RBAC Permission Check
    |
    +--> allowed
    |
    +--> HTTP 403 denied
```

The LLM never participates in authentication or permission decisions.

## Persistence Model

### users

- UUID primary key
- unique username
- optional unique email
- Argon2 password hash
- active flag
- timestamps

### roles

Stable named permission bundles.

Initial roles:

- `admin`
- `agent_developer`
- `business_user`
- `approver`

### permissions

Atomic `resource:action` capabilities.

Initial set includes:

- `admin:manage`
- `agent:read`
- `agent:create`
- `agent:update`
- `run:create`
- `run:cancel`
- `skill:read`
- `skill:execute`
- `workspace:read`
- `artifact:read`
- `experiment:read`
- `experiment:create`
- `approval:approve`
- `eval:run`

Join tables:

- `user_roles`
- `role_permissions`

## Password Security

Passwords are never stored directly.

The backend uses `pwdlib` with its recommended Argon2 configuration:

```text
plain password
      |
      v
Argon2 hash
      |
      v
users.password_hash
```

Authentication verifies the supplied password against the stored hash.

## JWT Contract

Successful login returns:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

The token currently contains:

- `sub`: User UUID
- `username`
- `type=access`
- `iat`
- `exp`

The database remains authoritative. Every protected request resolves the current User and current Role/Permission assignments from persistence, so removing a role takes effect without waiting for token expiry.

## API

### Login

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "..."
}
```

### Current Principal

```http
GET /api/auth/me
Authorization: Bearer <token>
```

Returns current roles and flattened permission codes.

### Admin RBAC Inspection

Requires `admin:manage`.

```http
GET /api/rbac/roles
GET /api/rbac/permissions
```

## Reusable Permission Dependency

Protected endpoints use the central dependency:

```python
Depends(require_permissions("admin:manage"))
```

Later phases reuse the same mechanism for:

- Agent APIs
- Skill execution
- Run control
- Workspace access
- MCP capabilities
- Evaluation execution

Phase 12 adds a second authorization layer — Policy Engine — for contextual decisions such as `ALLOW / DENY / REQUIRE_APPROVAL`. RBAC remains the first gate.

## Bootstrap

The seed command is idempotent:

```bash
python -m app.scripts.seed_rbac
```

It always reconciles canonical roles/permissions.

An initial admin user is created only when both environment variables are set:

```text
BOOTSTRAP_ADMIN_USERNAME
BOOTSTRAP_ADMIN_PASSWORD
```

Optional:

```text
BOOTSTRAP_ADMIN_EMAIL
```

Existing bootstrap-user passwords are not silently reset on every container restart.

## Docker Startup

Backend startup order:

```text
PostgreSQL healthy
       |
       v
alembic upgrade head
       |
       v
seed_rbac
       |
       v
FastAPI
```

## CI Acceptance

The Docker Compose integration job verifies:

1. migrations run successfully;
2. RBAC seed completes;
3. bootstrap admin can authenticate;
4. the returned JWT can call `/api/auth/me`;
5. admin can list roles;
6. admin can list permissions;
7. frontend and dependency health remain healthy.

Backend checks additionally validate Ruff, mypy and pytest.

## Phase 2 Exit Criteria

Phase 2 is complete when:

- identity tables exist under Alembic migration control;
- passwords are hashed with Argon2;
- login issues expiring JWT access tokens;
- invalid/missing tokens return HTTP 401;
- inactive/missing users cannot authenticate;
- current principal resolves roles and permissions from the database;
- permission dependencies produce HTTP 403 for insufficient access;
- default roles/permissions are seeded idempotently;
- optional admin bootstrap works;
- CI proves the authentication/RBAC chain end-to-end.
