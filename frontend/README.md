# Frontend

Vue 3 + TypeScript engineering console for Enterprise Agent Runtime Platform.

## Current Phase 5 contents

- infrastructure health
- authentication/current principal
- Agent selection
- Skill registry overview
- durable Run creation
- PENDING Run start
- PAUSED Run resume
- Run cancellation
- Run state/attempt/step/checkpoint/tool-call summary
- normalized Run error display

Live trace visualization is intentionally deferred to Phase 13. Phase 5 exposes the durable SSE endpoint from the backend and keeps the UI focused on lifecycle control.

Manual end-to-end validation remains deferred until all planned phases are complete.
