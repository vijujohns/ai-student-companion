/**
 * Centralized API fetch wrapper.
 *
 * Any 401 response from the backend triggers a "session:expired" CustomEvent
 * on window, which App.jsx listens to and uses to redirect the user to login
 * with an on-screen message.
 */

import settings from "../../../configs/settings.json";

function resolveApiBaseUrl() {
  const backendCfg = settings?.network?.backend || {};
  const protocol = backendCfg.protocol;
  const configuredPublicHost = (backendCfg.public_host || "").trim();
  if (!protocol) {
    throw new Error("network.backend.protocol must be set in configs/settings.json");
  }
  const host = configuredPublicHost || window.location.hostname;
  const port = Number(backendCfg.port);
  if (!Number.isFinite(port) || port <= 0) {
    throw new Error("network.backend.port must be set in configs/settings.json");
  }
  return `${protocol}://${host}:${port}`;
}

const API_BASE_URL = resolveApiBaseUrl();

export function clearStoredSessionState() {
  localStorage.removeItem("token");
  localStorage.removeItem("session_id");
  localStorage.removeItem("lesson_session_id");
  localStorage.removeItem("quiz_session_id");
  localStorage.removeItem("flashcard_session_id");
  localStorage.removeItem("username");
  localStorage.removeItem("role");
}

/**
 * Drop-in replacement for fetch() that:
 *  - Automatically injects the Bearer token from localStorage
 *  - Detects 401 responses and fires the session:expired event
 *
 * @param {string} path   - API path, e.g. "/sessions"
 * @param {RequestInit} options - standard fetch options (headers merged, not replaced)
 * @returns {Promise<Response>}
 */
export async function apiFetch(path, options = {}) {
  const { headers: optionHeaders, skipSessionExpiredEvent = false, ...fetchOptions } = options;
  const token = localStorage.getItem("token");

  const headers = {
    ...(optionHeaders || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...fetchOptions,
    credentials: "include",
    headers,
  });

  if (res.status === 401 && !skipSessionExpiredEvent) {
    dispatchSessionExpired();
    // Return the response so callers can still inspect it if needed,
    // but the app will be redirected before the caller does anything useful.
    return res;
  }

  return res;
}

export function getEnvelopeMessage(payload) {
  const message = payload?.message;
  if (!message || typeof message !== "object") return null;
  if (!message.message_id || !message.level || !message.user_text) return null;
  return message;
}

export function messageSummary(message) {
  if (!message) return "";
  const id = message.message_id || "MSG-1000";
  const level = String(message.level || "INFO").toUpperCase();
  const text = message.user_text || "Operation completed.";
  return `[${id} | ${level}] ${text}`;
}

export async function parseApiError(res, fallback = "Request failed.") {
  let payload = null;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }

  const message = getEnvelopeMessage(payload);
  if (message) return messageSummary(message);

  const detail = payload?.detail ?? payload?.error ?? payload;
  if (typeof detail === "string" && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const first = detail.find((entry) => entry?.msg || typeof entry === "string");
    if (typeof first === "string") return first;
    if (typeof first?.msg === "string") return first.msg;
  }

  if (detail && typeof detail === "object") {
    if (typeof detail.message === "string") return detail.message;
    if (typeof detail.msg === "string") return detail.msg;
  }

  return fallback;
}

/**
 * Clear auth state from localStorage and fire the session:expired event.
 * Also exported so websocket.js can call it on WS close code 1008.
 */
export function dispatchSessionExpired() {
  clearStoredSessionState();
  window.dispatchEvent(new CustomEvent("session:expired"));
}

export { API_BASE_URL };
