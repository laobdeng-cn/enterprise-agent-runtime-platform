# Backend

FastAPI control plane and execution backend for Enterprise Agent Runtime Platform.

## Current Phase 8 contents

- JWT authentication and RBAC
- versioned Agent / AgentVersion
- versioned Skill / SkillVersion
- DeepSeek Agent Harness
- durable AgentRun / RunStep / ToolCall / Checkpoint / Event persistence
- per-Run Workspace + Artifact persistence
- isolated Docker Python Sandbox
- Conversation / Task / Long-term / Semantic Memory
- USER / AGENT / RUN Memory scopes
- optional TTL and soft deletion
- content fingerprint deduplication
- importance / source / access metadata
- deterministic English/CJK relevance retrieval
- automatic relevant-Memory retrieval before model calls
- Memory IDs/count persisted on MODEL_CALL steps
- explicit untrusted-Memory ContextBuilder boundary
- `memory_search` and `memory_write` Skills
- Memory CRUD/search API
- Alembic migrations through 0007

## Memory execution boundary

```text
AgentRun
   |
   v
MemoryRetriever
   ├── USER
   ├── AGENT
   └── RUN
   |
   v
rank + bounded selection
   |
   v
ContextBuilder
   |
   +--> explicit untrusted Memory context
   |
   v
Agent Harness -> DeepSeek
```

Chat history is not persisted as Memory automatically.

## Memory API

```text
GET    /api/memories
POST   /api/memories
GET    /api/memories/search
GET    /api/memories/{id}
PATCH  /api/memories/{id}
DELETE /api/memories/{id}
```

## Validation

CI executes:

```bash
ruff check app tests
mypy app
pytest
```

Docker Compose CI additionally validates Memory migration/seeding, all three scopes, retrieval ranking, deduplication, soft deletion and Runtime context injection while retaining Phase 6/7 Workspace/Sandbox regression coverage.

Manual local validation remains deferred until all phases are complete.
