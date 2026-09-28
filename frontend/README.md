# Frontend

Vue 3 + TypeScript operations console for Enterprise Agent Runtime Platform.

## Phase 1 contents

- Vue 3
- TypeScript
- Vite
- Element Plus
- responsive engineering-status page
- backend health proxy

The Phase 1 page calls `/health` through Vite and displays Backend, PostgreSQL and Redis status.

## Local development

```bash
npm install
npm run dev
```

When the backend is running outside Docker on port 8000, no additional configuration is required.

For Docker Compose, the root configuration supplies:

```text
VITE_BACKEND_PROXY_TARGET=http://backend:8000
```

## Build / type check

```bash
npm run build
npm run typecheck
```

Later phases will evolve this skeleton into Agent Management, Skill Registry, Run Trace, Workspace, Approval and Evaluation consoles.
