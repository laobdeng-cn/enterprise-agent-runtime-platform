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

const backend = ref<DependencyState>("checking");
const database = ref<DependencyState>("checking");
const redis = ref<DependencyState>("checking");
const version = ref("0.2.0");

const username = ref("");
const password = ref("");
const authError = ref("");
const authLoading = ref(false);
const token = ref(sessionStorage.getItem("earp_access_token") ?? "");
const currentUser = ref<CurrentUser | null>(null);

const overallType = computed(() => {
  if (backend.value === "checking") return "info";
  return backend.value === "ok" && database.value === "ok" && redis.value === "ok"
    ? "success"
    : "danger";
});

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

  const response = await fetch("/api/auth/me", {
    headers: {
      Authorization: `Bearer ${token.value}`,
    },
  });

  if (!response.ok) {
    logout();
    return;
  }

  currentUser.value = (await response.json()) as CurrentUser;
}

async function login(): Promise<void> {
  authError.value = "";
  authLoading.value = true;

  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
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
  } catch {
    authError.value = "Authentication service is unavailable.";
  } finally {
    authLoading.value = false;
  }
}

function logout(): void {
  token.value = "";
  currentUser.value = null;
  sessionStorage.removeItem("earp_access_token");
}

onMounted(async () => {
  await refreshHealth();
  await loadCurrentUser();
});
</script>

<template>
  <main class="page-shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Enterprise Agent Runtime Platform</p>
        <h1>Authentication & RBAC</h1>
        <p class="subtitle">
          Phase 2 establishes authenticated principals, version-independent roles,
          atomic permissions, and deterministic authorization outside the LLM.
        </p>
      </div>

      <el-tag :type="overallType" size="large" effect="dark">
        Phase 2 · v{{ version }}
      </el-tag>
    </section>

    <el-card class="status-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>Local infrastructure</span>
          <el-button text type="primary" @click="refreshHealth">
            Refresh
          </el-button>
        </div>
      </template>

      <div class="status-grid">
        <div class="status-item">
          <span>Frontend</span>
          <el-tag type="success">ok</el-tag>
        </div>
        <div class="status-item">
          <span>Backend</span>
          <el-tag
            :type="backend === 'ok' ? 'success' : backend === 'checking' ? 'info' : 'danger'"
          >
            {{ backend }}
          </el-tag>
        </div>
        <div class="status-item">
          <span>PostgreSQL</span>
          <el-tag
            :type="database === 'ok' ? 'success' : database === 'checking' ? 'info' : 'danger'"
          >
            {{ database }}
          </el-tag>
        </div>
        <div class="status-item">
          <span>Redis</span>
          <el-tag
            :type="redis === 'ok' ? 'success' : redis === 'checking' ? 'info' : 'danger'"
          >
            {{ redis }}
          </el-tag>
        </div>
      </div>
    </el-card>

    <section class="auth-grid">
      <el-card v-if="!currentUser" shadow="never">
        <template #header>
          <strong>Sign in</strong>
        </template>

        <el-form label-position="top" @submit.prevent="login">
          <el-form-item label="Username">
            <el-input
              v-model="username"
              autocomplete="username"
              placeholder="Bootstrap or provisioned user"
            />
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
          <div>
            <dt>Username</dt>
            <dd>{{ currentUser.username }}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>
              <el-tag :type="currentUser.is_active ? 'success' : 'danger'">
                {{ currentUser.is_active ? "active" : "inactive" }}
              </el-tag>
            </dd>
          </div>
          <div>
            <dt>Roles</dt>
            <dd class="tag-list">
              <el-tag v-for="role in currentUser.roles" :key="role">
                {{ role }}
              </el-tag>
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
        <template #header>
          <strong>Authorization boundary</strong>
        </template>
        <div class="flow">
          <span>Authenticated User</span>
          <span>→</span>
          <span>JWT</span>
          <span>→</span>
          <span>Current Principal</span>
          <span>→</span>
          <span>RBAC</span>
          <span>→</span>
          <span>Protected API</span>
        </div>
        <p class="muted">
          The model never grants permissions. Later Tool, Skill, MCP, Workspace,
          and Approval layers reuse this same principal and permission model.
        </p>
      </el-card>
    </section>
  </main>
</template>
