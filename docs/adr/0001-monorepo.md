# ADR 0001 — Use a Monorepo

- **Status:** Accepted
- **Date:** 2026-09-28

## Context

Backend, frontend, MCP servers, sandbox definitions and architecture documents evolve together and share versioned contracts.

## Decision

Use a single repository containing all platform components.

## Consequences

### Positive

- atomic cross-component changes;
- easier local development and demo setup;
- one issue/commit history;
- consistent documentation.

### Negative

- repository can grow large;
- CI must later avoid running unrelated pipelines unnecessarily.

## Revisit When

Independent teams, release cadences or scale make separate repositories operationally valuable.
