# Enterprise Agent Runtime Platform

> 企业级智能体运行与自动化平台 — a production-oriented runtime for building, executing, governing, and evaluating enterprise AI agents.

[![Phase](https://img.shields.io/badge/phase-2%20authentication%20%26%20RBAC-blue)](#development-roadmap)
[![CI](https://github.com/laobdeng-cn/enterprise-agent-runtime-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/laobdeng-cn/enterprise-agent-runtime-platform/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12+-informational)](#technology-stack)
[![FastAPI](https://img.shields.io/badge/FastAPI-active-success)](#technology-stack)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-informational)](#technology-stack)
[![Vue](https://img.shields.io/badge/Vue-3-success)](#technology-stack)

## Overview

Enterprise Agent Runtime Platform is designed to move beyond a simple LLM chat application. The target platform provides a controlled execution environment in which an Agent can plan work, call governed capabilities, operate in isolated workspaces, pause for approval, recover from checkpoints, and expose complete traces and evaluations.

**Phase 2 is implemented.** The platform now has a durable identity and RBAC foundation before Agent execution is introduced.

## Core Security Principle

The LLM may reason and propose actions, but it never authenticates a user or grants authorization.

```text
User Credentials
      |
      v
Argon2 Verification
      |
      v
JWT Access Token
      |
      v
Current Principal
      |
      v
RBAC
      |
      v
Protected Platform Capability
```

Later phases add Tool/Skill policy and human approval on top of this first authorization gate.

## Current Runtime Topology

```text
Browser :5173
   |
   | /api + /health
   v
FastAPI :8000
   |
   +--> PostgreSQL 16
   |      |
   |      +--> users
   |      +--> roles
   |      +--> permissions
   |      +--> user_roles
   |      +--> role_permissions
   |
   +--> Redis 7
```

## Phase 2 Features

- User, Role and Permission persistence
- many-to-many User ↔ Role
- many-to-many Role ↔ Permission
- Argon2 password hashing
- JWT access-token issuance and validation
- database-backed current-principal resolution
- reusable `require_permissions(...)` dependency
- HTTP 401 vs 403 separation
- idempotent default RBAC seed
- optional bootstrap admin
- admin-only RBAC inspection APIs
- frontend sign-in/current-principal view
- CI authentication + authorization smoke test

## Quick Start

Requirements:

- Docker Desktop / Docker Engine
- Docker Compose v2

Clone and configure:

```bash
git clone https://github.com/laobdeng-cn/enterprise-agent-runtime-platform.git
cd enterprise-agent-runtime-platform
cp .env.example .env
```

Before first startup, set at least a local JWT secret and optional bootstrap administrator in `.env`:

```text
JWT_SECRET_KEY=replace-with-a-long-random-development-secret
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=choose-a-local-password
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
```

Start:

```bash
docker compose up --build
```

Open:

| Service | Address |
| --- | --- |
| Frontend | http://localhost:5173 |
| FastAPI OpenAPI | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| Liveness | http://localhost:8000/health/live |

## Authentication API

Login:

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "..."
}
```

Current principal:

```http
GET /api/auth/me
Authorization: Bearer <access-token>
```

Admin RBAC inspection:

```http
GET /api/rbac/roles
GET /api/rbac/permissions
Authorization: Bearer <admin-token>
```

## Default Roles

| Role | Purpose |
| --- | --- |
| `admin` | Platform administration and all current permissions |
| `agent_developer` | Agent/Skill/Run development and evaluation |
| `business_user` | Runs approved Agents and consumes outputs |
| `approver` | Reviews policy-gated actions |

Roles are permission bundles; application code checks atomic permissions rather than branching on role names.

## Technology Stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Authentication | Argon2 via pwdlib, JWT via PyJWT |
| Persistence | SQLAlchemy 2, Alembic, psycopg |
| Primary database | PostgreSQL 16 |
| Runtime state / cache | Redis 7 |
| Frontend | Vue 3, TypeScript, Vite, Element Plus |
| Infrastructure | Docker Compose |
| Quality | pytest, Ruff, mypy, GitHub Actions |
| Agent orchestration | LangGraph — Phase 3+ |
| LLM | DeepSeek through internal provider abstraction — Phase 3+ |
| Protocol | MCP — Phase 10+ |
| Sandbox | Docker-isolated Python execution — Phase 7+ |

## Safety and Governance Invariants

1. **The LLM never grants permissions.**
2. **Passwords are stored only as one-way Argon2 hashes.**
3. **JWT identity is re-resolved against the database on protected requests.**
4. **Inactive or missing users cannot operate with a stale token.**
5. **Tool input will be validated before execution.**
6. **Sensitive actions may require human approval.**
7. **A Run only accesses authorized resources and its assigned Workspace.**
8. **Externally meaningful actions are traceable.**

## Development Roadmap

```text
Phase 0  ✅ Product scope, architecture, contracts, ADRs
Phase 1  ✅ Engineering skeleton + local infrastructure
Phase 2  ✅ Authentication + RBAC
Phase 3  Agent Harness
Phase 4  Tool / Skill Registry
Phase 5  Agent Runtime + durable Run lifecycle
Phase 6  Workspace + artifacts
Phase 7  Docker Sandbox
Phase 8  Memory
Phase 9  Context Engineering
Phase 10 MCP + enterprise data sources
Phase 11 Workflow + Multi-Agent orchestration
Phase 12 Human-in-the-loop + Policy Engine
Phase 13 Trace + Observability
Phase 14 Agent Evaluation + Regression
Phase 15 Enterprise demonstration scenario + deployment hardening
```

## Documentation

- [Product Scope](docs/00-product-scope.md)
- [System Architecture](docs/01-system-architecture.md)
- [Domain Model](docs/02-domain-model.md)
- [Agent Run Lifecycle](docs/03-agent-run-lifecycle.md)
- [Tool / Skill Model](docs/04-tool-skill-model.md)
- [RBAC & Security Model](docs/05-rbac-security-model.md)
- [Development Roadmap](docs/06-phase-roadmap.md)
- [Phase 1 Engineering Skeleton](docs/07-phase1-engineering-skeleton.md)
- [Phase 2 Authentication & RBAC](docs/08-phase2-auth-rbac.md)

Architecture decisions are maintained under [docs/adr](docs/adr).

## License

A license will be selected before the first public release. Until then, repository contents are provided for source review and project development.
