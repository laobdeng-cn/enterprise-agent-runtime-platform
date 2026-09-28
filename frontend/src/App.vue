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

const backend = ref<DependencyState>("checking");
const database = ref<DependencyState>("checking");
const redis = ref<DependencyState>("checking");
const version = ref("0.1.0");

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

onMounted(refreshHealth);
</script>

<template>
  <main class="page-shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Enterprise Agent Runtime Platform</p>
        <h1>Engineering Skeleton</h1>
        <p class="subtitle">
          Phase 1 establishes the control-plane foundation before Agent Harness,
          Skills, durable Runs, Sandbox, MCP, and evaluation are introduced.
        </p>
      </div>

      <el-tag :type="overallType" size="large" effect="dark">
        Phase 1 · v{{ version }}
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

    <section class="foundation-grid">
      <el-card shadow="hover">
        <h2>Control Plane</h2>
        <p>FastAPI, Pydantic Settings, SQLAlchemy, Alembic, and health contracts.</p>
      </el-card>
      <el-card shadow="hover">
        <h2>Infrastructure</h2>
        <p>PostgreSQL 16, Redis, Docker Compose, explicit dependency health checks.</p>
      </el-card>
      <el-card shadow="hover">
        <h2>Next Boundary</h2>
        <p>Phase 2 adds identity, JWT authentication, roles, permissions, and RBAC.</p>
      </el-card>
    </section>
  </main>
</template>
