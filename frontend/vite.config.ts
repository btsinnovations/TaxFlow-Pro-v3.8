import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { inspectAttr } from "kimi-plugin-inspect-react";

export default defineConfig({
  base: "./",
  plugins: [inspectAttr(), react()],
  server: {
    watch: {
      ignored: ["**/venv/**", "**/node_modules/**", "**/.git/**"],
    },
    port: 3000,
  },
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      external: ["./src/data/mockData", "./src/mocks/browser", "./src/mocks/handlers", "./src/mocks/server"],
    },
  },
  define: {
    "import.meta.env.MOCK_DATA": JSON.stringify(false),
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    pool: "forks",
    poolOptions: {
      forks: {
        maxForks: 1,
      },
    },
  },
});
