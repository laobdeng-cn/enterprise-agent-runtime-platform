# ADR 0006 — Docker-Based Sandbox for Initial Code Execution

- **Status:** Accepted for initial implementation
- **Date:** 2026-09-28

## Context

Agents need to analyze files and execute generated Python without receiving direct host execution privileges.

## Decision

Use short-lived Docker containers with explicit CPU, memory, timeout, filesystem and network restrictions.

Only a dedicated per-Run workspace may be mounted.

## Consequences

### Positive

- practical local development;
- reproducible execution image;
- enforceable resource limits;
- clear boundary from the control plane.

### Risks

Container isolation is not a perfect security boundary. Production/high-assurance environments may later require stronger isolation such as microVMs or specialized sandboxing.

## Guardrails

- never mount Docker socket;
- no arbitrary host mounts;
- default-deny network;
- non-root execution where possible;
- cleanup after every execution.
