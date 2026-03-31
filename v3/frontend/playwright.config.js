import { defineConfig } from "@playwright/test";
import settings from "../configs/settings.json" with { type: "json" };

const testNetwork = settings?.network?.testing || {};
const testHost = testNetwork.host;
const testFrontendPort = Number(testNetwork.frontend_port);
const testBackendPort = Number(testNetwork.backend_port);

if (!testHost) {
  throw new Error("network.testing.host must be set in configs/settings.json");
}
if (!Number.isFinite(testFrontendPort) || testFrontendPort <= 0) {
  throw new Error("network.testing.frontend_port must be set in configs/settings.json");
}
if (!Number.isFinite(testBackendPort) || testBackendPort <= 0) {
  throw new Error("network.testing.backend_port must be set in configs/settings.json");
}

const testBaseHttpUrl = `http://${testHost}:${testFrontendPort}`;
const testApiHttpUrl = `http://${testHost}:${testBackendPort}`;
const testApiWsUrl = `ws://${testHost}:${testBackendPort}`;

export default defineConfig({
  testDir: "../test_suite/frontend/e2e",
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL: testBaseHttpUrl,
    headless: true,
  },
  webServer: {
    command: `npm run dev -- --host ${testHost} --port ${testFrontendPort}`,
    url: testBaseHttpUrl,
    env: {
      ...process.env,
      VITE_API_BASE_URL: testApiHttpUrl,
      VITE_WS_BASE_URL: testApiWsUrl,
    },
    reuseExistingServer: true,
    timeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
});
