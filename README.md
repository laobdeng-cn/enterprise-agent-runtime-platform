# Enterprise Agent Runtime Platform

> 企业级智能体运行与自动化平台 — a production-oriented runtime for building, executing, governing, and evaluating enterprise AI agents.

[![Phase](https://img.shields.io/badge/phase-4%20Tool%20%2F%20Skill%20Registry-blue)](#development-roadmap)
[![CI](https://github.com/laobdeng-cn/enterprise-agent-runtime-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/laobdeng-cn/enterprise-agent-runtime-platform/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12+-informational)](#technology-stack)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-tool%20calling-informational)](#tool--skill-runtime)

## Overview

Enterprise Agent Runtime Platform is a governed runtime for enterprise AI agents rather than a thin chat wrapper.

**Phase 4 is implemented.** Versioned Agents can now receive explicit versioned Skills. DeepSeek tool calls are normalized, validated, authorized, executed through provider adapters, and returned to the model through a bounded Harness loop.

## Current execution boundary

```text
Authenticated Principal
        |
       RBAC
        |
        v
AgentVersion
        |
        +--> concrete bound SkillVersions
        |
        v
Agent Harness
        |
        v
DeepSeek tool selection
        |
        v
SkillExecutor
  ├── bound-skill check
  ├── JSON Schema input validation
  ├── permission check
  ├── timeout / retry
  ├── provider adapter
  └── JSON Schema output validation
        |
        v
structured tool result
        |
        +--> model final response
```

The model never grants itself capabilities. A tool not bound to the AgentVersion cannot execute.

## Phase 4 capabilities

- `Skill` / `SkillVersion` persistence
- `AgentVersion ↔ SkillVersion` immutable-style binding
- Skill provider registry
- local Skill adapter
- registered local handlers only
- JSON Schema input/output validation
- per-Skill permission metadata
- side-effect classification
- execution timeout
- bounded retry
- normalized Skill errors
- DeepSeek function/tool-call parsing
- bounded model ↔ tool loop
- Skill results returned to the model
- safe seeded Skills: `system_echo`, `math_add`, `text_stats`
- Skill management/execution APIs
- Skill Registry frontend view

## Quick start

The project remains Docker Compose based. Local end-to-end validation is intentionally deferred until all planned phases are implemented.

Configuration templates remain in `.env.example`. Real model execution requires:

```text
DEEPSEEK_API_KEY=<your-key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

## APIs

Agent definitions:

```text
GET  /api/agents
POST /api/agents
GET  /api/agents/{agent_id}
POST /api/agents/{agent_id}/versions
POST /api/agents/{agent_id}/versions/{version_id}/activate
POST /api/agents/{agent_id}/preview
```

Skill Registry:

```text
GET  /api/skills
POST /api/skills
GET  /api/skills/{skill_id}
POST /api/skills/{skill_id}/versions
POST /api/skills/{skill_id}/versions/{version_id}/activate
POST /api/skills/{skill_id}/execute
```

Example Agent version capability declaration:

```json
{
  "system_instructions": "Use tools when useful.",
  "model_provider": "deepseek",
  "model_name": "deepseek-chat",
  "skills": ["math_add", "text_stats"]
}
```

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
```

## Runtime invariants

1. LLM output is untrusted.
2. The model sees only explicitly bound Skills.
3. Tool arguments are JSON Schema validated before execution.
4. Required permissions are checked outside the model.
5. Provider adapters are registered by the application, not chosen as arbitrary code paths by the model.
6. Tool timeouts and retries are bounded.
7. Tool outputs are schema validated before returning to the model.
8. Side-effect metadata is platform-controlled.
9. Existing AgentVersions continue pointing to concrete SkillVersions even when a Skill's active version later changes.
10. Durable Run semantics remain the responsibility of Phase 5.

## Technology stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Persistence | SQLAlchemy 2, Alembic, PostgreSQL 16 |
| Auth | JWT, Argon2, RBAC |
| Runtime cache | Redis 7 |
| Model provider | DeepSeek |
| Model transport | httpx |
| Skill schema | JSON Schema Draft 2020-12 |
| Frontend | Vue 3, TypeScript, Element Plus |
| Quality | pytest, Ruff, mypy, GitHub Actions |

## Development roadmap

```text
Phase 0  ✅ Architecture & Contracts
Phase 1  ✅ Engineering Skeleton
Phase 2  ✅ Authentication + RBAC
Phase 3  ✅ Agent Harness
Phase 4  ✅ Tool / Skill Registry
Phase 5  ⏭ Durable Agent Runtime
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
- [Phase 4 Tool / Skill Registry](docs/10-phase4-tool-skill-registry.md)

## License

A license will be selected before the first public release. Until then, repository contents are provided for source review and project development.
