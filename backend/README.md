# Backend

This directory will contain the Python/FastAPI control plane and agent runtime implementation.

## Planned boundaries

```text
backend/
├── app/
│   ├── api/               # HTTP/SSE transport only
│   ├── core/              # configuration, security, shared primitives
│   ├── models/            # persistence models
│   ├── schemas/           # API/domain validation schemas
│   ├── services/          # application services
│   ├── agents/
│   │   └── harness/       # model/context/tool lifecycle
│   ├── runtime/           # durable Run/Step execution
│   ├── skills/            # registry and execution adapters
│   ├── memory/            # memory retrieval/persistence
│   ├── mcp/               # MCP clients and registry
│   ├── sandbox/           # sandbox orchestration client
│   ├── workflows/         # graph/DAG orchestration
│   ├── observability/     # traces and metrics
│   └── eval/              # evaluation/regression
├── alembic/
└── tests/
```

## Architectural rule

HTTP handlers must not contain agent orchestration logic. API code delegates to application/runtime services. The LLM provider is accessed through an internal adapter rather than directly from business modules.

Implementation begins in **Phase 1**.
