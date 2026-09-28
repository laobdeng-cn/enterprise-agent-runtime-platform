# Frontend

Vue 3 + TypeScript operations console for Enterprise Agent Runtime Platform.

## Current Phase 2 contents

- Vue 3
- TypeScript
- Vite
- Element Plus
- dependency health status
- JWT sign-in form
- current principal viewer
- role and permission display
- backend proxy for `/health` and `/api`

The browser stores the current access token in `sessionStorage`, not persistent local storage. This is sufficient for the development console; production session hardening is deferred until deployment/security hardening phases.

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

Later phases will evolve this console into Agent Management, Skill Registry, Run Trace, Workspace, Approval and Evaluation views.
