<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

type DependencyState = "ok" | "unavailable" | "checking";

interface HealthResponse {
  status: "ok" | "degraded";
  service: string;
  version: string;
  database: "ok" | "unavailable";
  redis: "ok" | "unavailable";
}

interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

interface CurrentUser {
  id: string;
  username: string;
  email: string | null;
  is_active: boolean;
  roles: string[];
  permissions: string[];
}

interface AgentVersion {
  id: string;
  version: number;
  skills: string[];
}

interface Agent {
  id: string;
  name: string;
  description: string;
  status: string;
  active_version_id: string | null;
  versions: AgentVersion[];
}

interface Skill {
  id: string;
  name: string;
  description: string;
  provider_type: string;
  status: string;
}

interface RunStep {
  id: string;
  sequence: number;
  step_type: string;
  status: string;
  attempt: number;
}

interface RunCheckpoint {
  id: string;
  sequence: number;
  state: string;
  kind: string;
}

interface RunRecord {
  id: string;
  agent_id: string;
  agent_version_id: string;
  status: string;
  input: string;
  attempt: number;
  max_attempts: number;
  state_version: number;
  error_data: Record<string, unknown> | null;
  result_data: Record<string, unknown> | null;
  created_at: string;
  steps: RunStep[];
  checkpoints: RunCheckpoint[];
  tool_calls: Array<Record<string, unknown>>;
}

interface WorkspaceSummary {
  id: string;
  run_id: string;
  status: string;
  quota_bytes: number;
  max_file_bytes: number;
  used_bytes: number;
  created_at: string;
}

interface WorkspaceEntry {
  path: string;
  name: string;
  type: "file" | "directory";
  size_bytes: number;
}

interface ArtifactRecord {
  id: string;
  relative_path: string;
  display_name: string;
  kind: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  created_by: string;
}

interface SandboxHealth {
  available: boolean;
  image: string;
  security: {
    network_mode: string;
    read_only: boolean;
    memory_limit_mb: number;
    cpu_limit: number;
    pids_limit: number;
    cap_drop: string[];
    no_new_privileges: boolean;
    user: string;
    tmpfs_mb: number;
    timeout_seconds: number;
  };
}

interface MemoryRecord {
  id: string;
  owner_user_id: string;
  agent_id: string | null;
  run_id: string | null;
  memory_type: "CONVERSATION" | "TASK" | "LONG_TERM" | "SEMANTIC";
  scope: "USER" | "AGENT" | "RUN";
  status: "ACTIVE" | "ARCHIVED" | "DELETED";
  label: string | null;
  content: string;
  metadata: Record<string, unknown>;
  source: string;
  source_ref: string | null;
  importance: number;
  expires_at: string | null;
  access_count: number;
  last_accessed_at: string | null;
  created_at: string;
  updated_at: string;
  score?: number;
}

interface ContextDecision {
  component_id: string;
  kind: "system" | "user" | "additional_context" | "memory" | "skill" | "tool_history";
  label: string;
  status: "included" | "compressed" | "excluded";
  reason: string;
  priority: number;
  original_tokens: number;
  used_tokens: number;
  score: number | null;
  preview: string;
}

interface ContextBudget {
  context_window_tokens: number;
  reserved_output_tokens: number;
  runtime_reserve_tokens: number;
  input_budget_tokens: number;
  initial_budget_tokens: number;
  used_tokens: number;
  remaining_tokens: number;
  message_tokens: number;
  tool_tokens: number;
}

interface ContextTrace {
  budget: ContextBudget;
  decisions: ContextDecision[];
  selected_skill_names: string[];
  excluded_skill_names: string[];
  compression_count: number;
  policy: Record<string, unknown>;
}

interface ContextInspection {
  run_id: string;
  agent_version_id: string;
  source: "preview" | "persisted";
  trace: ContextTrace;
}

interface SandboxResult {
  execution_id: string;
  run_id: string;
  status: "SUCCEEDED" | "FAILED" | "TIMED_OUT";
  exit_code: number | null;
  stdout: string;
  stderr: string;
  duration_ms: number;
  timed_out: boolean;
  stdout_truncated: boolean;
  stderr_truncated: boolean;
  artifacts: Array<{
    artifact_id: string;
    path: string;
    display_name: string;
    media_type: string;
    size_bytes: number;
    sha256: string;
  }>;
}

const backend = ref<DependencyState>("checking");
const database = ref<DependencyState>("checking");
const redis = ref<DependencyState>("checking");
const version = ref("0.9.0");

const username = ref("");
const password = ref("");
const authError = ref("");
const authLoading = ref(false);
const token = ref(sessionStorage.getItem("earp_access_token") ?? "");
const currentUser = ref<CurrentUser | null>(null);

const agents = ref<Agent[]>([]);
const skills = ref<Skill[]>([]);
const runs = ref<RunRecord[]>([]);
const selectedAgentId = ref("");
const runInput = ref("Summarize this task and use the available capabilities when useful.");
const runtimeError = ref("");
const runtimeLoading = ref(false);
const selectedRunId = ref("");
const workspace = ref<WorkspaceSummary | null>(null);
const workingFiles = ref<WorkspaceEntry[]>([]);
const artifacts = ref<ArtifactRecord[]>([]);
const workspaceLoading = ref(false);
const sandboxHealth = ref<SandboxHealth | null>(null);
const sandboxCode = ref(
  'from pathlib import Path\n' +
    'text = "sandbox execution"\n' +
    'Path("/workspace/output/result.txt").write_text(text.upper())\n' +
    'print("sandbox-ok")',
);
const sandboxResult = ref<SandboxResult | null>(null);
const sandboxLoading = ref(false);
const memories = ref<MemoryRecord[]>([]);
const memoryQuery = ref("");
const memoryType = ref<MemoryRecord["memory_type"]>("LONG_TERM");
const memoryScope = ref<MemoryRecord["scope"]>("USER");
const memoryContent = ref("");
const memoryImportance = ref(0.7);
const memoryLoading = ref(false);
const memoryError = ref("");
const contextInspection = ref<ContextInspection | null>(null);
const contextLoading = ref(false);
const contextError = ref("");

const overallType = computed(() => {
  if (backend.value === "checking") return "info";
  return backend.value === "ok" && database.value === "ok" && redis.value === "ok"
    ? "success"
    : "danger";
});

const canReadAgents = computed(
  () => currentUser.value?.permissions.includes("agent:read") ?? false,
);
const canReadSkills = computed(
  () => currentUser.value?.permissions.includes("skill:read") ?? false,
);
const canReadRuns = computed(
  () => currentUser.value?.permissions.includes("run:read") ?? false,
);
const canCreateRuns = computed(
  () => currentUser.value?.permissions.includes("run:create") ?? false,
);
const canUpdateRuns = computed(
  () => currentUser.value?.permissions.includes("run:update") ?? false,
);
const canCancelRuns = computed(
  () => currentUser.value?.permissions.includes("run:cancel") ?? false,
);
const canReadWorkspace = computed(
  () => currentUser.value?.permissions.includes("workspace:read") ?? false,
);
const canReadArtifacts = computed(
  () => currentUser.value?.permissions.includes("artifact:read") ?? false,
);
const canExecuteSandbox = computed(
  () => currentUser.value?.permissions.includes("sandbox:execute") ?? false,
);
const canReadMemory = computed(
  () => currentUser.value?.permissions.includes("memory:read") ?? false,
);
const canWriteMemory = computed(
  () => currentUser.value?.permissions.includes("memory:write") ?? false,
);
const canDeleteMemory = computed(
  () => currentUser.value?.permissions.includes("memory:delete") ?? false,
);

function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (token.value) {
    headers.set("Authorization", `Bearer ${token.value}`);
  }
  return fetch(path, { ...init, headers });
}

async function refreshHealth(): Promise<void> {
  backend.value = "checking";
  database.value = "checking";
  redis.value = "checking";
  try {
    const response = await fetch("/health");
    const payload = (await response.json()) as HealthResponse;
    backend.value = response.ok ? "ok" : "unavailable";
    database.value = payload.database;
    redis.value = payload.redis;
    version.value = payload.version;
  } catch {
    backend.value = "unavailable";
    database.value = "unavailable";
    redis.value = "unavailable";
  }
}

async function loadCurrentUser(): Promise<void> {
  if (!token.value) {
    currentUser.value = null;
    return;
  }
  const response = await apiFetch("/api/auth/me");
  if (!response.ok) {
    logout();
    return;
  }
  currentUser.value = (await response.json()) as CurrentUser;
}

async function loadAgents(): Promise<void> {
  if (!currentUser.value || !canReadAgents.value) return;
  const response = await apiFetch("/api/agents");
  if (!response.ok) return;
  agents.value = (await response.json()) as Agent[];
  if (!selectedAgentId.value && agents.value.length > 0) {
    selectedAgentId.value = agents.value[0].id;
  }
}

async function loadSkills(): Promise<void> {
  if (!currentUser.value || !canReadSkills.value) return;
  const response = await apiFetch("/api/skills");
  if (!response.ok) return;
  skills.value = (await response.json()) as Skill[];
}

async function loadRuns(): Promise<void> {
  if (!currentUser.value || !canReadRuns.value) return;
  const response = await apiFetch("/api/runs");
  if (!response.ok) return;
  runs.value = (await response.json()) as RunRecord[];
}

async function login(): Promise<void> {
  authError.value = "";
  authLoading.value = true;
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username.value,
        password: password.value,
      }),
    });
    if (!response.ok) {
      authError.value = "Invalid username or password.";
      return;
    }
    const payload = (await response.json()) as LoginResponse;
    token.value = payload.access_token;
    sessionStorage.setItem("earp_access_token", payload.access_token);
    password.value = "";
    await loadCurrentUser();
    await Promise.all([loadAgents(), loadSkills(), loadRuns(), loadMemories()]);
  } catch {
    authError.value = "Authentication service is unavailable.";
  } finally {
    authLoading.value = false;
  }
}

async function loadMemories(): Promise<void> {
  if (!currentUser.value || !canReadMemory.value) return;

  memoryLoading.value = true;
  memoryError.value = "";
  try {
    const query = memoryQuery.value.trim();
    let path = "/api/memories";
    if (query) {
      const params = new URLSearchParams({ q: query, limit: "50" });
      if (selectedRunId.value) {
        params.set("run_id", selectedRunId.value);
      } else if (selectedAgentId.value) {
        params.set("agent_id", selectedAgentId.value);
      }
      path = `/api/memories/search?${params.toString()}`;
    }

    const response = await apiFetch(path);
    if (!response.ok) {
      memoryError.value = await response.text();
      return;
    }
    memories.value = (await response.json()) as MemoryRecord[];
  } catch {
    memoryError.value = "Memory API is unavailable.";
  } finally {
    memoryLoading.value = false;
  }
}

async function createMemory(): Promise<void> {
  if (!memoryContent.value.trim() || !canWriteMemory.value) return;

  const payload: Record<string, unknown> = {
    memory_type: memoryType.value,
    scope: memoryScope.value,
    content: memoryContent.value.trim(),
    importance: memoryImportance.value,
    metadata: { created_from: "memory-inspector" },
  };

  if (memoryScope.value === "AGENT") {
    if (!selectedAgentId.value) {
      memoryError.value = "Select an Agent before creating AGENT-scoped Memory.";
      return;
    }
    payload.agent_id = selectedAgentId.value;
  }

  if (memoryScope.value === "RUN") {
    if (!selectedRunId.value) {
      memoryError.value = "Open a Run workspace before creating RUN-scoped Memory.";
      return;
    }
    payload.run_id = selectedRunId.value;
  }

  memoryLoading.value = true;
  memoryError.value = "";
  try {
    const response = await apiFetch("/api/memories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      memoryError.value = await response.text();
      return;
    }
    memoryContent.value = "";
    await loadMemories();
  } catch {
    memoryError.value = "Memory create failed.";
  } finally {
    memoryLoading.value = false;
  }
}

async function deleteMemory(memory: MemoryRecord): Promise<void> {
  if (!canDeleteMemory.value) return;
  memoryLoading.value = true;
  memoryError.value = "";
  try {
    const response = await apiFetch(`/api/memories/${memory.id}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      memoryError.value = await response.text();
      return;
    }
    await loadMemories();
  } catch {
    memoryError.value = "Memory delete failed.";
  } finally {
    memoryLoading.value = false;
  }
}

async function createRun(): Promise<void> {
  if (!selectedAgentId.value || !runInput.value.trim()) return;
  runtimeError.value = "";
  runtimeLoading.value = true;
  try {
    const response = await apiFetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_id: selectedAgentId.value,
        input: runInput.value.trim(),
        additional_context: [],
        max_attempts: 2,
      }),
    });
    if (!response.ok) {
      runtimeError.value = await response.text();
      return;
    }
    await loadRuns();
  } catch {
    runtimeError.value = "Durable Runtime API is unavailable.";
  } finally {
    runtimeLoading.value = false;
  }
}

async function inspectContext(run: RunRecord): Promise<void> {
  if (!canReadRuns.value) return;
  selectedRunId.value = run.id;
  contextLoading.value = true;
  contextError.value = "";
  try {
    const response = await apiFetch(`/api/runs/${run.id}/context`);
    if (!response.ok) {
      contextError.value = await response.text();
      return;
    }
    contextInspection.value = (await response.json()) as ContextInspection;
  } catch {
    contextError.value = "Context Inspector API is unavailable.";
  } finally {
    contextLoading.value = false;
  }
}

async function inspectWorkspace(run: RunRecord): Promise<void> {
  if (!canReadWorkspace.value) return;
  workspaceLoading.value = true;
  runtimeError.value = "";
  selectedRunId.value = run.id;

  try {
    const [workspaceResponse, filesResponse, artifactsResponse] = await Promise.all([
      apiFetch(`/api/runs/${run.id}/workspace`),
      apiFetch(`/api/runs/${run.id}/workspace/files?path=working`),
      canReadArtifacts.value
        ? apiFetch(`/api/runs/${run.id}/artifacts`)
        : Promise.resolve(null),
    ]);

    if (!workspaceResponse.ok || !filesResponse.ok) {
      runtimeError.value = "Could not inspect the Run workspace.";
      return;
    }

    workspace.value = (await workspaceResponse.json()) as WorkspaceSummary;
    workingFiles.value = (await filesResponse.json()) as WorkspaceEntry[];

    if (artifactsResponse?.ok) {
      artifacts.value = (await artifactsResponse.json()) as ArtifactRecord[];
    } else {
      artifacts.value = [];
    }
  } catch {
    runtimeError.value = "Workspace API is unavailable.";
  } finally {
    workspaceLoading.value = false;
  }
}

async function loadSandboxHealth(): Promise<void> {
  if (!currentUser.value || !canExecuteSandbox.value) return;
  try {
    const response = await apiFetch("/api/sandbox/health");
    if (response.ok) {
      sandboxHealth.value = (await response.json()) as SandboxHealth;
    }
  } catch {
    sandboxHealth.value = null;
  }
}

async function executeSandbox(): Promise<void> {
  if (!selectedRunId.value || !sandboxCode.value.trim() || !canExecuteSandbox.value) return;

  sandboxLoading.value = true;
  runtimeError.value = "";
  sandboxResult.value = null;

  try {
    const response = await apiFetch(
      `/api/runs/${selectedRunId.value}/sandbox/python`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: sandboxCode.value,
          publish_artifacts: true,
        }),
      },
    );

    if (!response.ok) {
      runtimeError.value = await response.text();
      return;
    }

    sandboxResult.value = (await response.json()) as SandboxResult;
    const selectedRun = runs.value.find((run) => run.id === selectedRunId.value);
    await loadRuns();
    if (selectedRun) {
      await inspectWorkspace({ ...selectedRun, id: selectedRunId.value });
    }
  } catch {
    runtimeError.value = "Sandbox Runtime API is unavailable.";
  } finally {
    sandboxLoading.value = false;
  }
}

async function runAction(run: RunRecord, action: "start" | "resume" | "cancel"): Promise<void> {
  runtimeError.value = "";
  runtimeLoading.value = true;
  try {
    const response = await apiFetch(`/api/runs/${run.id}/${action}`, {
      method: "POST",
    });
    if (!response.ok) {
      runtimeError.value = await response.text();
      return;
    }
    await loadRuns();
    if (selectedRunId.value === run.id) {
      await inspectContext(run);
    }
  } catch {
    runtimeError.value = `Run ${action} failed.`;
  } finally {
    runtimeLoading.value = false;
  }
}

function statusType(status: string): "success" | "warning" | "danger" | "info" {
  if (status === "COMPLETED") return "success";
  if (status === "FAILED" || status === "CANCELLED") return "danger";
  if (status === "PAUSED" || status === "RETRYING") return "warning";
  return "info";
}

function logout(): void {
  token.value = "";
  currentUser.value = null;
  agents.value = [];
  skills.value = [];
  runs.value = [];
  selectedAgentId.value = "";
  selectedRunId.value = "";
  workspace.value = null;
  workingFiles.value = [];
  artifacts.value = [];
  sandboxHealth.value = null;
  sandboxResult.value = null;
  memories.value = [];
  memoryQuery.value = "";
  memoryContent.value = "";
  memoryError.value = "";
  contextInspection.value = null;
  contextError.value = "";
  sessionStorage.removeItem("earp_access_token");
}

onMounted(async () => {
  await refreshHealth();
  await loadCurrentUser();
  await Promise.all([
    loadAgents(),
    loadSkills(),
    loadRuns(),
    loadSandboxHealth(),
    loadMemories(),
  ]);
});
</script>

<template>
  <main class="page-shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Enterprise Agent Runtime Platform</p>
        <h1>Context Engineering Pipeline</h1>
        <p class="subtitle">
          Phase 9 adds token budgeting, relevance-based Skill selection, bounded Memory
          and additional-context compression, runtime tool-history control, and an
          inspectable inclusion/exclusion trace for every Run.
        </p>
      </div>
      <el-tag :type="overallType" size="large" effect="dark">
        Phase 9 · v{{ version }}
      </el-tag>
    </section>

    <el-card class="status-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>Infrastructure</span>
          <el-button text type="primary" @click="refreshHealth">Refresh</el-button>
        </div>
      </template>
      <div class="status-grid">
        <div class="status-item"><span>Frontend</span><el-tag type="success">ok</el-tag></div>
        <div class="status-item"><span>Backend</span><el-tag :type="backend === 'ok' ? 'success' : 'danger'">{{ backend }}</el-tag></div>
        <div class="status-item"><span>PostgreSQL</span><el-tag :type="database === 'ok' ? 'success' : 'danger'">{{ database }}</el-tag></div>
        <div class="status-item"><span>Redis</span><el-tag :type="redis === 'ok' ? 'success' : 'danger'">{{ redis }}</el-tag></div>
      </div>
    </el-card>

    <section class="auth-grid">
      <el-card v-if="!currentUser" shadow="never">
        <template #header><strong>Sign in</strong></template>
        <el-form label-position="top" @submit.prevent="login">
          <el-form-item label="Username">
            <el-input v-model="username" autocomplete="username" />
          </el-form-item>
          <el-form-item label="Password">
            <el-input v-model="password" type="password" show-password @keyup.enter="login" />
          </el-form-item>
          <el-alert v-if="authError" :title="authError" type="error" :closable="false" />
          <el-button type="primary" :loading="authLoading" @click="login">
            Authenticate
          </el-button>
        </el-form>
      </el-card>

      <el-card v-else shadow="never">
        <template #header>
          <div class="card-header">
            <strong>Current principal</strong>
            <el-button text type="danger" @click="logout">Sign out</el-button>
          </div>
        </template>
        <dl class="principal-grid">
          <div><dt>Username</dt><dd>{{ currentUser.username }}</dd></div>
          <div>
            <dt>Roles</dt>
            <dd class="tag-list">
              <el-tag v-for="role in currentUser.roles" :key="role">{{ role }}</el-tag>
            </dd>
          </div>
          <div>
            <dt>Run permissions</dt>
            <dd class="tag-list">
              <el-tag
                v-for="permission in currentUser.permissions.filter((item) => item.startsWith('run:'))"
                :key="permission"
                type="info"
              >
                {{ permission }}
              </el-tag>
            </dd>
          </div>
        </dl>
      </el-card>

      <el-card shadow="never">
        <template #header><strong>Context pipeline</strong></template>
        <div class="flow">
          <span>System/User</span><span>→</span><span>Budget</span><span>→</span>
          <span>Memory + Skills</span><span>→</span><span>DeepSeek</span>
        </div>
        <p class="muted">
          Authoritative input is never silently truncated. Lower-priority context is
          ranked, compressed or excluded under an explicit token budget and every
          decision is inspectable.
        </p>
      </el-card>
    </section>

    <el-card
      v-if="currentUser && canReadMemory"
      class="status-card result-block"
      shadow="never"
    >
      <template #header>
        <div class="card-header">
          <strong>Memory Inspector</strong>
          <div class="tag-list">
            <el-tag type="info">Conversation</el-tag>
            <el-tag type="info">Task</el-tag>
            <el-tag type="info">Long-term</el-tag>
            <el-tag type="info">Semantic</el-tag>
          </div>
        </div>
      </template>

      <el-alert
        v-if="memoryError"
        :title="memoryError"
        type="error"
        :closable="false"
        class="result-block"
      />

      <div class="agent-grid">
        <div>
          <el-form label-position="top">
            <el-form-item label="Search relevant Memory">
              <el-input
                v-model="memoryQuery"
                placeholder="Search by current user / selected Agent / opened Run"
                clearable
                @keyup.enter="loadMemories"
              />
            </el-form-item>
            <div class="tag-list">
              <el-button
                type="primary"
                plain
                :loading="memoryLoading"
                @click="loadMemories"
              >
                Search / Reload
              </el-button>
              <el-tag type="info">{{ memories.length }} result(s)</el-tag>
            </div>
          </el-form>

          <div v-for="memory in memories" :key="memory.id" class="status-item result-block">
            <div>
              <div class="tag-list">
                <el-tag>{{ memory.memory_type }}</el-tag>
                <el-tag type="info">{{ memory.scope }}</el-tag>
                <el-tag type="success">{{ memory.status }}</el-tag>
                <el-tag v-if="memory.score !== undefined" type="warning">
                  score {{ memory.score.toFixed(3) }}
                </el-tag>
              </div>
              <p><strong>{{ memory.label || "Memory" }}</strong></p>
              <p>{{ memory.content }}</p>
              <p class="muted">
                importance {{ memory.importance.toFixed(2) }} · source {{ memory.source }}
                · accessed {{ memory.access_count }} time(s)
              </p>
            </div>
            <el-button
              v-if="canDeleteMemory"
              size="small"
              type="danger"
              plain
              @click="deleteMemory(memory)"
            >
              Delete
            </el-button>
          </div>
        </div>

        <div v-if="canWriteMemory">
          <h3>Create explicit Memory</h3>
          <el-form label-position="top">
            <el-form-item label="Type">
              <el-select v-model="memoryType">
                <el-option label="Conversation" value="CONVERSATION" />
                <el-option label="Task" value="TASK" />
                <el-option label="Long-term" value="LONG_TERM" />
                <el-option label="Semantic" value="SEMANTIC" />
              </el-select>
            </el-form-item>
            <el-form-item label="Scope">
              <el-select v-model="memoryScope">
                <el-option label="User" value="USER" />
                <el-option label="Agent" value="AGENT" />
                <el-option label="Run" value="RUN" />
              </el-select>
            </el-form-item>
            <el-form-item label="Importance">
              <el-slider
                v-model="memoryImportance"
                :min="0"
                :max="1"
                :step="0.05"
                show-input
              />
            </el-form-item>
            <el-form-item label="Content">
              <el-input
                v-model="memoryContent"
                type="textarea"
                :rows="5"
                placeholder="Persist only information worth retaining."
              />
            </el-form-item>
            <el-button
              type="primary"
              :loading="memoryLoading"
              :disabled="!memoryContent.trim()"
              @click="createMemory"
            >
              Save Memory
            </el-button>
          </el-form>
        </div>
      </div>
    </el-card>

    <section v-if="currentUser && canCreateRuns" class="agent-grid">
      <el-card shadow="never">
        <template #header><strong>Create durable Run</strong></template>
        <el-form label-position="top">
          <el-form-item label="Agent">
            <el-select v-model="selectedAgentId" placeholder="Select an Agent">
              <el-option
                v-for="agent in agents"
                :key="agent.id"
                :label="`${agent.name} · ${agent.versions.length} version(s)`"
                :value="agent.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="Input">
            <el-input v-model="runInput" type="textarea" :rows="5" />
          </el-form-item>
          <el-button
            type="primary"
            :loading="runtimeLoading"
            :disabled="!selectedAgentId || !runInput.trim()"
            @click="createRun"
          >
            Create PENDING Run
          </el-button>
        </el-form>
      </el-card>

      <el-card v-if="canReadSkills" shadow="never">
        <template #header><strong>Available Skills</strong></template>
        <div class="principal-grid">
          <div v-for="skill in skills" :key="skill.id">
            <dt>{{ skill.name }}</dt>
            <dd>
              <div class="tag-list">
                <el-tag>{{ skill.provider_type }}</el-tag>
                <el-tag type="info">{{ skill.status }}</el-tag>
              </div>
              <p class="muted">{{ skill.description }}</p>
            </dd>
          </div>
        </div>
      </el-card>
    </section>

    <el-card v-if="currentUser && canReadRuns" class="status-card result-block" shadow="never">
      <template #header>
        <div class="card-header">
          <strong>Durable Runs</strong>
          <el-button text type="primary" @click="loadRuns">Reload</el-button>
        </div>
      </template>

      <el-alert
        v-if="runtimeError"
        :title="runtimeError"
        type="error"
        :closable="false"
        class="result-block"
      />

      <el-empty v-if="runs.length === 0" description="No Runs yet" />

      <div v-for="run in runs" :key="run.id" class="status-item result-block">
        <div>
          <div class="tag-list">
            <el-tag :type="statusType(run.status)">{{ run.status }}</el-tag>
            <el-tag type="info">attempt {{ run.attempt }}/{{ run.max_attempts }}</el-tag>
            <el-tag type="info">{{ run.steps.length }} step(s)</el-tag>
            <el-tag type="info">{{ run.checkpoints.length }} checkpoint(s)</el-tag>
          </div>
          <p><strong>{{ run.input }}</strong></p>
          <p class="muted">
            Run {{ run.id }} · state version {{ run.state_version }} ·
            {{ run.tool_calls.length }} persisted tool call(s)
          </p>
          <p v-if="run.error_data" class="muted">
            Error: {{ JSON.stringify(run.error_data) }}
          </p>
        </div>

        <div class="tag-list">
          <el-button
            v-if="run.status === 'PENDING' && canUpdateRuns"
            size="small"
            type="primary"
            :loading="runtimeLoading"
            @click="runAction(run, 'start')"
          >
            Start
          </el-button>
          <el-button
            v-if="run.status === 'PAUSED' && canUpdateRuns"
            size="small"
            type="warning"
            :loading="runtimeLoading"
            @click="runAction(run, 'resume')"
          >
            Resume
          </el-button>
          <el-button
            v-if="canReadRuns"
            size="small"
            type="info"
            plain
            :loading="contextLoading && selectedRunId === run.id"
            @click="inspectContext(run)"
          >
            Context
          </el-button>
          <el-button
            v-if="canReadWorkspace"
            size="small"
            plain
            :loading="workspaceLoading && selectedRunId === run.id"
            @click="inspectWorkspace(run)"
          >
            Workspace
          </el-button>
          <el-button
            v-if="!['COMPLETED', 'FAILED', 'CANCELLED'].includes(run.status) && canCancelRuns"
            size="small"
            type="danger"
            plain
            :loading="runtimeLoading"
            @click="runAction(run, 'cancel')"
          >
            Cancel
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card
      v-if="currentUser && contextInspection"
      class="status-card result-block"
      shadow="never"
    >
      <template #header>
        <div class="card-header">
          <strong>Context Inspector</strong>
          <div class="tag-list">
            <el-tag :type="contextInspection.source === 'persisted' ? 'success' : 'info'">
              {{ contextInspection.source }}
            </el-tag>
            <el-tag type="info">{{ contextInspection.run_id }}</el-tag>
          </div>
        </div>
      </template>

      <el-alert
        v-if="contextError"
        :title="contextError"
        type="error"
        :closable="false"
        class="result-block"
      />

      <div class="status-grid">
        <div class="status-item">
          <span>Initial budget</span>
          <strong>{{ contextInspection.trace.budget.initial_budget_tokens }}</strong>
        </div>
        <div class="status-item">
          <span>Used</span>
          <strong>{{ contextInspection.trace.budget.used_tokens }}</strong>
        </div>
        <div class="status-item">
          <span>Remaining</span>
          <strong>{{ contextInspection.trace.budget.remaining_tokens }}</strong>
        </div>
        <div class="status-item">
          <span>Runtime reserve</span>
          <strong>{{ contextInspection.trace.budget.runtime_reserve_tokens }}</strong>
        </div>
      </div>

      <div class="result-block">
        <p><strong>Selected Skills</strong></p>
        <div class="tag-list">
          <el-tag
            v-for="skillName in contextInspection.trace.selected_skill_names"
            :key="skillName"
            type="success"
          >
            {{ skillName }}
          </el-tag>
          <el-tag
            v-if="contextInspection.trace.selected_skill_names.length === 0"
            type="info"
          >
            no Skill injected
          </el-tag>
        </div>
      </div>

      <div class="agent-grid result-block">
        <div
          v-for="decision in contextInspection.trace.decisions"
          :key="decision.component_id"
          class="status-item"
        >
          <div>
            <div class="tag-list">
              <el-tag type="info">{{ decision.kind }}</el-tag>
              <el-tag
                :type="
                  decision.status === 'included'
                    ? 'success'
                    : decision.status === 'compressed'
                      ? 'warning'
                      : 'danger'
                "
              >
                {{ decision.status }}
              </el-tag>
              <el-tag v-if="decision.score !== null" type="info">
                score {{ decision.score.toFixed(3) }}
              </el-tag>
            </div>
            <p><strong>{{ decision.label }}</strong></p>
            <p class="muted">
              {{ decision.reason }} · {{ decision.used_tokens }}/{{ decision.original_tokens }}
              estimated token(s) · priority {{ decision.priority }}
            </p>
            <p v-if="decision.preview" class="muted">{{ decision.preview }}</p>
          </div>
        </div>
      </div>
    </el-card>

    <el-card
      v-if="currentUser && selectedRunId && canExecuteSandbox"
      class="status-card result-block"
      shadow="never"
    >
      <template #header>
        <div class="card-header">
          <strong>Python Sandbox Console</strong>
          <div class="tag-list">
            <el-tag :type="sandboxHealth?.available ? 'success' : 'warning'">
              {{ sandboxHealth?.available ? "daemon ready" : "health unknown" }}
            </el-tag>
            <el-tag type="info">{{ selectedRunId }}</el-tag>
          </div>
        </div>
      </template>

      <el-alert
        title="Sandbox code can read /workspace/input and /workspace/working. Write generated files only to /workspace/output."
        type="info"
        :closable="false"
      />

      <el-input
        v-model="sandboxCode"
        type="textarea"
        :rows="10"
        class="result-block"
      />

      <div class="tag-list result-block">
        <el-button
          type="primary"
          :loading="sandboxLoading"
          :disabled="!sandboxCode.trim()"
          @click="executeSandbox"
        >
          Execute isolated Python
        </el-button>
        <el-tag type="info">
          {{ sandboxHealth?.security.cpu_limit ?? 1 }} CPU
        </el-tag>
        <el-tag type="info">
          {{ sandboxHealth?.security.memory_limit_mb ?? 512 }} MB
        </el-tag>
        <el-tag type="info">
          {{ sandboxHealth?.security.timeout_seconds ?? 60 }}s timeout
        </el-tag>
      </div>

      <div v-if="sandboxResult" class="result-block">
        <div class="tag-list">
          <el-tag :type="statusType(sandboxResult.status)">
            {{ sandboxResult.status }}
          </el-tag>
          <el-tag type="info">exit {{ sandboxResult.exit_code ?? "n/a" }}</el-tag>
          <el-tag type="info">{{ sandboxResult.duration_ms.toFixed(1) }} ms</el-tag>
          <el-tag type="success">{{ sandboxResult.artifacts.length }} artifact(s)</el-tag>
        </div>
        <p><strong>stdout</strong></p>
        <pre>{{ sandboxResult.stdout || "(empty)" }}</pre>
        <p v-if="sandboxResult.stderr"><strong>stderr</strong></p>
        <pre v-if="sandboxResult.stderr">{{ sandboxResult.stderr }}</pre>
      </div>
    </el-card>

    <el-card
      v-if="currentUser && workspace"
      class="status-card result-block"
      shadow="never"
    >
      <template #header>
        <div class="card-header">
          <strong>Workspace Inspector</strong>
          <el-tag type="info">{{ selectedRunId }}</el-tag>
        </div>
      </template>

      <div class="status-grid">
        <div class="status-item">
          <span>Used</span>
          <strong>{{ workspace.used_bytes }} bytes</strong>
        </div>
        <div class="status-item">
          <span>Quota</span>
          <strong>{{ workspace.quota_bytes }} bytes</strong>
        </div>
        <div class="status-item">
          <span>Max file</span>
          <strong>{{ workspace.max_file_bytes }} bytes</strong>
        </div>
        <div class="status-item">
          <span>Status</span>
          <el-tag type="success">{{ workspace.status }}</el-tag>
        </div>
      </div>

      <div class="agent-grid result-block">
        <div>
          <h3>working/</h3>
          <el-empty
            v-if="workingFiles.length === 0"
            description="No working files"
          />
          <div
            v-for="file in workingFiles"
            :key="file.path"
            class="status-item"
          >
            <span>{{ file.path }}</span>
            <el-tag type="info">{{ file.size_bytes }} B</el-tag>
          </div>
        </div>

        <div v-if="canReadArtifacts">
          <h3>Artifacts</h3>
          <el-empty
            v-if="artifacts.length === 0"
            description="No published artifacts"
          />
          <div
            v-for="artifact in artifacts"
            :key="artifact.id"
            class="status-item"
          >
            <div>
              <strong>{{ artifact.display_name }}</strong>
              <p class="muted">
                {{ artifact.kind }} · {{ artifact.media_type }} ·
                {{ artifact.size_bytes }} B
              </p>
            </div>
            <el-tag type="success">published</el-tag>
          </div>
        </div>
      </div>
    </el-card>
  </main>
</template>
