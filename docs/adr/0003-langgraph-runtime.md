# ADR 0003 — LangGraph for Agent/Workflow Orchestration

- **Status:** Accepted with boundary
- **Date:** 2026-09-28

## Context

The platform requires stateful graph execution, checkpoints, interrupts and human-in-the-loop behavior.

## Decision

Use LangGraph as an orchestration engine behind an internal Runtime/Harness abstraction.

LangGraph objects must not become the public domain model.

## Rationale

The abstraction prevents framework-specific state from leaking into APIs and persistence contracts, while allowing LangGraph to provide graph execution and checkpoint primitives.

## Consequences

- fast implementation of graph workflows and interrupts;
- easier replacement/augmentation if requirements change;
- requires explicit mapping between domain Run/Step state and LangGraph state.
