# 00 — Product Scope

## 1. Problem Statement

Many LLM applications stop at conversational response generation. Enterprise agents must additionally execute actions, maintain durable state, obey authorization, work with files and data, recover from failures, and expose enough evidence to debug and evaluate behavior.

This project provides the runtime and governance layer between an LLM's reasoning and enterprise systems.

## 2. Product Goal

Given an authorized user goal, the platform should eventually be able to:

1. create a durable execution Run;
2. assemble relevant instructions, state, memory and capabilities;
3. let the model plan or select the next action;
4. validate and authorize that action;
5. invoke a local Skill, MCP capability, enterprise API, database query or sandbox task;
6. persist step results and checkpoints;
7. pause for approval when policy requires it;
8. resume safely;
9. produce artifacts and a final result;
10. expose trace and evaluation data for the entire execution.

## 3. Primary Personas

### Platform Administrator

Configures users, roles, permissions, agents, skills and MCP servers.

### Agent Developer

Builds agent definitions, workflows and tool integrations, then observes traces and runs evaluations.

### Business User

Submits goals, provides files, reviews outputs and approves protected actions when authorized.

### Reviewer / Approver

Inspects pending high-risk operations and approves, rejects or requests modifications.

## 4. Phase-15 Reference Scenario

The reference business demonstration will be a **Materials R&D Agent**.

Example user goal:

> Analyze recent perovskite thin-film experiment results, identify variables associated with efficiency decline, combine internal experiment data with evidence from the knowledge base, and propose the next experiment. Create the experiment task only after approval.

This scenario forces the runtime to demonstrate data access, knowledge retrieval, code execution, artifacts, tool calling, review, approval and traceability without making the platform itself domain-specific.

## 5. Core Functional Scope

### Agent Definition

- versioned instructions and model configuration;
- allowed/default skill sets;
- context policy;
- workflow association;
- lifecycle state.

### Skill System

- registry and versioning;
- structured input/output contracts;
- permission requirements;
- timeout/retry policy;
- side-effect classification;
- execution metadata.

### Durable Runtime

- Run and RunStep persistence;
- explicit lifecycle;
- pause/resume/cancel/retry;
- checkpointing;
- idempotency support for side-effecting actions.

### Workspace and Artifacts

- per-run logical isolation;
- file operations through runtime-managed APIs;
- generated artifact metadata;
- bounded sizes and validated paths.

### Sandbox

- isolated Python execution;
- resource/time limits;
- controlled workspace access;
- structured outputs.

### Memory and Context

- conversation memory;
- task memory;
- long-term memory;
- semantic retrieval;
- context assembly under a token budget;
- inspection of what entered model context.

### Enterprise Connectivity

- MCP;
- REST APIs;
- controlled database access;
- knowledge retrieval;
- health/status inspection for capability providers.

### Workflow and Multi-Agent

- explicit task graph;
- dependency and conditional routing;
- controlled parallelism;
- specialized agents with clear responsibilities;
- reviewer/verification stages.

### Governance

- authentication;
- RBAC;
- deterministic policy enforcement;
- approval gates;
- audit records.

### Observability and Evaluation

- trace spans for model/tool/runtime operations;
- latency, retry and token metadata;
- evaluation datasets;
- task/tool/workflow/policy metrics;
- baseline vs. candidate regression comparison.

## 6. Non-Goals

The following are explicitly outside initial scope:

- training or fine-tuning foundation models;
- building a general-purpose container orchestration platform;
- replacing enterprise IAM;
- allowing unrestricted host shell access;
- giving the LLM authority to grant permissions;
- implementing arbitrary browser automation in the first release;
- supporting every model provider before the DeepSeek path is stable;
- building a visual no-code workflow editor before the runtime graph is proven.

## 7. Quality Attributes

The platform prioritizes:

1. **Correctness** — validated contracts and explicit state transitions.
2. **Control** — deterministic policy outside the model.
3. **Isolation** — workspace and sandbox boundaries.
4. **Recoverability** — durable checkpoints and bounded retries.
5. **Traceability** — every meaningful operation is inspectable.
6. **Testability** — runtime units are separable from HTTP and model providers.
7. **Extensibility** — adapters for models, skills and MCP servers.
8. **Evaluability** — behavior changes can be regression-tested.

## 8. Definition of Product Success

The project is successful when the reference scenario can execute end-to-end while demonstrating:

- one durable Run with multiple steps;
- dynamic tool/skill selection;
- at least one MCP call;
- at least one sandbox execution;
- memory/context construction;
- one policy-protected approval;
- checkpoint resume after approval;
- generated artifact(s);
- full execution trace;
- automated evaluation over a repeatable case set.
