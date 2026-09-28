# Enterprise Agent Runtime Platform

> 企业级智能体运行与自动化平台 — a production-oriented runtime for building, executing, governing, and evaluating enterprise AI agents.

[![Phase](https://img.shields.io/badge/phase-3%20Agent%20Harness-blue)](#development-roadmap)
[![CI](https://github.com/laobdeng-cn/enterprise-agent-runtime-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/laobdeng-cn/enterprise-agent-runtime-platform/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12+-informational)](#technology-stack)
[![FastAPI](https://img.shields.io/badge/FastAPI-active-success)](#technology-stack)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-provider-informational)](#agent-harness)

## Overview

Enterprise Agent Runtime Platform is designed to move beyond a simple LLM chat application. It separates model reasoning from authorization, durable execution, tools, sandboxing, approvals, observability, and evaluation.

**Phase 3 is implemented.** The project now has authenticated versioned Agents and a provider-independent Agent Harness with a DeepSeek adapter.

## Core Boundary

```text
Authenticated User
      |
      v
RBAC
      |
      v
Agent Application Service
      |
      v
Agent Harness
      |
      +--> Context Builder
      +--> Lifecycle Hooks
      +--> Model Provider Registry
                |
                v
           DeepSeek Provider
```

The LLM may generate content and later propose actions, but it never grants permissions or bypasses the control plane.

## Agent Harness

Phase 3 introduces:

- stable `Agent` identity;
- immutable-style `AgentVersion` execution configurations;
- active-version switching;
- normalized `ModelRequest` and `ModelResponse`;
- normalized token usage;
- provider error classification;
- provider registry;
- DeepSeek adapter;
- basic Context Package;
- lifecycle hooks;
- Harness preview execution.

A model call is still **not** a durable Run. Phase 5 introduces `AgentRun`, `RunStep`, checkpoints, pause/resume/cancel and bounded retry.

## Quick Start

```bash
git clone https://github.com/laobdeng-cn/enterprise-agent-runtime-platform.git
cd enterprise-agent-runtime-platform
cp .env.example .env
```

Configure local authentication and DeepSeek:

```text
JWT_SECRET_KEY=replace-with-a-long-random-development-secret

BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=choose-a-local-password
BOOTSTRAP_ADMIN_EMAIL=admin@example.com

DEEPSEEK_API_KEY=<your-key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_TIMEOUT_SECONDS=60
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

## Agent APIs

Create a versioned Agent:

```http
POST /api/agents
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "name": "research-assistant",
  "description": "Enterprise research helper",
  "system_instructions": "You are a concise enterprise assistant.",
  "model_provider": "deepseek",
  "model_name": "deepseek-chat",
  "temperature": 0.2
}
```

Execute a non-durable Harness preview:

```http
POST /api/agents/{agent_id}/preview
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "input": "Summarize this task.",
  "additional_context": []
}
```

Version-management endpoints:

```text
GET  /api/agents
GET  /api/agents/{agent_id}
POST /api/agents/{agent_id}/versions
POST /api/agents/{agent_id}/versions/{version_id}/activate
```

## Current Persistence

```text
users
roles
permissions
user_roles
role_permissions

agents
agent_versions
```

`Agent.active_version_id` points to the execution configuration currently selected for new preview calls.

## Technology Stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Authentication | Argon2, JWT |
| Persistence | SQLAlchemy 2, Alembic, PostgreSQL 16 |
| Runtime cache | Redis 7 |
| Frontend | Vue 3, TypeScript, Vite, Element Plus |
| Model transport | httpx |
| LLM provider | DeepSeek via internal ModelProvider adapter |
| Infrastructure | Docker Compose |
| Quality | pytest, Ruff, mypy, GitHub Actions |
| Tool orchestration | Phase 4 |
| Durable runtime / LangGraph | Phase 5+ |
| MCP | Phase 10 |
| Sandbox | Phase 7 |

## Security / Runtime Invariants

1. The LLM never grants permissions.
2. API handlers do not call model providers directly.
3. Provider credentials are environment configuration, not Agent metadata.
4. Agent execution references a concrete AgentVersion.
5. Provider failures are normalized before reaching higher runtime layers.
6. Additional context is treated as untrusted data.
7. Tool execution will require schema validation and authorization.
8. Durable retry semantics are deferred to the Runtime rather than hidden inside API handlers.

## Development Roadmap

```text
Phase 0  ✅ Architecture & Contracts
Phase 1  ✅ Engineering Skeleton
Phase 2  ✅ Authentication + RBAC
Phase 3  ✅ Agent Harness
Phase 4  ⏭ Tool / Skill Registry
Phase 5     Durable Agent Runtime
Phase 6     Workspace + Artifacts
Phase 7     Docker Sandbox
Phase 8     Memory
Phase 9     Context Engineering
Phase 10    MCP + Enterprise Data
Phase 11    Workflow + Multi-Agent
Phase 12    Human-in-the-loop + Policy Engine
Phase 13    Trace + Observability
Phase 14    Agent Evaluation + Regression
Phase 15    Enterprise Demo + Hardening
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
- [Phase 3 Agent Harness](docs/09-phase3-agent-harness.md)

## License

A license will be selected before the first public release. Until then, repository contents are provided for source review and project development.
