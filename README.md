# Enterprise Agent Runtime Platform

> 企业级智能体运行与自动化平台 — a production-oriented runtime for building, executing, governing, and evaluating enterprise AI agents.

[![Phase](https://img.shields.io/badge/phase-0%20architecture-blue)](#development-roadmap)
[![Python](https://img.shields.io/badge/Python-3.12+-informational)](#planned-technology-stack)
[![FastAPI](https://img.shields.io/badge/FastAPI-planned-informational)](#planned-technology-stack)
[![LangGraph](https://img.shields.io/badge/LangGraph-planned-informational)](#planned-technology-stack)
[![MCP](https://img.shields.io/badge/MCP-planned-informational)](#planned-technology-stack)

## Overview

Enterprise Agent Runtime Platform is designed to move beyond a simple LLM chat application. The platform will provide a controlled execution environment in which an agent can:

- plan and execute multi-step business tasks;
- discover and call tools / skills with schema validation;
- connect to enterprise data and services through MCP, APIs, databases, and knowledge bases;
- manage conversation, task, and long-term memory;
- build context under explicit token budgets;
- execute code inside an isolated sandbox and per-run workspace;
- pause for human approval before sensitive actions;
- resume from checkpoints after interruption;
- coordinate multiple specialized agents;
- expose full execution traces, metrics, and regression evaluation.

The project is being developed incrementally. **Phase 0 defines architecture and contracts only**. Runtime code, DeepSeek integration, databases, and deployable services begin in later phases.

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

## Repository Layout

```text
enterprise-agent-runtime-platform/
├── backend/          # FastAPI runtime service (Phase 1+)
├── frontend/         # Vue 3 + TypeScript console (Phase 1+)
├── mcp_servers/      # First-party MCP servers (Phase 10+)
├── sandbox/          # Isolated execution runtime (Phase 7+)
└── docs/
    ├── 00-product-scope.md
    ├── 01-system-architecture.md
    ├── 02-domain-model.md
    ├── 03-agent-run-lifecycle.md
    ├── 04-tool-skill-model.md
    ├── 05-rbac-security-model.md
    ├── 06-phase-roadmap.md
    └── adr/
```

## Planned Technology Stack

| Layer | Planned choice |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Agent orchestration | LangGraph |
| LLM | DeepSeek API through an internal model-provider abstraction |
| Protocol | Model Context Protocol (MCP) |
| Primary database | PostgreSQL 16 |
| Vector storage | pgvector initially; Qdrant can be added if justified by scale |
| Runtime state / cache | Redis |
| Sandbox | Docker Engine |
| Frontend | Vue 3, TypeScript, Vite, Element Plus |
| Streaming | Server-Sent Events (SSE) |
| Deployment | Docker Compose first |
| Tests | pytest, pytest-asyncio |
| Observability | First-party trace model; OpenTelemetry/Langfuse optional later |

Technology decisions are recorded as ADRs under [docs/adr](docs/adr).

## Domain Vocabulary

The project uses a small set of stable concepts:

- **Agent** — a versioned definition describing model policy, instructions and capabilities.
- **Skill** — a callable capability with a machine-readable input/output contract and authorization requirements.
- **Run** — one execution instance of an agent or workflow.
- **RunStep** — one durable step inside a run.
- **ToolCall** — one concrete request to invoke a skill/tool.
- **Workspace** — isolated file scope owned by a run.
- **Artifact** — a user-visible or machine-consumable output generated by a run.
- **Memory** — durable or retrievable state that may be injected into future context.
- **Workflow** — an explicit graph of tasks, dependencies and routing rules.
- **Approval** — a human decision required before a protected action.
- **TraceSpan** — one observable unit of execution.
- **EvaluationRun** — a regression/evaluation execution over defined cases.

See [docs/02-domain-model.md](docs/02-domain-model.md) for ownership and relationships.

## Safety and Governance Invariants

The architecture is built around several non-negotiable rules:

1. **The LLM never grants permissions.** Authorization is evaluated by a deterministic policy layer.
2. **Tool input is validated before execution.** Model output is treated as untrusted input.
3. **Sensitive actions may require human approval.**
4. **Sandboxed execution has explicit CPU, memory, time, network and filesystem boundaries.**
5. **A run can only access its authorized workspace and enterprise resources.**
6. **Every externally meaningful action must be traceable.**
7. **Retry is bounded and idempotency must be considered for side-effecting tools.**
8. **Run state transitions are explicit and persisted.**

## Development Roadmap

The planned sequence deliberately builds runtime foundations before multi-agent demos:

```text
Phase 0  Product scope, architecture, contracts, ADRs
Phase 1  Engineering skeleton + local infrastructure
Phase 2  Authentication + RBAC
Phase 3  Agent Harness
Phase 4  Tool / Skill Registry
Phase 5  Agent Runtime + durable run lifecycle
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

Detailed acceptance criteria are in [docs/06-phase-roadmap.md](docs/06-phase-roadmap.md).

## Current Status

**Phase 0 — Architecture & Contracts**

Current deliverables:

- product scope and explicit non-goals;
- system boundaries and component architecture;
- core domain model;
- Agent Run state machine;
- Tool / Skill invocation contract;
- RBAC and security model;
- architecture decision records;
- phased implementation roadmap.

No production runtime code has intentionally been added yet.

## Documentation

Start here:

1. [Product Scope](docs/00-product-scope.md)
2. [System Architecture](docs/01-system-architecture.md)
3. [Domain Model](docs/02-domain-model.md)
4. [Agent Run Lifecycle](docs/03-agent-run-lifecycle.md)
5. [Tool / Skill Model](docs/04-tool-skill-model.md)
6. [RBAC & Security Model](docs/05-rbac-security-model.md)
7. [Phase Roadmap](docs/06-phase-roadmap.md)

## License

A license will be selected before the first public release. Until then, repository contents are provided for source review and project development.
