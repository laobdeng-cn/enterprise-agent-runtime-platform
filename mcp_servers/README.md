# MCP Servers

First-party Model Context Protocol servers will live here.

## Planned servers

```text
mcp_servers/
├── knowledge_server/
├── experiment_server/
└── enterprise_server/
```

Initial target tools:

### knowledge_server

- `search_documents`
- `get_document`

### experiment_server

- `search_experiments`
- `get_experiment`
- `create_experiment`

### enterprise_server

- `query_inventory`
- `create_work_order`
- `submit_approval`

MCP servers are capability providers, not authorization authorities. The central Policy Engine still decides whether the current principal may invoke a discovered capability.

Implementation begins in **Phase 10**.
