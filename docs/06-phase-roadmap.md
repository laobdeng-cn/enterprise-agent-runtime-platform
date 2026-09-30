# 06 — Development Roadmap

The project is built from runtime foundations upward. Each phase must leave the system in a testable state.

## Phase 0 — Architecture & Contracts

**Goal:** define stable boundaries before implementation.

Deliverables:

- repository structure;
- product scope and non-goals;
- logical architecture;
- core domain model;
- Agent Run lifecycle;
- Skill contract;
- RBAC/security model;
- ADRs;
- phased acceptance criteria.

**Exit criteria:** design docs are internally consistent and no production runtime implementation is required.

---

## Phase 1 — Engineering Skeleton

**Goal:** establish a reproducible local environment.

Implement:

- Python 3.12 backend project;
- FastAPI health endpoint;
- Vue 3/TypeScript frontend;
- PostgreSQL 16;
- Redis;
- Docker Compose;
- Pydantic settings;
- SQLAlchemy/Alembic bootstrap;
- pytest baseline;
- lint/format tooling.

**Exit criteria:** `docker compose up` starts frontend, backend, PostgreSQL and Redis; health checks pass.

---

## Phase 2 — Authentication & RBAC

Implement:

- User/Role/Permission persistence;
- login and JWT;
- current-user endpoint;
- permission dependency/service;
- initial role seed;
- tests for permission allow/deny.

**Exit criteria:** protected API actions are deterministically authorized.

---

## Phase 3 — Agent Harness

Implement:

- Agent/AgentVersion models;
- model-provider abstraction;
- DeepSeek provider;
- Harness runner/lifecycle hooks;
- basic context package;
- model-call normalization;
- no direct provider calls from API handlers.

**Exit criteria:** a versioned Agent can execute a basic DeepSeek request through the Harness.

---

## Phase 4 — Tool / Skill Registry

Implement:

- Skill/SkillVersion models;
- registry;
- schema validation;
- local skill adapter;
- permission metadata;
- timeout/retry envelope;
- initial safe skills;
- basic dynamic skill binding.

**Exit criteria:** the model can select a bound Skill; arguments are validated/authorized; result returns to the model.

---

## Phase 5 — Durable Agent Runtime

Implement:

- AgentRun/RunStep/ToolCall/Checkpoint persistence;
- explicit state machine;
- start/pause/resume/cancel;
- bounded retry;
- SSE run events;
- LangGraph checkpointer integration where appropriate.

**Exit criteria:** a Run survives backend restart from a durable checkpoint and exposes its step history.

**Milestone:** Agent Runtime MVP.

---

## Phase 6 — Workspace & Artifacts

Implement:

- per-Run workspace metadata;
- safe path resolver;
- file skills;
- artifact metadata/download;
- size/type policies;
- traversal/symlink security tests.

**Exit criteria:** an Agent can read/write its own workspace and produce artifacts without escaping its boundary.

---

## Phase 7 — Docker Sandbox

Implement:

- sandbox manager;
- ephemeral Python container;
- CPU/memory/time limits;
- controlled workspace mount;
- network policy;
- structured execution result;
- cleanup;
- adversarial tests.

**Exit criteria:** an Agent can analyze a workspace file with Python and return generated artifacts inside enforced limits.

---

## Phase 8 — Memory

**Status: implemented.**

Implemented:

- Conversation / Task / Long-term / Semantic Memory types;
- USER / AGENT / RUN scopes;
- TTL, soft deletion, importance, source and metadata;
- fingerprint deduplication;
- deterministic English/CJK relevance retrieval;
- MemoryRetriever / MemoryWriter boundaries;
- `memory_search` / `memory_write` Skills;
- Runtime retrieval before model invocation;
- safe untrusted Memory context injection;
- Memory Inspector.

**Exit criteria:** relevant durable Memory is retrieved for a later Run without blindly replaying all history, and retained content cannot override system/RBAC/tool policy.

---

## Phase 9 — Context Engineering

**Status: implemented.**

Implemented:

- token-budgeted Context Builder;
- explicit Token Budget Manager;
- provider-independent token estimation;
- AgentVersion `context_policy` overrides;
- mandatory system/current-user preservation;
- additional-context and Memory compression;
- runtime tool-history compression;
- permission-first relevant Skill selection;
- bounded Skill-definition injection;
- persisted per-component ContextTrace metadata;
- `run.context_prepared` event;
- Context Inspector API and UI.

**Exit criteria:** every model request can explain which context components were included, compressed, or excluded and why, while authoritative input is never silently truncated.

---

## Phase 10 — MCP & Enterprise Data

**Status: implemented.**

Implemented:

- durable MCPServer / MCPTool registry;
- Streamable HTTP MCP client boundary;
- protected server health/discovery APIs;
- MCP Skill adapter;
- remote schema validation and SkillVersion synchronization;
- stale capability detection;
- platform-owned connector permission mapping;
- platform-owned side-effect policy with SENSITIVE safe default;
- current-principal authorization re-check before remote execution;
- first-party knowledge, experiment and enterprise MCP servers;
- MCP Server Registry UI;
- Docker Compose MCP integration testing.

**Exit criteria:** the platform discovers first-party MCP capabilities, persists/synchronizes them into governed Skills, completes a real MCP-backed Skill round trip, and includes a relevant MCP Skill in Context Engineering without allowing the remote server to grant authorization.

---

## Phase 11 — Workflow & Multi-Agent

Implement:

- Workflow/WorkflowVersion/Node models;
- Planner, Executor and Reviewer roles;
- DAG dependencies;
- conditional routing;
- controlled parallelism;
- node retries/timeouts;
- workflow checkpoints.

**Exit criteria:** a multi-step DAG with at least three specialized execution roles completes deterministically and is inspectable.

---

## Phase 12 — Human-in-the-loop & Policy Engine

Implement:

- PolicyDecision;
- Approval persistence/API/UI;
- LangGraph interrupt/resume integration;
- approval freshness;
- high-risk tool policies.

**Exit criteria:** a protected side effect pauses the Run, survives restart, resumes only after valid approval, then executes once.

**Milestone:** Enterprise Agent Platform.

---

## Phase 13 — Trace & Observability

Implement:

- TraceSpan hierarchy;
- model/tool/MCP/sandbox/workflow spans;
- latency/token/retry/error data;
- trace timeline UI;
- sensitive-field redaction.

**Exit criteria:** one Run can be debugged end-to-end from a single trace view.

---

## Phase 14 — Agent Evaluation & Regression

Implement:

- EvaluationCase/Dataset/Run/Result;
- task success metric;
- tool selection/argument accuracy;
- workflow completion;
- permission violation rate;
- sandbox success;
- latency/token/cost;
- baseline vs candidate comparison.

**Exit criteria:** a prompt/agent change can be evaluated against a fixed dataset before promotion.

**Milestone:** Production-oriented Agent Runtime.

---

## Phase 15 — Enterprise Demo & Hardening

Implement the Materials R&D reference scenario:

- experiment data source;
- knowledge evidence;
- Python analysis;
- generated charts/report;
- candidate experiment proposal;
- reviewer;
- approval;
- MCP side effect;
- complete trace;
- regression suite.

Hardening:

- documentation;
- deployment scripts;
- seed/demo data;
- integration tests;
- security tests;
- polished console flows.

**Exit criteria:** a clean-machine deployment can run the documented end-to-end demonstration.
