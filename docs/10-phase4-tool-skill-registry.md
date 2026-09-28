# 10 — Phase 4 Tool / Skill Registry

## Status

**Implemented**

Phase 4 converts the Phase 3 Agent Harness from model-only execution into governed tool-using execution.

## Runtime flow

```text
AgentVersion
    |
    +--> bound SkillVersions only
    |
    v
ModelRequest(tools=...)
    |
    v
DeepSeek
    |
    +--> text response ----------------------------+
    |                                             |
    +--> structured tool call                     |
             |                                    |
             v                                    |
      Resolve bound SkillVersion                  |
             |                                    |
      JSON Schema input validation                |
             |                                    |
      Permission metadata check                   |
             |                                    |
      Provider adapter                            |
             |                                    |
      Timeout / bounded retry                     |
             |                                    |
      JSON Schema output validation               |
             |                                    |
      Structured Skill result                     |
             |                                    |
             +------ returned to model ------------+
```

LLM tool arguments are always treated as untrusted input.

## Persistence

### Skill

Stable logical capability:

- UUID
- canonical tool-safe name
- description
- provider type
- status
- active version

### SkillVersion

Concrete immutable-style contract:

- input JSON Schema
- output JSON Schema
- required permissions
- side-effect classification
- timeout
- maximum attempts
- provider configuration

### AgentVersion ↔ SkillVersion

`agent_version_skills` stores explicit capability bindings.

An AgentVersion receives only those concrete SkillVersions. The model is not shown the entire platform registry.

## Provider adapters

Phase 4 implements the `SkillProviderAdapter` boundary and a local adapter.

```text
SkillExecutor
    |
    v
SkillProviderRegistry
    |
    +--> local -> LocalSkillAdapter
    |
    +--> MCP / REST / sandbox in later phases
```

The local adapter resolves only registered handler identifiers. Arbitrary Python module names, shell commands, or model-produced code are not executed.

## Seeded safe local Skills

Three read-only Skills are seeded idempotently:

| Skill | Purpose |
| --- | --- |
| `system_echo` | structured echo |
| `math_add` | add two numeric values |
| `text_stats` | count characters, words and lines |

All require `skill:execute`.

## Validation

The executor uses JSON Schema Draft 2020-12.

Before execution:

1. resolve the exact bound SkillVersion;
2. verify required permissions;
3. validate model-produced arguments;
4. resolve the registered provider adapter;
5. enforce timeout/retry limits.

After execution, output is validated against the declared output schema.

Unknown fields can be rejected with `additionalProperties: false`.

## Error envelope

Skill failures are normalized into structured results:

```json
{
  "ok": false,
  "error": {
    "code": "SKILL_INPUT_VALIDATION",
    "retryable": false,
    "message": "..."
  }
}
```

Implemented categories include:

- `SKILL_NOT_BOUND`
- `SKILL_PERMISSION_DENIED`
- `SKILL_INPUT_VALIDATION`
- `SKILL_OUTPUT_VALIDATION`
- `SKILL_PROVIDER_CONFIGURATION`
- `SKILL_PROVIDER_ERROR`
- `SKILL_PROVIDER_RETRYABLE`
- `SKILL_TIMEOUT`

Only retryable failures can consume further attempts.

## Side-effect metadata

Each SkillVersion declares one of:

- `READ_ONLY`
- `REVERSIBLE_WRITE`
- `IRREVERSIBLE_WRITE`
- `SENSITIVE`

Phase 4 records and propagates this classification. Phase 12 Policy Engine uses it to make ALLOW / DENY / REQUIRE_APPROVAL decisions.

## Model tool calling

DeepSeek requests now support normalized tool definitions.

A provider tool call is normalized to:

```text
ModelToolCall
├── id
├── name
└── arguments
```

The Harness performs a bounded model/tool loop. Skill results are serialized into `tool` messages and returned to the model for final synthesis.

Maximum tool rounds are bounded by the Harness.

## RBAC

Phase 4 adds:

- `skill:manage`
- existing `skill:read`
- existing `skill:execute`

The generic endpoint permission is only the first gate. Every SkillVersion can require additional atomic permissions.

## Skill API

```text
GET  /api/skills
POST /api/skills
GET  /api/skills/{skill_id}
POST /api/skills/{skill_id}/versions
POST /api/skills/{skill_id}/versions/{version_id}/activate
POST /api/skills/{skill_id}/execute
```

Manual execute is useful for administration and contract testing. Agent execution uses the same SkillExecutor.

## Agent binding

Agent creation/version creation now accepts:

```json
{
  "skills": ["math_add", "text_stats"]
}
```

Names are resolved to the current active concrete SkillVersions when the AgentVersion is created. Later changes to a Skill's active version do not silently rewrite an existing AgentVersion.

This preserves reproducibility.

## Testing

Automated tests verify:

- input schema validation;
- output schema validation path;
- permission enforcement;
- retryable failure retry;
- safe local execution;
- model selects a bound Skill;
- result is returned to the model;
- token usage is accumulated across model rounds.

Docker Compose CI verifies:

- migration 0004;
- RBAC seed;
- safe Skill seed;
- Skill registry API;
- manual `math_add` execution;
- AgentVersion Skill binding;
- Agent version switching;
- frontend health.

No real DeepSeek credential is required by CI.

## Exit criteria

Phase 4 is complete when:

1. Skill / SkillVersion are versioned database entities.
2. AgentVersion binds concrete SkillVersions.
3. only bound Skills are exposed to the model.
4. tool arguments and outputs are schema validated.
5. Skill permission metadata is enforced outside the model.
6. local execution occurs only through registered adapters/handlers.
7. timeout and bounded retry envelopes exist.
8. model tool calls are normalized by the provider layer.
9. Skill results can return to the model for final synthesis.
10. automated tests prove the complete bound-Skill loop.
