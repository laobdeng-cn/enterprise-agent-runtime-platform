# Frontend

Vue 3 + TypeScript engineering console for Enterprise Agent Runtime Platform.

## Current Phase 7 contents

- infrastructure health
- authentication/current principal
- Agent selection
- Skill registry overview
- durable Run lifecycle controls
- Run state/attempt/step/checkpoint/tool-call summary
- Workspace Inspector
- workspace quota / usage display
- working-directory file listing
- Artifact metadata listing
- Sandbox daemon policy summary
- Run-scoped Python Sandbox editor
- isolated execution trigger
- Sandbox status / exit code / duration
- bounded stdout/stderr display
- generated Artifact count

The Sandbox Console calls the same governed Run-scoped execution service used by the `python_execute` Agent Skill. It is an engineering/operator surface rather than a separate execution path.

Manual end-to-end validation remains deferred until all planned phases are complete.
