/**
 * Centralized API fetch wrapper.
 *
 * Any 401 response from the backend triggers a "session:expired" CustomEvent
 * on window, which App.jsx listens to and uses to redirect the user to login
 * with an on-screen message.
 */

import settings from "../../../configs/settings.json";

const OFFLINE_MUTATION_QUEUE_KEY = "offline_mutation_queue_v1";
const OFFLINE_GET_CACHE_KEY = "offline_get_cache_v1";
const OFFLINE_QUEUE_MAX = 120;
const OFFLINE_CACHE_MAX = 180;

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

function canUseNavigatorOnline() {
  return typeof navigator !== "undefined" && typeof navigator.onLine === "boolean";
}

function isOnlineNow() {
  return canUseNavigatorOnline() ? navigator.onLine : true;
}

function readJsonStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeJsonStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage quota/runtime failures.
  }
}

function getMethod(options = {}) {
  return String(options.method || "GET").toUpperCase();
}

function buildRequestUrl(path) {
  return `${API_BASE_URL}${path}`;
}

function buildGetCacheKey(path) {
  return `${path}::${localStorage.getItem("username") || "anonymous"}`;
}

function cacheSuccessfulGet(path, payload) {
  const cache = readJsonStorage(OFFLINE_GET_CACHE_KEY, {});
  cache[buildGetCacheKey(path)] = {
    payload,
    ts: Date.now(),
  };
  const keys = Object.keys(cache);
  if (keys.length > OFFLINE_CACHE_MAX) {
    const overflow = keys
      .sort((a, b) => (cache[a]?.ts || 0) - (cache[b]?.ts || 0))
      .slice(0, keys.length - OFFLINE_CACHE_MAX);
    for (const key of overflow) delete cache[key];
  }
  writeJsonStorage(OFFLINE_GET_CACHE_KEY, cache);
}

function getCachedGetResponse(path) {
  const cache = readJsonStorage(OFFLINE_GET_CACHE_KEY, {});
  const cached = cache[buildGetCacheKey(path)];
  if (!cached?.payload) return null;
  return new Response(JSON.stringify(cached.payload), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "X-Offline-Cache": "1",
    },
  });
}

function getMutationQueue() {
  return readJsonStorage(OFFLINE_MUTATION_QUEUE_KEY, []);
}

function saveMutationQueue(items) {
  const next = Array.isArray(items) ? items.slice(-OFFLINE_QUEUE_MAX) : [];
  writeJsonStorage(OFFLINE_MUTATION_QUEUE_KEY, next);
  window.dispatchEvent(new CustomEvent("offline:queue-updated", { detail: { pending: next.length } }));
}

function queueOfflineMutation(path, options, headers) {
  const method = getMethod(options);
  if (method === "GET" || method === "HEAD") return false;
  const queue = getMutationQueue();
  queue.push({
    path,
    method,
    body: options?.body || null,
    headers: headers || {},
    queuedAt: Date.now(),
  });
  saveMutationQueue(queue);
  return true;
}

export function getOfflinePendingCount() {
  return getMutationQueue().length;
}

export async function flushOfflineMutationQueue() {
  if (!isOnlineNow()) return { flushed: 0, remaining: getOfflinePendingCount() };

  const queue = getMutationQueue();
  if (!queue.length) return { flushed: 0, remaining: 0 };

  const remaining = [];
  let flushed = 0;

  for (const job of queue) {
    try {
      const res = await fetch(buildRequestUrl(job.path), {
        method: job.method,
        credentials: "include",
        headers: job.headers || {},
        body: job.body,
      });
      if (!res.ok) {
        // Keep 5xx and transport-like retries queued; drop 4xx.
        if (res.status >= 500) remaining.push(job);
        continue;
      }
      flushed += 1;
    } catch {
      remaining.push(job);
    }
  }

  saveMutationQueue(remaining);
  return { flushed, remaining: remaining.length };
}

export function startOfflineSyncLoop() {
  const onOnline = async () => {
    const result = await flushOfflineMutationQueue();
    window.dispatchEvent(new CustomEvent("offline:sync-finished", { detail: result }));
  };
  window.addEventListener("online", onOnline);
  if (isOnlineNow()) {
    onOnline();
  }
  return () => window.removeEventListener("online", onOnline);
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
  const method = getMethod(fetchOptions);

  const headers = {
    ...(optionHeaders || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  if (!isOnlineNow()) {
    if (method === "GET") {
      const cached = getCachedGetResponse(path);
      if (cached) return cached;
    }
    const queued = queueOfflineMutation(path, fetchOptions, headers);
    if (queued) {
      return new Response(
        JSON.stringify({ queued: true, offline: true, message: "Request queued for sync." }),
        {
          status: 202,
          headers: { "Content-Type": "application/json", "X-Offline-Queued": "1" },
        }
      );
    }
  }

  let res;
  try {
    res = await fetch(buildRequestUrl(path), {
      ...fetchOptions,
      credentials: "include",
      headers,
    });
  } catch (err) {
    if (method === "GET") {
      const cached = getCachedGetResponse(path);
      if (cached) return cached;
    }
    const queued = queueOfflineMutation(path, fetchOptions, headers);
    if (queued) {
      return new Response(
        JSON.stringify({ queued: true, offline: true, message: "Request queued for sync." }),
        {
          status: 202,
          headers: { "Content-Type": "application/json", "X-Offline-Queued": "1" },
        }
      );
    }
    throw err;
  }

  if (res.ok && method === "GET") {
    try {
      const clone = res.clone();
      const payload = await clone.json();
      cacheSuccessfulGet(path, payload);
    } catch {
      // Ignore non-JSON payloads.
    }
  }

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
