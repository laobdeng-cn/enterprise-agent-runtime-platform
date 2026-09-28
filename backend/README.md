# Backend

FastAPI control plane and Agent execution backend for Enterprise Agent Runtime Platform.

## Current Phase 4 contents

- JWT authentication + RBAC
- versioned Agent / AgentVersion
- DeepSeek ModelProvider adapter
- Agent Harness lifecycle
- versioned Skill / SkillVersion
- AgentVersion ↔ concrete SkillVersion binding
- JSON Schema validation
- Skill provider registry
- local Skill adapter
- permission-aware SkillExecutor
- timeout and bounded retry envelope
- model tool-call normalization
- bounded model/tool loop
- Skill CRUD/version/execute APIs
- Alembic migrations through 0004

## Safe local Skills

Startup seed creates:

```text
system_echo
math_add
text_stats
```

They are read-only and require `skill:execute`.

## Boundaries

```text
API
 -> Application Service
 -> AgentHarness
 -> ModelProvider

Model tool proposal
 -> SkillExecutor
 -> schema validation
 -> authorization
 -> registered SkillProviderAdapter
 -> output validation
 -> model
```

No HTTP handler directly calls DeepSeek or a Skill handler.

## Validation

Automated CI runs:

```bash
ruff check app tests
mypy app
pytest
```

It also boots the full Docker Compose stack, seeds RBAC/Skills, executes `math_add`, and verifies AgentVersion Skill bindings.

Manual end-to-end validation is deferred until all project phases are complete.
