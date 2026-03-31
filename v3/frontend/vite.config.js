import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import settings from "../configs/settings.json";

const frontendConfig = settings?.network?.frontend || {};
const host = frontendConfig.host;
const port = Number(frontendConfig.port);
const previewPort = Number(frontendConfig.preview_port);

if (!host) {
  throw new Error("network.frontend.host must be set in configs/settings.json");
}
if (!Number.isFinite(port) || port <= 0) {
  throw new Error("network.frontend.port must be set in configs/settings.json");
}
if (!Number.isFinite(previewPort) || previewPort <= 0) {
  throw new Error("network.frontend.preview_port must be set in configs/settings.json");
}

export default defineConfig({
  plugins: [react()],
  server: {
    host,
    port,
    fs: {
      allow: [".."],
    },
  },
  preview: {
    host,
    port: previewPort,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.js",
    include: ["../test_suite/frontend/unit/**/*.{test,spec}.{js,jsx,ts,tsx}"],
    exclude: ["../test_suite/frontend/e2e/**", "node_modules/**"],
  },
});
