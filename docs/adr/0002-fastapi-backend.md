# ADR 0002 — Python 3.12 + FastAPI Control Plane

- **Status:** Accepted
- **Date:** 2026-09-28

## Context

The runtime needs strong Python ecosystem compatibility for LLM libraries, LangGraph, MCP and evaluation while also exposing typed APIs and SSE.

## Decision

Use Python 3.12 with FastAPI, Pydantic v2, SQLAlchemy 2 and Alembic.

## Consequences

- Python ecosystem fits Agent/RAG/runtime work.
- Pydantic schemas can serve API and tool-contract validation.
- Async execution must be designed carefully around blocking providers.
- Runtime/application logic must remain independent of FastAPI request objects.
