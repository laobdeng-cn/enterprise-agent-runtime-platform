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
  system_instructions: string;
  model_provider: string;
  model_name: string;
  temperature: number | null;
  max_tokens: number | null;
  context_policy: Record<string, unknown>;
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

interface SkillVersion {
  id: string;
  version: number;
  required_permissions: string[];
  side_effect: string;
  timeout_seconds: number;
  max_attempts: number;
}

interface Skill {
  id: string;
  name: string;
  description: string;
  provider_type: string;
  status: string;
  active_version_id: string | null;
  versions: SkillVersion[];
}

interface AgentInvokeResponse {
  agent_id: string;
  agent_version_id: string;
  agent_version: number;
  content: string;
  provider: string;
  model: string;
  finish_reason: string | null;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  duration_ms: number;
  tool_results: Array<Record<string, unknown>>;
}

const backend = ref<DependencyState>("checking");
const database = ref<DependencyState>("checking");
const redis = ref<DependencyState>("checking");
const version = ref("0.4.0");

const username = ref("");
const password = ref("");
const authError = ref("");
const authLoading = ref(false);
const token = ref(sessionStorage.getItem("earp_access_token") ?? "");
const currentUser = ref<CurrentUser | null>(null);

const agents = ref<Agent[]>([]);
const agentsLoading = ref(false);
const skills = ref<Skill[]>([]);
const skillsLoading = ref(false);
const agentError = ref("");
const newAgentName = ref("");
const newAgentInstructions = ref("You are a concise enterprise assistant.");
const selectedNewAgentSkills = ref<string[]>([]);
const selectedAgentId = ref("");
const previewInput = ref("");
const previewLoading = ref(false);
const previewResult = ref<AgentInvokeResponse | null>(null);

const overallType = computed(() => {
  if (backend.value === "checking") return "info";
  return backend.value === "ok" && database.value === "ok" && redis.value === "ok"
    ? "success"
    : "danger";
});

const canReadAgents = computed(
  () => currentUser.value?.permissions.includes("agent:read") ?? false,
);
const canCreateAgents = computed(
  () => currentUser.value?.permissions.includes("agent:create") ?? false,
);
const canReadSkills = computed(
  () => currentUser.value?.permissions.includes("skill:read") ?? false,
);
const canRunAgents = computed(
  () =>
    (currentUser.value?.permissions.includes("agent:read") ?? false) &&
    (currentUser.value?.permissions.includes("run:create") ?? false),
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
  if (!currentUser.value || !canReadAgents.value) {
    agents.value = [];
    return;
  }

  agentsLoading.value = true;
  agentError.value = "";
  try {
    const response = await apiFetch("/api/agents");
    if (!response.ok) {
      agentError.value = await response.text();
      return;
    }
    agents.value = (await response.json()) as Agent[];
    if (!selectedAgentId.value && agents.value.length > 0) {
      selectedAgentId.value = agents.value[0].id;
    }
  } catch {
    agentError.value = "Agent API is unavailable.";
  } finally {
    agentsLoading.value = false;
  }
}

async function loadSkills(): Promise<void> {
  if (!currentUser.value || !canReadSkills.value) {
    skills.value = [];
    return;
  }

  skillsLoading.value = true;
  try {
    const response = await apiFetch("/api/skills");
    if (!response.ok) return;
    skills.value = (await response.json()) as Skill[];
  } finally {
    skillsLoading.value = false;
  }
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
    await Promise.all([loadAgents(), loadSkills()]);
  } catch {
    authError.value = "Authentication service is unavailable.";
  } finally {
    authLoading.value = false;
  }
}

async function createAgent(): Promise<void> {
  if (!newAgentName.value.trim() || !newAgentInstructions.value.trim()) return;

  agentError.value = "";
  try {
    const response = await apiFetch("/api/agents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: newAgentName.value.trim(),
        description: "Created from the Phase 4 console.",
        system_instructions: newAgentInstructions.value,
        model_provider: "deepseek",
        model_name: "deepseek-chat",
        temperature: 0.2,
        skills: selectedNewAgentSkills.value,
      }),
    });

    if (!response.ok) {
      agentError.value = await response.text();
      return;
    }

    const created = (await response.json()) as Agent;
    newAgentName.value = "";
    selectedNewAgentSkills.value = [];
    selectedAgentId.value = created.id;
    await loadAgents();
  } catch {
    agentError.value = "Could not create Agent.";
  }
}

async function previewAgent(): Promise<void> {
  if (!selectedAgentId.value || !previewInput.value.trim()) return;

  previewLoading.value = true;
  previewResult.value = null;
  agentError.value = "";

  try {
    const response = await apiFetch(
      `/api/agents/${selectedAgentId.value}/preview`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input: previewInput.value,
          additional_context: [],
        }),
      },
    );

    if (!response.ok) {
      agentError.value = await response.text();
      return;
    }

    previewResult.value = (await response.json()) as AgentInvokeResponse;
  } catch {
    agentError.value = "Harness preview request failed.";
  } finally {
    previewLoading.value = false;
  }
}

function logout(): void {
  token.value = "";
  currentUser.value = null;
  agents.value = [];
  skills.value = [];
  selectedAgentId.value = "";
  selectedNewAgentSkills.value = [];
  previewResult.value = null;
  sessionStorage.removeItem("earp_access_token");
}

onMounted(async () => {
  await refreshHealth();
  await loadCurrentUser();
  await Promise.all([loadAgents(), loadSkills()]);
});
</script>

<template>
  <main class="page-shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Enterprise Agent Runtime Platform</p>
        <h1>Tool / Skill Registry</h1>
        <p class="subtitle">
          Phase 4 adds versioned Skills, JSON Schema validation, RBAC-aware execution,
          bounded timeout/retry handling, and dynamic Skill binding for Agent versions.
        </p>
      </div>

      <el-tag :type="overallType" size="large" effect="dark">
        Phase 4 · v{{ version }}
      </el-tag>
    </section>

    <el-card class="status-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>Local infrastructure</span>
          <el-button text type="primary" @click="refreshHealth">Refresh</el-button>
        </div>
      </template>

      <div class="status-grid">
        <div class="status-item"><span>Frontend</span><el-tag type="success">ok</el-tag></div>
        <div class="status-item">
          <span>Backend</span>
          <el-tag :type="backend === 'ok' ? 'success' : backend === 'checking' ? 'info' : 'danger'">
            {{ backend }}
          </el-tag>
        </div>
        <div class="status-item">
          <span>PostgreSQL</span>
          <el-tag :type="database === 'ok' ? 'success' : database === 'checking' ? 'info' : 'danger'">
            {{ database }}
          </el-tag>
        </div>
        <div class="status-item">
          <span>Redis</span>
          <el-tag :type="redis === 'ok' ? 'success' : redis === 'checking' ? 'info' : 'danger'">
            {{ redis }}
          </el-tag>
        </div>
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
            <el-input
              v-model="password"
              type="password"
              show-password
              autocomplete="current-password"
              @keyup.enter="login"
            />
          </el-form-item>
          <el-alert
            v-if="authError"
            :title="authError"
            type="error"
            show-icon
            :closable="false"
            class="auth-alert"
          />
          <el-button
            type="primary"
            :loading="authLoading"
            :disabled="!username || !password"
            @click="login"
          >
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
            <dt>Permissions</dt>
            <dd class="tag-list">
              <el-tag
                v-for="permission in currentUser.permissions"
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
        <template #header><strong>Controlled execution boundary</strong></template>
        <div class="flow">
          <span>LLM Tool Call</span><span>→</span><span>Bound SkillVersion</span>
          <span>→</span><span>JSON Schema</span><span>→</span>
          <span>RBAC</span><span>→</span><span>Timeout / Retry</span>
        </div>
        <p class="muted">
          Tool arguments are untrusted model output. They are validated and authorized
          before any provider adapter executes them.
        </p>
      </el-card>
    </section>

    <section v-if="currentUser && canReadAgents" class="agent-grid">
      <el-card v-if="canCreateAgents" shadow="never">
        <template #header><strong>Create versioned Agent</strong></template>
        <el-form label-position="top">
          <el-form-item label="Agent name">
            <el-input v-model="newAgentName" placeholder="research-assistant" />
          </el-form-item>
          <el-form-item label="System instructions">
            <el-input
              v-model="newAgentInstructions"
              type="textarea"
              :rows="5"
            />
          </el-form-item>
          <el-form-item v-if="canReadSkills" label="Bound Skills">
            <el-select
              v-model="selectedNewAgentSkills"
              multiple
              clearable
              placeholder="Select only the capabilities this Agent may use"
            >
              <el-option
                v-for="skill in skills"
                :key="skill.id"
                :label="skill.name"
                :value="skill.name"
              />
            </el-select>
          </el-form-item>
          <el-button
            type="primary"
            :disabled="!newAgentName.trim() || !newAgentInstructions.trim()"
            @click="createAgent"
          >
            Create Agent v1
          </el-button>
        </el-form>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <strong>Harness + Skills preview</strong>
            <el-button text :loading="agentsLoading" @click="loadAgents">Reload</el-button>
          </div>
        </template>

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
          <el-form-item label="User input">
            <el-input v-model="previewInput" type="textarea" :rows="4" />
          </el-form-item>
          <el-button
            type="primary"
            :loading="previewLoading"
            :disabled="!canRunAgents || !selectedAgentId || !previewInput.trim()"
            @click="previewAgent"
          >
            Execute through Harness
          </el-button>
        </el-form>

        <el-alert
          v-if="agentError"
          :title="agentError"
          type="error"
          show-icon
          :closable="false"
          class="result-block"
        />

        <div v-if="previewResult" class="result-block">
          <div class="result-meta">
            <el-tag>{{ previewResult.provider }}</el-tag>
            <el-tag type="info">{{ previewResult.model }}</el-tag>
            <span>{{ previewResult.usage.total_tokens }} tokens</span>
            <span>{{ previewResult.duration_ms.toFixed(1) }} ms</span>
            <span>{{ previewResult.tool_results.length }} tool result(s)</span>
          </div>
          <pre>{{ previewResult.content }}</pre>
        </div>
      </el-card>

      <el-card v-if="canReadSkills" shadow="never">
        <template #header>
          <div class="card-header">
            <strong>Skill Registry</strong>
            <el-button text :loading="skillsLoading" @click="loadSkills">Reload</el-button>
          </div>
        </template>
        <div class="principal-grid">
          <div v-for="skill in skills" :key="skill.id">
            <dt>{{ skill.name }}</dt>
            <dd>
              <div class="tag-list">
                <el-tag>{{ skill.provider_type }}</el-tag>
                <el-tag type="info">{{ skill.status }}</el-tag>
                <el-tag
                  v-if="skill.versions.length"
                  type="success"
                >
                  v{{ skill.versions[skill.versions.length - 1].version }}
                </el-tag>
              </div>
              <p class="muted">{{ skill.description }}</p>
            </dd>
          </div>
        </div>
      </el-card>
    </section>
  </main>
</template>
