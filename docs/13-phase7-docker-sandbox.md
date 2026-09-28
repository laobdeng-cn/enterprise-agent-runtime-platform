# 13 — Phase 7 Docker Sandbox

## Status

**Implemented**

Phase 7 adds isolated Python execution to the durable Agent Runtime. Agent-generated code is never executed inside the FastAPI process. It is dispatched to a short-lived container managed by a dedicated Docker daemon and bound to the current Run's Workspace.

## Execution architecture

```text
Agent / operator
      |
      v
python_execute Skill or Run Sandbox API
      |
      v
SandboxExecutionService
      |
      +--> SANDBOX_EXECUTION RunStep
      +--> sandbox.* RunEvent
      |
      v
Dedicated Docker daemon
      |
      v
Ephemeral Python container
  ├── /workspace/input    read-only
  ├── /workspace/working  read-only
  └── /workspace/output   execution-scoped read-write
      |
      v
Output validation
      |
      v
Artifact publication
```

## Dedicated Docker daemon

Docker Compose contains a dedicated Docker-in-Docker service. The backend does not mount the host Docker socket.

The daemon service needs privileged mode to operate Docker internally, but child Sandbox containers do not receive the daemon socket, Docker credentials, or host-wide mounts. This separates the application backend from the host Docker control plane while keeping the local development stack reproducible.

## Container security policy

Every Python execution applies:

- `network_mode=none`;
- read-only root filesystem;
- `cap_drop=[ALL]`;
- `no-new-privileges`;
- non-root UID/GID `65534:65534`;
- CPU quota;
- memory + swap cap;
- PID limit;
- hard wall-clock timeout;
- bounded tmpfs for `/tmp`;
- current Run input/working mounted read-only;
- one isolated output directory mounted read-write.

The Sandbox image is versioned independently and contains only Python 3.12 + standard library in Phase 7.

## Run integration

Each dispatch creates a durable `SANDBOX_EXECUTION` RunStep containing execution metadata rather than raw host paths.

Stored metadata includes:

- execution ID;
- language;
- SHA-256 of submitted code;
- code byte size;
- image name;
- security policy snapshot;
- status / exit code;
- bounded stdout/stderr;
- duration;
- timeout state;
- produced Artifact metadata.

Events include:

```text
sandbox.started
sandbox.completed
sandbox.failed
sandbox.timed_out
sandbox.output_rejected
sandbox.infrastructure_failed
```

## Python capability

The registry seeds one Sandbox Skill:

```text
python_execute
```

Required permissions:

```text
skill:execute
sandbox:execute
workspace:read
artifact:create
```

The Skill requires a durable `SkillExecutionContext.run_id`; it cannot be executed as an unscoped generic filesystem/code tool.

Code can read:

```text
/workspace/input
/workspace/working
```

Code can write generated outputs only to:

```text
/workspace/output
```

## Output validation and Artifact promotion

Successful execution does not automatically trust files created by code.

The backend scans the execution output directory and rejects:

- symlink files or directories;
- unsupported file extensions;
- files over the Workspace per-file limit;
- too many generated files;
- Workspace quota overflow.

Accepted outputs are copied into the Run's `artifacts/` tree and registered with Artifact metadata including SHA-256, MIME type, size, creator and source Sandbox step.

Failed or timed-out executions remove the execution output directory.

## API

```text
GET  /api/sandbox/health
POST /api/runs/{run_id}/sandbox/python
```

The direct API is intended for engineering/operator workflows. Agent execution uses the same underlying `SandboxExecutionService` through the `python_execute` Skill.

## Response

```json
{
  "execution_id": "...",
  "run_id": "...",
  "status": "SUCCEEDED",
  "exit_code": 0,
  "stdout": "sandbox-ok\n",
  "stderr": "",
  "duration_ms": 123.4,
  "timed_out": false,
  "stdout_truncated": false,
  "stderr_truncated": false,
  "artifacts": []
}
```

Stdout and stderr are bounded to prevent untrusted code from creating unbounded API/DB payloads.

## CI security validation

Integration CI verifies an actual Docker Sandbox execution:

1. dedicated daemon is reachable;
2. security configuration reports network disabled, read-only root and non-root user;
3. sandbox reads Run input;
4. sandbox writes only to `/workspace/output`;
5. generated output becomes a downloadable Artifact;
6. outbound socket connection fails;
7. code exceeding the hard timeout is killed and reported `TIMED_OUT`;
8. three executions persist as `SANDBOX_EXECUTION` RunSteps;
9. ephemeral containers are removed after execution;
10. existing durable Run and Workspace tests continue to pass.

## Phase boundary

Phase 7 deliberately does not add arbitrary shell execution, dynamic package installation, network allow-listing or a fleet scheduler.

Phase 8 adds durable Memory. Later hardening can introduce multiple versioned Sandbox images and remote Sandbox workers behind the same execution interface.

## Exit criteria

Phase 7 is complete because:

1. Python code executes outside the backend process;
2. Sandbox containers are short-lived and default-deny;
3. CPU, memory, PID and time limits are enforced;
4. network access is disabled by default;
5. normal Run workspace mounts are read-only;
6. generated files are confined to an execution output mount;
7. execution state is persisted as RunStep/Event data;
8. outputs are policy-validated before Artifact registration;
9. failed/timed-out containers and output directories are cleaned;
10. automated integration CI proves execution, network denial, timeout and cleanup.
