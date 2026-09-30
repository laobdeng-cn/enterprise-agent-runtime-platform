# MCP Servers

First-party MCP capability providers used by the Enterprise Agent Runtime Platform reference environment.

These services contain synthetic demo data. They exist to exercise enterprise connector boundaries, not to represent production scientific or ERP data.

## Services

```text
mcp_servers/
├── common/
│   └── security.py
├── knowledge_server/
│   └── app.py
├── experiment_server/
│   └── app.py
├── enterprise_server/
│   └── app.py
├── Dockerfile
└── requirements.txt
```

All first-party services expose Streamable HTTP MCP at `/mcp` and a simple container health endpoint at `/health`.

## Knowledge server

Tools:

- `search_documents`
- `get_document`

Purpose: approved internal engineering/process knowledge.

Platform permission mapping:

```text
search_documents -> knowledge:read
get_document     -> knowledge:read
```

## Experiment server

Tools:

- `search_experiments`
- `get_experiment`
- `create_experiment`

Purpose: R&D experiment history and candidate experiment creation.

Platform permission mapping:

```text
search_experiments -> experiment:read
get_experiment     -> experiment:read
create_experiment  -> experiment:create
```

## Enterprise server

Tools:

- `query_inventory`
- `create_work_order`
- `submit_approval`

Purpose: reference inventory, work-order, and approval-system connectivity.

Platform permission mapping:

```text
query_inventory   -> inventory:read
create_work_order -> work_order:create
submit_approval   -> approval:submit
```

## Trust boundary

MCP servers provide tool contracts and data. They do **not** grant authorization.

The backend owns:

- server trust classification;
- tool-to-domain permission mapping;
- side-effect classification;
- JSON Schema validation;
- Skill synchronization;
- current-principal authorization immediately before execution.

Unknown tools without an explicit side-effect map default to `SENSITIVE`.

## Local stack

The root Docker Compose stack starts all three services:

```text
knowledge-mcp  : 8101
experiment-mcp : 8102
enterprise-mcp : 8103
```

The backend seeds their registry entries and performs discovery after the MCP containers become healthy.

Manual local validation remains deferred until all project phases are complete.
