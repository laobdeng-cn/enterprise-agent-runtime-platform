# 15 — Phase 9 Context Engineering

## Status

**Implemented**

Phase 9 turns context construction from simple prompt concatenation into a governed, inspectable pipeline.

The runtime now decides what enters a model request under an explicit budget and records why each component was included, compressed, or excluded.

## Design goals

Context Engineering must preserve four properties:

1. system instructions and the current user request remain authoritative;
2. durable Memory and external context remain untrusted data;
3. the model sees only a bounded, relevant subset of authorized Skills;
4. every inclusion/exclusion decision is inspectable.

The platform does not silently truncate system instructions or the current user request. If authoritative input alone cannot fit the configured budget, execution fails explicitly.

## Pipeline

```text
AgentVersion + Run
        |
        +--> System Instructions
        +--> Current User Request
        +--> Additional Context
        +--> Relevant Memory
        +--> Bound Skills
        |
        v
Token Budget Manager
        |
        +--> mandatory authority budget
        +--> additional-context budget
        +--> memory budget
        +--> Skill-definition budget
        +--> runtime tool-history reserve
        |
        v
Priority + Relevance
        |
        +--> Context Compressor
        +--> Permission-aware Skill Selector
        |
        v
ContextPackage
        |
        +--> messages
        +--> selected Skill names
        +--> ContextTrace
        |
        v
Agent Harness
        |
        v
DeepSeek
```

## Token Budget Manager

The default policy is:

```text
CONTEXT_TOKEN_BUDGET=32768
CONTEXT_RESERVED_OUTPUT_TOKENS=4096
CONTEXT_RUNTIME_RESERVE_TOKENS=4096
CONTEXT_ADDITIONAL_TOKENS=8192
CONTEXT_MEMORY_TOKENS=6144
CONTEXT_SKILL_TOKENS=4096
CONTEXT_SKILL_LIMIT=8
CONTEXT_ITEM_MAX_TOKENS=2048
CONTEXT_FALLBACK_SKILL_COUNT=3
```

Each AgentVersion may override supported values through its existing `context_policy` JSON.

The budget is divided into:

```text
context window
  - reserved model output
  = model input budget

model input budget
  - runtime reserve for tool-result history
  = initial context budget
```

The Token Budget Manager then allocates flexible capacity to additional context, Memory, and Skill definitions. Unused additional-context capacity can flow to Memory, and remaining flexible capacity can flow to Skills.

## Token estimation

Phase 9 uses a deterministic provider-independent estimator.

It counts a conservative mixture of:

- CJK characters;
- Latin words;
- long-word character adjustment;
- punctuation;
- message/tool serialization overhead.

This is intentionally an **estimate**, not a claim of exact DeepSeek tokenizer parity.

The abstraction can later be replaced by a provider tokenizer without changing the Context Builder contract.

## Priority rules

Context decisions expose explicit priorities:

| Component | Priority | Rule |
| --- | ---: | --- |
| System instructions | 100 | mandatory, never silently truncated |
| Current user request | 100 | mandatory, never silently truncated |
| Additional context | 90 | compress/exclude under budget |
| Relevant Memory | 80 | rank by retrieval score/importance, then compress/exclude |
| Skill definitions | 70 | permission filter first, then relevance/budget selection |
| Tool-result history | runtime | compressed only when the request approaches the model input limit |

Memory cannot override system instructions, RBAC, Skill policy, or the current request.

## Compression

`ContextCompressor` is a deterministic extractive baseline.

For oversized non-authoritative context it:

1. splits text into sentence/line segments;
2. scores segments against the current user request;
3. preserves relevant, first, and final segments when possible;
4. falls back to bounded truncation if no complete segment can fit.

The compressor is used for:

- additional context;
- oversized Memory entries;
- tool-result history when later tool rounds exceed the runtime budget.

No extra model call is required for compression, so CI and offline development do not require a DeepSeek API key.

## Relevant Skill selection

The model no longer automatically receives every bound Skill.

The selector applies this sequence:

```text
AgentVersion bound Skills
        |
        v
current principal permissions
        |
        v
query relevance ranking
        |
        v
Skill count limit
        |
        v
Skill token budget
        |
        v
selected tool definitions
```

Permission filtering happens before relevance ranking.

A Skill excluded from the model request is also excluded from the SkillExecutor's allowed bound-version set for that model round. This prevents a provider response from invoking a hidden capability that was not exposed in the request.

When no query-relevant Skill exists, the selector can expose a small configurable fallback set of read-only Skills rather than injecting the entire registry.

## Tool-history control

Initial context reserves tokens for later tool rounds.

Before every model call, the Harness re-estimates:

```text
messages + tool definitions
```

If tool-result history pushes the request over the input budget, only tool-result content is compressed. System instructions and the current user request are not altered.

If the request still cannot fit after compressing tool results, the Harness raises an explicit Context budget error.

## Context trace

Every Context plan records:

- context window;
- output reserve;
- runtime reserve;
- initial input budget;
- estimated message tokens;
- estimated tool-definition tokens;
- used/remaining tokens;
- selected/excluded Skills;
- compression count;
- effective Context policy;
- per-component decision metadata.

Each decision includes:

```text
component_id
kind
label
status
reason
priority
original_tokens
used_tokens
score
preview
```

Status is one of:

```text
included
compressed
excluded
```

## Durable Run integration

Before a Run invokes DeepSeek:

```text
Memory retrieval
      |
      v
Harness.prepare_context()
      |
      v
ContextTrace persisted on MODEL_CALL.input_data
      |
      v
run.context_prepared event
      |
      v
Harness.run(prepared_context=...)
```

The persisted MODEL_CALL input contains:

- included Memory IDs/count;
- selected Skill names;
- complete ContextTrace metadata.

This remains available even if the provider call fails, which makes pre-model context planning debuggable.

## Context Inspector API

```text
GET /api/runs/{run_id}/context
```

For a PENDING Run, the endpoint returns:

```text
source = preview
```

It computes the Context plan without incrementing Memory access counters.

After execution has prepared a model call, the endpoint returns the exact persisted planning metadata:

```text
source = persisted
```

## Context Inspector UI

The Vue console now exposes a Context action for every Run.

The inspector shows:

- preview vs persisted source;
- initial/used/remaining token budget;
- runtime reserve;
- selected Skills;
- every component's type/status;
- relevance score when available;
- used/original estimated tokens;
- inclusion/exclusion reason;
- content preview.

## AgentVersion context policy

No schema migration was needed.

Phase 3 already defined:

```text
agent_versions.context_policy JSON
```

Phase 9 makes this field operational.

Example:

```json
{
  "context_window_tokens": 8192,
  "reserved_output_tokens": 1024,
  "runtime_reserve_tokens": 1024,
  "additional_context_tokens": 1200,
  "memory_tokens": 1000,
  "skill_tokens": 1800,
  "skill_limit": 4,
  "item_max_tokens": 512,
  "fallback_skill_count": 2
}
```

## Testing

Unit tests validate:

- authoritative input preservation;
- explicit overflow failure;
- additional-context compression;
- Memory-aware budgeting;
- permission-first Skill selection;
- relevant Skill selection;
- runtime tool-result compression.

Docker Compose CI additionally validates:

- Context preview on PENDING Runs;
- AgentVersion context-policy overrides;
- token-budget invariants;
- relevant workspace Skill selection;
- oversized additional-context compression;
- persisted ContextTrace after Run start;
- Memory decision metadata;
- `run.context_prepared` SSE event;
- all earlier Workspace, Sandbox, Memory, RBAC and durable-runtime regressions.

## Phase boundary

Phase 9 controls what the Harness sends to the model.

Phase 10 will add MCP and enterprise data sources. MCP capabilities will enter the same Context/Skill selection boundary instead of bypassing it.

## Exit criteria

Phase 9 is complete when:

1. every model request is planned under an explicit input/output/runtime budget;
2. system instructions and the current user request are never silently truncated;
3. lower-priority context can be compressed or excluded deterministically;
4. relevant Memory is bounded by the Context budget;
5. permissions are applied before Skill relevance selection;
6. only selected Skills are exposed and executable for the model round;
7. growing tool-result history cannot silently overflow the request;
8. a ContextTrace explains every inclusion/exclusion decision;
9. PENDING Runs can be previewed through the Context Inspector;
10. executed Runs persist the exact pre-model planning metadata.
