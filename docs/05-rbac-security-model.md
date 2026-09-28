# 05 — RBAC & Security Model

## 1. Security Principle

The LLM is a reasoning component, not a security principal or authorization service.

```text
LLM proposes action
      |
      v
Structured validation
      |
      v
Authenticated principal
      |
      v
RBAC + Policy Engine
      |
  +---+---+
  |       |
allow   deny / approval
```

## 2. Identity Model

Every external Run has an authenticated initiating principal.

Runtime context carries:

- user identity;
- roles;
- permissions;
- resource ownership/tenant scope;
- authentication/session metadata relevant to authorization.

Agent identity does not replace user identity.

## 3. Permission Naming

Use resource/action naming:

```text
agent:read
agent:create
agent:update
run:create
run:cancel
skill:read
skill:execute
workspace:read
artifact:read
experiment:read
experiment:create
approval:approve
eval:run
admin:manage
```

Permissions are atomic. Roles group them.

## 4. Initial Roles

### Admin

Platform configuration and governance.

### AgentDeveloper

May create/manage agents, skills, workflows and evaluations, subject to provider/resource permissions.

### BusinessUser

May run approved agents and access owned/authorized artifacts.

### Approver

May decide approval requests for explicitly authorized resource classes.

These roles are defaults, not hard-coded branches in application logic.

## 5. Two-Layer Authorization

### Layer 1 — RBAC

Does the principal have the required capability?

Example:

`experiment:create`

### Layer 2 — Runtime Policy

Even with the permission, should this concrete action execute automatically?

Policy may inspect:

- skill side-effect class;
- amount/cost threshold;
- target resource;
- data sensitivity;
- environment;
- current Run risk classification.

Result:

- `ALLOW`
- `DENY`
- `REQUIRE_APPROVAL`

## 6. Example

A Lab Manager has `experiment:create`.

The Skill `experiment.create` is a reversible write, but policy says experiments with estimated cost above 5,000 require approval.

Therefore:

```text
RBAC = allowed
Policy(cost=8,600) = REQUIRE_APPROVAL
Final = WAITING_APPROVAL
```

The model never sees an opportunity to override the threshold.

## 7. Workspace Security

A Run may access only its assigned workspace.

Path operations must:

1. canonicalize the requested path;
2. reject traversal outside workspace root;
3. enforce file type/size policies;
4. prevent symlink escapes;
5. audit writes/deletes.

## 8. Sandbox Security

Initial security controls:

- no host Docker socket inside sandbox;
- no arbitrary host mounts;
- dedicated workspace mount only;
- CPU and memory quotas;
- hard execution timeout;
- default-deny network;
- non-root user where possible;
- read-only base filesystem where possible;
- kill and cleanup after execution.

Container isolation reduces risk but is not treated as a perfect security boundary. High-assurance deployments may later require stronger isolation.

## 9. Secrets

Secrets must never be:

- committed to Git;
- inserted into prompts unless a tool contract explicitly requires and safely handles them;
- persisted in normal traces;
- returned to the model as tool output.

Providers receive secrets server-side from configuration/secret storage.

## 10. Prompt Injection Consideration

Retrieved documents, user files and external tool results are untrusted content.

The runtime should distinguish:

- trusted system instructions;
- application policy;
- user requests;
- retrieved evidence;
- external content.

External content cannot define authorization policy.

## 11. Audit Requirements

Record at minimum:

- principal;
- Run;
- proposed capability;
- validated arguments or secure reference;
- policy decision;
- approval if required;
- execution result;
- timestamp;
- trace link.

Sensitive arguments may be redacted while preserving audit meaning.

## 12. Threats to Test

Security tests will eventually cover:

- path traversal;
- symlink escape;
- permission bypass;
- stale approval replay;
- duplicate side effects on retry;
- prompt injection attempting to alter policy;
- model-generated SQL/shell injection;
- sandbox timeout/resource abuse;
- secrets leaking into traces.
