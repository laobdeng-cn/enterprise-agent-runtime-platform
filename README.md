# Enterprise Agent Runtime Platform

> 企业级智能体运行与自动化平台 — a production-oriented runtime for building, executing, governing, and evaluating enterprise AI agents.

[![Phase](https://img.shields.io/badge/phase-1%20engineering%20skeleton-blue)](#development-roadmap)
[![CI](https://github.com/laobdeng-cn/enterprise-agent-runtime-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/laobdeng-cn/enterprise-agent-runtime-platform/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12+-informational)](#technology-stack)
[![FastAPI](https://img.shields.io/badge/FastAPI-active-success)](#technology-stack)
[![Vue](https://img.shields.io/badge/Vue-3-success)](#technology-stack)
[![LangGraph](https://img.shields.io/badge/LangGraph-phase%203+-informational)](#development-roadmap)
[![MCP](https://img.shields.io/badge/MCP-phase%2010+-informational)](#development-roadmap)

## Overview

Enterprise Agent Runtime Platform is designed to move beyond a simple LLM chat application. The target platform provides a controlled execution environment in which an agent can:

- plan and execute multi-step business tasks;
- discover and call tools / skills with schema validation;
- connect to enterprise data and services through MCP, APIs, databases, and knowledge bases;
- manage conversation, task, and long-term memory;
- build context under explicit token budgets;
- execute code inside an isolated sandbox and per-run workspace;
- pause for human approval before sensitive actions;
- resume from durable checkpoints;
- coordinate multiple specialized agents;
- expose full execution traces, metrics, and regression evaluation.

The project is built incrementally. **Phase 1 is now implemented**: the backend, frontend, PostgreSQL, Redis, migrations, tests, Docker Compose, and CI skeleton are in place. Agent behavior begins in later phases.

## Core Design Principle

The LLM may **reason and propose actions**, but the runtime owns **execution, authorization, isolation, state, and auditability**.

```text
User Goal
   |
   v
Agent Harness
   |
   +--> Context Builder
   +--> Memory Manager
   +--> Policy Engine
   +--> Tool / Skill Binding
   |
   v
Agent Runtime / Workflow
   |
   +--> MCP / REST / DB / Knowledge
   +--> Workspace / Sandbox
   +--> Human Approval
   |
   v
Trace + Checkpoint + Evaluation
```

## Current Phase — Engineering Skeleton

The repository currently provides:

```text
Browser
  |
  v
Vue 3 + TypeScript :5173
  |
  | /health proxy
  v
FastAPI :8000
  |
  +----> PostgreSQL 16 :5432
  |
  +----> Redis 7 :6379
```

Implemented foundations:

- Python 3.12 + FastAPI;
- Pydantic Settings;
- SQLAlchemy 2 + psycopg;
- Alembic baseline migration;
- PostgreSQL 16;
- Redis 7;
- Vue 3 + TypeScript + Vite + Element Plus;
- Docker Compose;
- dependency-aware health checks;
- pytest;
- Ruff;
- mypy;
- GitHub Actions CI.

## Quick Start

Requirements:

- Docker Desktop / Docker Engine
- Docker Compose v2

Start the complete Phase 1 stack:

```bash
git clone https://github.com/laobdeng-cn/enterprise-agent-runtime-platform.git
cd enterprise-agent-runtime-platform
cp .env.example .env
docker compose up --build
```

The `.env` copy is optional for the default development setup.

Open:

| Service | Address |
| --- | --- |
| Frontend | http://localhost:5173 |
| FastAPI OpenAPI | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| Liveness | http://localhost:8000/health/live |

Check containers:

```bash
docker compose ps
```

A healthy Phase 1 environment should show PostgreSQL, Redis, backend, and frontend as healthy/running.

Stop:

```bash
docker compose down
```

Remove development volumes as well:

```bash
docker compose down -v
```

## Health Contract

`GET /health` verifies PostgreSQL and Redis instead of merely reporting that the HTTP process is alive.

Expected healthy response:

```json
{
  "status": "ok",
  "service": "enterprise-agent-runtime-platform",
  "version": "0.1.0",
  "database": "ok",
  "redis": "ok"
}
```

`GET /health/live` is a lightweight liveness endpoint independent of downstream dependency status.

## Repository Layout

```text
enterprise-agent-runtime-platform/
├── .github/
│   └── workflows/
│       └── ci.yml
├── backend/
│   ├── alembic/
│   ├── app/
│   │   ├── api/
│   │   ├── clients/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── agents/
│   │   ├── runtime/
│   │   ├── skills/
│   │   ├── memory/
│   │   ├── mcp/
│   │   ├── sandbox/
│   │   ├── workflows/
│   │   ├── observability/
│   │   └── eval/
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── mcp_servers/
├── sandbox/
├── docs/
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Technology Stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Persistence | SQLAlchemy 2, Alembic, psycopg |
| Primary database | PostgreSQL 16 |
| Runtime state / cache | Redis 7 |
| Frontend | Vue 3, TypeScript, Vite, Element Plus |
| Infrastructure | Docker Compose |
| Backend quality | pytest, Ruff, mypy |
| CI | GitHub Actions |
| Agent orchestration | LangGraph — Phase 3+ |
| LLM | DeepSeek through internal provider abstraction — Phase 3+ |
| Protocol | MCP — Phase 10+ |
| Sandbox | Docker-isolated Python execution — Phase 7+ |
| Vector retrieval | pgvector planned for memory/retrieval phases |

## Target Capabilities

| Capability | Goal |
| --- | --- |
| Agent Harness | Unified model/tool/context lifecycle and runtime hooks |
| Tool / Skill Registry | Versioned registration, discovery, binding, validation, retry and timeout |
| Agent Runtime | Long-running runs, steps, pause/resume/cancel/retry and checkpoints |
| Workspace | Per-run files and generated artifacts with path isolation |
| Sandbox | Resource-limited isolated code execution |
| Memory | Conversation, task, long-term and semantic memory |
| Context Engineering | Budgeted assembly of instructions, state, memory, evidence and tools |
| MCP | Standardized enterprise tool/data connectivity |
| RBAC & Policy | Deterministic authorization outside the LLM |
| Multi-Agent Workflow | DAG-based coordination with explicit responsibilities |
| Human-in-the-loop | Approval gates for risky actions |
| Observability | Trace timeline for prompts, tool calls, latency, tokens and errors |
| Evaluation | Task, tool, workflow, policy, latency and cost regression metrics |

## Domain Vocabulary

- **Agent** — a versioned definition describing model policy, instructions and capabilities.
- **Skill** — a callable capability with a machine-readable contract and authorization requirements.
- **Run** — one durable execution instance of an Agent or Workflow.
- **RunStep** — one durable step inside a Run.
- **ToolCall** — one concrete request to invoke a Skill.
- **Workspace** — isolated file scope owned by a Run.
- **Artifact** — an output generated by a Run.
- **Memory** — durable or retrievable state available to future context.
- **Workflow** — an explicit graph of tasks, dependencies and routing rules.
- **Approval** — a human decision required before a protected action.
- **TraceSpan** — one observable unit of execution.
- **EvaluationRun** — evaluation/regression execution over defined cases.

## Safety and Governance Invariants

1. **The LLM never grants permissions.**
2. **Tool input is validated before execution.**
3. **Sensitive actions may require human approval.**
4. **Sandbox execution has explicit resource and filesystem boundaries.**
5. **A Run only accesses authorized resources and its assigned Workspace.**
6. **Externally meaningful actions are traceable.**
7. **Retries are bounded and side effects require idempotency consideration.**
8. **Run state transitions are explicit and durable.**

## Development Roadmap

```text
Phase 0  ✅ Product scope, architecture, contracts, ADRs
Phase 1  ✅ Engineering skeleton + local infrastructure
Phase 2  Authentication + RBAC
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

See [docs/06-phase-roadmap.md](docs/06-phase-roadmap.md) for acceptance criteria and [docs/07-phase1-engineering-skeleton.md](docs/07-phase1-engineering-skeleton.md) for Phase 1 details.

## Documentation

1. [Product Scope](docs/00-product-scope.md)
2. [System Architecture](docs/01-system-architecture.md)
3. [Domain Model](docs/02-domain-model.md)
4. [Agent Run Lifecycle](docs/03-agent-run-lifecycle.md)
5. [Tool / Skill Model](docs/04-tool-skill-model.md)
6. [RBAC & Security Model](docs/05-rbac-security-model.md)
7. [Development Roadmap](docs/06-phase-roadmap.md)
8. [Phase 1 Engineering Skeleton](docs/07-phase1-engineering-skeleton.md)

Architecture decisions are maintained under [docs/adr](docs/adr).

## License

A license will be selected before the first public release. Until then, repository contents are provided for source review and project development.
