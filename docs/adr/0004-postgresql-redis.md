# ADR 0004 — PostgreSQL as System of Record, Redis as Ephemeral Infrastructure

- **Status:** Accepted
- **Date:** 2026-09-28

## Decision

Use PostgreSQL 16 as the durable source of truth. Use Redis for cache, pub/sub, rate-limit state and short-lived coordination only.

Start vector retrieval with pgvector unless scale demonstrates a need for a dedicated vector database.

## Rationale

A durable Agent Run must survive Redis loss/restart. Keeping authoritative lifecycle state in PostgreSQL provides transactional consistency and simplifies recovery.

## Consequences

- fewer infrastructure components initially;
- durable auditability;
- Redis outages should degrade ephemeral functionality rather than erase Run state.
