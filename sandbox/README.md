# Sandbox Runtime

This directory will define the isolated code-execution environment used by agents.

## Intended security model

Each execution receives:

- an ephemeral container;
- explicit CPU and memory limits;
- a hard timeout;
- a dedicated workspace mount only;
- no Docker socket;
- no arbitrary host filesystem mounts;
- default-deny network access, with allow-listing introduced only when required;
- a read-only base filesystem where practical.

## First execution backend

Phase 7 will implement a **Python sandbox** first. Shell execution is out of scope until the Python path is stable and audited.

A sandbox result must return a structured envelope containing:

```json
{
  "status": "success",
  "exit_code": 0,
  "stdout": "",
  "stderr": "",
  "artifacts": []
}
```

The sandbox is an execution boundary. It does not decide business permissions; authorization happens before dispatch.
