# Frontend

Vue 3 + TypeScript operations console for Enterprise Agent Runtime Platform.

## Current Phase 3 contents

- infrastructure health status
- JWT sign-in
- current-principal / permission display
- Agent v1 creation
- Agent list and version count
- Harness preview form
- normalized model result metadata

The preview page calls:

```text
POST /api/agents/{agent_id}/preview
```

A real response requires the backend to have a valid `DEEPSEEK_API_KEY`.

## Development

```bash
npm install
npm run dev
```

Docker Compose supplies:

```text
VITE_BACKEND_PROXY_TARGET=http://backend:8000
```

Validation:

```bash
npm run typecheck
npm run build
```

Later phases add Skill Registry, durable Run timelines, Workspace, Approval, Trace and Evaluation views.
