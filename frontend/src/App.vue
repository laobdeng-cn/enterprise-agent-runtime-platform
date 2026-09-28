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

const backend = ref<DependencyState>("checking");
const database = ref<DependencyState>("checking");
const redis = ref<DependencyState>("checking");
const version = ref("0.5.0");

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
    await Promise.all([loadAgents(), loadSkills(), loadRuns()]);
  } catch {
    authError.value = "Authentication service is unavailable.";
  } finally {
    authLoading.value = false;
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
  sessionStorage.removeItem("earp_access_token");
}

onMounted(async () => {
  await refreshHealth();
  await loadCurrentUser();
  await Promise.all([loadAgents(), loadSkills(), loadRuns()]);
});
</script>

<template>
  <main class="page-shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Enterprise Agent Runtime Platform</p>
        <h1>Durable Agent Runtime</h1>
        <p class="subtitle">
          Phase 5 adds durable Run state, steps, checkpoints, bounded retry,
          cooperative lifecycle controls, persisted SSE events, and restart recovery.
        </p>
      </div>
      <el-tag :type="overallType" size="large" effect="dark">
        Phase 5 · v{{ version }}
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
        <template #header><strong>Runtime lifecycle</strong></template>
        <div class="flow">
          <span>PENDING</span><span>→</span><span>RUNNING</span><span>→</span>
          <span>RETRYING / PAUSED</span><span>→</span>
          <span>COMPLETED / FAILED / CANCELLED</span>
        </div>
        <p class="muted">
          Run state and checkpoints live in PostgreSQL. Redis is not the source of truth.
        </p>
      </el-card>
    </section>

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
  </main>
</template>
