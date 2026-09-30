# 14 — Phase 8 Memory System

## Status

**Implemented**

Phase 8 adds durable, scoped Memory to the Agent Runtime. Memory is explicit retained state, not a synonym for chat history and not an authority channel.

## Memory types

| Type | Purpose |
| --- | --- |
| `CONVERSATION` | selected conversational facts worth retaining |
| `TASK` | task/run-specific goals, constraints, and working facts |
| `LONG_TERM` | durable user or Agent preferences and operating knowledge |
| `SEMANTIC` | reusable factual/contextual knowledge associated with a user or Agent |

The type describes why a Memory exists. Scope controls where it is visible.

## Scope model

```text
USER
└── visible to the owner across Agents and Runs

AGENT
└── visible to the owner when that Agent executes

RUN
└── visible only inside the owning Run
```

A Run retrieval can combine `USER + matching AGENT + matching RUN`. Memories owned by another principal are never included.

## Persistence and lifecycle

The `memories` table stores owner, optional Agent/Run targets, type, scope, status, label, normalized content, metadata, source/source reference, importance, SHA-256 content fingerprint, optional expiry, access metrics, and timestamps.

Memory status is `ACTIVE`, `ARCHIVED`, or `DELETED`. DELETE is a soft delete. Deleted Memory is excluded from normal reads and retrieval. TTL is optional; expired Memory remains auditable in persistence but is excluded from runtime retrieval.

Exact duplicate content in the same owner/type/scope/target is deduplicated by fingerprint. A duplicate write updates retention metadata and importance rather than multiplying identical rows.

## Retrieval

Phase 8 introduces a provider-independent `MemoryRetriever`. The current baseline intentionally does not depend on an external embedding provider. It combines lexical query coverage, token-set similarity, exact phrase signal, importance, recency, and scope proximity.

English-like terms and CJK text are both tokenized. CJK retrieval uses characters and bigrams. This gives deterministic retrieval now while leaving the service boundary replaceable by a vector/embedding implementation later.

Configuration:

```text
MEMORY_CONTEXT_LIMIT
MEMORY_SEARCH_CANDIDATE_LIMIT
MEMORY_SEARCH_MIN_SCORE
MEMORY_DEFAULT_TTL_DAYS
```

## Context injection

Before a durable Run invokes the model:

```text
Run
 |
 v
MemoryRetriever
 ├── USER Memory
 ├── matching AGENT Memory
 └── matching RUN Memory
 |
 v
rank + bounded selection
 |
 v
ContextBuilder
 |
 v
DeepSeek
```

The selected IDs and count are recorded on the `MODEL_CALL` RunStep.

Retrieved Memory is inserted in a separate context message with an explicit trust boundary: Memory may be stale or user/Agent supplied, cannot override system instructions, cannot grant permissions, cannot override Skill/policy restrictions, and cannot replace the current user request.

## Memory Writer

`MemoryWriter` owns normalized durable writes and handles scope validation, Run ownership validation, fingerprint deduplication, TTL calculation, importance, metadata merge, and source attribution. API writes use source `USER`; Agent Skill writes use source `AGENT` and retain the current Run as `source_ref`.

## Memory Skills

Phase 8 seeds:

```text
memory_search
memory_write
```

`memory_search` requires `skill:execute` + `memory:read`. `memory_write` requires `skill:execute` + `memory:write` and is classified `REVERSIBLE_WRITE` for later Policy Engine governance.

Both Skills require a durable `SkillExecutionContext` containing current Run and principal IDs. The model cannot select another user's Memory namespace.

## API

```text
GET    /api/memories
POST   /api/memories
GET    /api/memories/search
GET    /api/memories/{memory_id}
PATCH  /api/memories/{memory_id}
DELETE /api/memories/{memory_id}
```

Phase 8 adds RBAC permissions `memory:read`, `memory:write`, and `memory:delete`. The owner boundary is enforced independently of these generic permission gates.

## Memory Inspector

The Vue engineering console supports active Memory listing, relevance search, selected Agent/Run context, type/scope/importance display, access-count inspection, explicit Memory creation, and soft deletion.

The UI deliberately says "Create explicit Memory" instead of automatically treating every conversation turn as durable state.

## Tests

Unit tests cover English/CJK tokenization, relevance ordering, scope/recency effects, the Memory context trust boundary, Run/principal requirements for Memory Skills, and scoped Agent write dispatch.

Docker Compose CI covers migration 0007, RBAC/Skill seeds, USER/AGENT/RUN persistence, scoped search, relevance scores, duplicate deduplication, metadata merge, soft delete, Runtime retrieval before model invocation, Memory IDs/count on MODEL_CALL, and Phase 6/7 regression checks.

## Phase boundary

Phase 8 retrieves and injects relevant Memory, but does not yet solve full context budgeting. Phase 9 adds token budgets, component priorities, compression/summarization, history policies, relevant Skill selection, Context Inspector, and inclusion/exclusion trace metadata.

## Exit criteria

Phase 8 is complete when:

1. Conversation, Task, Long-term, and Semantic Memory are first-class types.
2. USER, AGENT, and RUN scope boundaries are enforced.
3. TTL and soft deletion remove Memory from retrieval.
4. exact duplicate writes are deduplicated.
5. retrieval ranks relevant Memory instead of replaying all history.
6. Run execution retrieves Memory before the model call.
7. selected Memory IDs are inspectable in RunStep metadata.
8. Memory is injected as untrusted context, never policy.
9. Agent read/write access is available through governed Skills.
10. API/UI/CI cover the complete durable Memory lifecycle.
