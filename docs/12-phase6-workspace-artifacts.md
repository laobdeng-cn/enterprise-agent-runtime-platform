# 12 — Phase 6 Workspace + Artifacts

## Status

**Implemented**

Phase 6 gives every durable Run an isolated filesystem boundary and a first-class Artifact model. Workspace state is persistent across backend restarts and is designed to be mounted into the Phase 7 Docker Sandbox.

## Workspace layout

Every Run receives one Workspace row and one physical root:

```text
<WORKSPACE_ROOT>/<run_id>/
├── input/
├── working/
└── artifacts/
```

Semantics:

- `input/` stores user/operator supplied inputs;
- `working/` is the Agent's mutable working area;
- `artifacts/` contains immutable-style published outputs.

The Run owns the Workspace. A Workspace cannot be created independently of a Run.

## Persistence

### Workspace

Stores:

- Run ID;
- storage key;
- status;
- total quota;
- per-file size limit;
- timestamps.

### Artifact

Stores:

- Workspace ID;
- optional source RunStep;
- workspace-relative physical path;
- display name;
- artifact kind;
- media type;
- size;
- SHA-256;
- creator classification;
- timestamp.

The database stores metadata. File bytes live in the persistent workspace volume.

## Safe path resolver

All file operations pass through `WorkspaceStorage.resolve()`.

The resolver rejects:

- absolute paths;
- `..` traversal;
- dot/empty path components;
- Windows-style backslash paths;
- NUL bytes;
- paths outside the Run root;
- symlink components, including broken symlinks.

Agent Skills do not receive host filesystem paths.

They only receive workspace-relative paths such as:

```text
input/request.md
working/analysis.csv
working/report.md
```

## File policies

UTF-8 text read/write is restricted to an allowlist including:

- txt;
- md;
- json;
- csv;
- yaml/yml;
- log;
- html;
- py.

Artifact publication additionally allows common report/image/archive types such as PDF, PNG, JPEG, SVG and ZIP.

Each Workspace enforces:

- `WORKSPACE_MAX_FILE_BYTES`;
- `WORKSPACE_QUOTA_BYTES`.

Writes are staged to a temporary file and atomically replaced.

## Run creation

`POST /api/runs` now creates both:

1. the durable AgentRun;
2. its Workspace metadata and physical directory tree.

The database transaction is not committed until workspace initialization succeeds.

## Workspace Skills

Phase 6 seeds four Run-scoped Skills:

```text
workspace_list
workspace_read_text
workspace_write_text
artifact_publish
```

These use the new `workspace` Skill provider.

The Skill execution layer receives a `SkillExecutionContext` containing the durable Run ID. Workspace Skills fail if invoked outside a Run context.

This prevents a generic Skill invocation from guessing or selecting an arbitrary workspace.

### Permission model

Workspace Skills require both `skill:execute` and the relevant resource permission:

```text
workspace_list       -> workspace:read
workspace_read_text  -> workspace:read
workspace_write_text -> workspace:write
artifact_publish     -> artifact:create
```

The Agent can write only under `working/`.

## Workspace API

```text
GET /api/runs/{run_id}/workspace

GET /api/runs/{run_id}/workspace/files?path=working

GET /api/runs/{run_id}/workspace/text?path=working/report.md

PUT /api/runs/{run_id}/workspace/text
```

The operator/API write endpoint supports controlled writes to `input/` and `working/`.

## Artifact API

```text
GET  /api/runs/{run_id}/artifacts
POST /api/runs/{run_id}/artifacts
GET  /api/runs/{run_id}/artifacts/{artifact_id}/download
```

Publishing copies a file from `working/` into an artifact-specific directory under `artifacts/`.

Publication records:

- SHA-256 checksum;
- MIME type;
- byte size;
- display name;
- source metadata.

The original working file and published artifact are separate copies, which preserves the published output even if the working file later changes.

## Persistent Docker volume

Docker Compose now mounts:

```text
workspace_data:/data/workspaces
```

The backend receives:

```text
WORKSPACE_ROOT
WORKSPACE_MAX_FILE_BYTES
WORKSPACE_QUOTA_BYTES
```

Restarting the backend does not remove Run files or artifacts.

## Frontend

The engineering console now includes a Workspace Inspector for a selected Run:

- used bytes;
- total quota;
- maximum file size;
- working directory entries;
- Artifact metadata.

Phase 7 will extend this view with Sandbox execution results.

## Security tests

Automated tests cover:

- Run-to-Run isolation;
- parent traversal;
- absolute paths;
- backslash paths;
- empty path components;
- symlink escape;
- file type policy;
- file size policy;
- total quota;
- artifact publication boundary;
- Run execution context required by Workspace Skills.

Docker Compose CI additionally validates:

- migration 0006;
- seeded Workspace Skills;
- Workspace creation with the Run;
- input/working writes;
- text read;
- traversal rejection;
- artifact publication;
- artifact metadata listing;
- artifact download;
- file and artifact persistence across backend restart;
- Phase 5 durable Run behavior remains intact.

## Phase boundary

Phase 6 provides a safe filesystem abstraction but does **not** execute arbitrary code.

That is intentionally deferred to Phase 7.

Phase 7 will mount only the current Run's Workspace into an ephemeral Docker container with CPU, memory, time and network controls.

## Exit criteria

Phase 6 is complete because:

1. every Run receives an isolated Workspace;
2. workspace metadata is persisted;
3. files survive backend restart;
4. traversal and symlink escapes are rejected;
5. per-file and total-size policies are enforced;
6. Agent Skills can read/write only the current Run workspace;
7. published artifacts receive immutable metadata and checksum;
8. artifacts are downloadable only through authorized Run-scoped APIs;
9. artifact bytes survive backend restart;
10. automated security and Docker integration tests cover the boundary.
