# Enterprise Agent Runtime Platform

> 企业级智能体运行与自动化平台 — a production-oriented runtime for building, executing, governing, and evaluating enterprise AI agents.

[![Phase](https://img.shields.io/badge/phase-6%20Workspace%20%2B%20Artifacts-blue)](#development-roadmap)
[![CI](https://github.com/laobdeng-cn/enterprise-agent-runtime-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/laobdeng-cn/enterprise-agent-runtime-platform/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12+-informational)](#technology-stack)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-provider-informational)](#technology-stack)

## Overview

Enterprise Agent Runtime Platform is a governed execution platform rather than a thin LLM chat wrapper.

**Phase 6 is implemented.** Every durable Run now owns an isolated persistent Workspace with safe path resolution, file policies, Run-scoped file Skills, Artifact metadata, checksums and authorized downloads.

## Current architecture

```text
Authenticated Principal
        |
       RBAC
        |
        v
     AgentRun
        |
        +--> concrete AgentVersion
        +--> RunStep[]
        +--> RunCheckpoint[]
        +--> RunEvent[]
        +--> ToolCall[]
        +--> Workspace
              ├── input/
              ├── working/
              └── artifacts/
        |
        v
 Durable Runtime
        |
        v
   Agent Harness
        |
        +--> DeepSeek
        |
        +--> bound SkillVersions
                |
                v
           SkillExecutor
```

## Durable runtime

A Run is not a single HTTP request.

```text
PENDING
  ↓
RUNNING
  ├── RETRYING -> RUNNING
  ├── PAUSED -> RUNNING
  ├── COMPLETED
  ├── FAILED
  └── CANCELLED
```

Every transition is validated by the runtime state machine.

The runtime stores checkpoints in PostgreSQL. If the backend restarts while a Run is `RUNNING` or `RETRYING`, startup recovery moves it to `PAUSED`, preserves history, writes a recovery checkpoint, and requires explicit resume.

## Run API

```text
GET  /api/runs
POST /api/runs
GET  /api/runs/{run_id}
POST /api/runs/{run_id}/start
POST /api/runs/{run_id}/pause
POST /api/runs/{run_id}/resume
POST /api/runs/{run_id}/cancel
GET  /api/runs/{run_id}/events
```

The events endpoint is SSE and supports `Last-Event-ID` for reconnect.

## Current persistence

```text
Identity
├── users
├── roles
├── permissions
├── user_roles
└── role_permissions

Agent definitions
├── agents
└── agent_versions

Capabilities
├── skills
├── skill_versions
└── agent_version_skills

Durable Runtime
├── agent_runs
├── run_steps
├── tool_calls
├── run_checkpoints
└── run_events

Workspace
├── workspaces
└── artifacts
```

## Runtime invariants

1. The LLM never grants permissions.
2. A Run captures a concrete AgentVersion.
3. The model sees only bound SkillVersions.
4. Skill arguments are validated before execution.
5. current execution permissions are re-evaluated rather than trusting only the creation-time snapshot.
6. Run transitions are validated centrally.
7. retries are bounded and only retry classified failures.
8. PostgreSQL is the source of truth for resumable execution state.
9. process restart cannot silently erase an active Run.
10. framework-specific graph state does not replace the platform's public domain model.
11. every Run owns a distinct workspace root.
12. Agent file paths are relative and cannot escape through traversal or symlinks.
13. workspace writes are constrained by file-size and total-quota policy.
14. published artifacts are checksummed and tied to a Run-owned Workspace.

## Technology stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Persistence | SQLAlchemy 2, Alembic, PostgreSQL 16 |
| Auth | JWT, Argon2, RBAC |
| Runtime cache | Redis 7 |
| Model provider | DeepSeek |
| Skill schema | JSON Schema Draft 2020-12 |
| Durable runtime | PostgreSQL Run/Step/Checkpoint/Event model |
| Streaming | SSE |
| Workspace | Run-scoped persistent filesystem + metadata |
| Artifact integrity | SHA-256 + MIME/size metadata |
| Frontend | Vue 3, TypeScript, Element Plus |
| Quality | pytest, Ruff, mypy, GitHub Actions |

## Development roadmap

```text
Phase 0  ✅ Architecture & Contracts
Phase 1  ✅ Engineering Skeleton
Phase 2  ✅ Authentication + RBAC
Phase 3  ✅ Agent Harness
Phase 4  ✅ Tool / Skill Registry
Phase 5  ✅ Durable Agent Runtime
Phase 6  ✅ Workspace + Artifacts
Phase 7  ⏭ Docker Sandbox
Phase 8     Memory
Phase 9     Context Engineering
Phase 10    MCP + Enterprise Data
Phase 11    Workflow + Multi-Agent
Phase 12    Human-in-the-loop + Policy Engine
Phase 13    Trace + Observability
Phase 14    Agent Evaluation + Regression
Phase 15    Enterprise Demo + Hardening
```

Manual end-to-end validation is intentionally deferred until all phases are finished. CI continues to validate every phase as it is merged.

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
- [Phase 4 Tool / Skill Registry](docs/10-phase4-tool-skill-registry.md)
- [Phase 5 Durable Agent Runtime](docs/11-phase5-durable-agent-runtime.md)
- [Phase 6 Workspace + Artifacts](docs/12-phase6-workspace-artifacts.md)

## License

A license will be selected before the first public release. Until then, repository contents are provided for source review and project development.
