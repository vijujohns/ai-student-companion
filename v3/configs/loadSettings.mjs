import baseSettings from "./settings.base.json" with { type: "json" };
import devSettings from "./settings.dev.json" with { type: "json" };
import testSettings from "./settings.test.json" with { type: "json" };
import prodExampleSettings from "./settings.prod.example.json" with { type: "json" };
import { ENV_NAMES } from "./envNames.mjs";

const ENV_ALIASES = {
  development: "dev",
  debug: "dev",
  local: "dev",
  dev: "dev",
  production: "prod",
  live: "prod",
  prod: "prod",
  testing: "test",
  test: "test",
};

function isPlainObject(value) {
  return value && typeof value === "object" && !Array.isArray(value);
}

export function normalizeAppEnv(value = "") {
  const raw = String(value || "").trim().toLowerCase();
  return ENV_ALIASES[raw] || raw || "dev";
}

export function mergeSettings(base, overlay) {
  if (!isPlainObject(base)) return overlay;
  if (!isPlainObject(overlay)) return base;

  const merged = { ...base };
  for (const [key, value] of Object.entries(overlay)) {
    merged[key] = isPlainObject(value) && isPlainObject(merged[key])
      ? mergeSettings(merged[key], value)
      : value;
  }
  return merged;
}

function envFromRuntime() {
  const viteEnv = typeof import.meta !== "undefined" ? import.meta.env : undefined;
  if (viteEnv?.[ENV_NAMES.VITE_APP_ENV]) return viteEnv[ENV_NAMES.VITE_APP_ENV];
  if (viteEnv?.MODE) return viteEnv.MODE;
  if (typeof process !== "undefined" && process?.env) {
    return process.env[ENV_NAMES.APP_ENV] || process.env[ENV_NAMES.NODE_ENV] || "";
  }
  return "";
}

export function loadSettings(appEnv = envFromRuntime()) {
  const normalized = normalizeAppEnv(appEnv);
  const overlays = {
    dev: devSettings,
    test: testSettings,
    prod: prodExampleSettings,
  };
  return mergeSettings(baseSettings, overlays[normalized] || devSettings);
}

export default loadSettings();
