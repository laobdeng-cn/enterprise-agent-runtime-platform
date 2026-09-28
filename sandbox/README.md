# Python Sandbox Runtime

Phase 7 executes Agent-generated Python in short-lived containers managed by a dedicated Docker daemon.

## Security boundary

Each execution is created with:

- `network_mode=none` by default;
- a read-only container root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- non-root UID/GID `65534:65534`;
- CPU, memory and PID limits;
- a hard wall-clock timeout;
- bounded `/tmp` tmpfs;
- Run-owned `input/` and `working/` bind-mounted read-only;
- one execution-scoped `/workspace/output` bind-mounted read-write;
- no Docker socket or daemon credentials inside the sandbox.

The backend talks to a dedicated Docker-in-Docker daemon over the internal Compose network. The daemon service itself requires privileged mode, but sandbox child containers are created with the restrictions above and never receive control of the daemon.

## Filesystem contract

Sandbox code can read:

```text
/workspace/input
/workspace/working
```

Generated files must be written to:

```text
/workspace/output
```

Outputs are scanned after execution. Symlinks, unsupported types, oversized files, excessive file counts and workspace-quota violations are rejected before Artifact publication.

## Image policy

The Phase 7 image intentionally contains Python 3.12 and the standard library only. Package installation and outbound network access are not available from the sandbox. Additional analysis libraries should be introduced as explicit, versioned sandbox images rather than installed dynamically by Agent code.
