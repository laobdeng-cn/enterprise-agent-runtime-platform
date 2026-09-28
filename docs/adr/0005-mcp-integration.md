# ADR 0005 — MCP as a First-Class Capability Provider

- **Status:** Accepted
- **Date:** 2026-09-28

## Context

Enterprise agents need standardized integration with external tools and data sources.

## Decision

Support Model Context Protocol as a first-class Skill provider type alongside local, REST, database and sandbox adapters.

MCP discovery does not imply permission to execute a tool.

## Consequences

- standardized external capability discovery;
- clear separation between provider connectivity and central authorization;
- server health, schema drift and transport failures require observability and error normalization.
