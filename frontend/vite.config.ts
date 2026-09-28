import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendTarget = env.VITE_BACKEND_PROXY_TARGET || "http://localhost:8000";

  return {
    plugins: [vue()],
    server: {
      host: "0.0.0.0",
      port: 5173,
      proxy: {
        "/health": {
          target: backendTarget,
          changeOrigin: true,
        },
        "/api": {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
