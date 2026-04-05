// src/services/websocket.js
import { API_BASE_URL, dispatchSessionExpired } from "./api";
import settings from "../../../configs/settings.json";

let sockets = {}; // manage multiple sockets by type
let callbacks = {}; // store message/close callbacks by type
let intentionalClose = {}; // suppress noise for expected reconnect/teardown closes

function getCallbacks(type) {
  if (!callbacks[type]) {
    callbacks[type] = {
      onMessage: () => {},
      onClose: () => {},
    };
  }
  return callbacks[type];
}

function sendWhenOpen(ws, payload) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(payload);
    return;
  }

  if (ws.readyState === WebSocket.CONNECTING) {
    ws.addEventListener(
      "open",
      () => {
        ws.send(payload);
      },
      { once: true }
    );
    return;
  }

  throw new Error("WebSocket is not open");
}

function resolveWsBaseUrl() {
  const backendCfg = settings?.network?.backend || {};
  const wsProtocol = backendCfg.ws_protocol;
  const configuredPublicHost = (backendCfg.public_host || "").trim();
  if (!wsProtocol) {
    throw new Error("network.backend.ws_protocol must be set in configs/settings.json");
  }
  const host = configuredPublicHost || window.location.hostname;
  const port = Number(backendCfg.port);
  if (!Number.isFinite(port) || port <= 0) {
    throw new Error("network.backend.port must be set in configs/settings.json");
  }
  const configuredBase = `${wsProtocol}://${host}:${port}`;
  if (configuredBase) return configuredBase;

  if (API_BASE_URL) {
    try {
      const parsed = new URL(API_BASE_URL);
      const protocol = parsed.protocol === "https:" ? "wss:" : "ws:";
      return `${protocol}//${parsed.host}`;
    } catch {
      // Fall through to local fallback.
    }
  }

  return configuredBase;
}

async function buildRuntimeHint(code) {
  try {
    const res = await fetch(`${API_BASE_URL}/health/runtime`, {
      method: "GET",
      credentials: "include",
    });
    if (!res.ok) {
      return `⚠️ WebSocket closed unexpectedly (code ${code}). Backend responded ${res.status}; check backend logs.`;
    }
    const data = await res.json();
    const mode = data?.kb_reindex_mode || "unknown";
    return `⚠️ WebSocket closed unexpectedly (code ${code}). Backend is reachable (${data?.status || "ok"}); check auth/session or backend worker logs. KB reindex mode: ${mode}.`;
  } catch {
    return `⚠️ WebSocket closed unexpectedly (code ${code}). Backend may be down or on a different port. Confirm backend is running and reachable.`;
  }
}

/**
 * Connect WebSocket for a given type and provide streaming callbacks
 * @param {function} onMessage - called with streaming token
 * @param {function} onClose - called when socket closes
 * @param {string} type - 'ask' | 'lesson' | 'quiz'
 */
export function connectWebSocket(onMessage, onClose = () => {}, type = "ask") {
  const token = localStorage.getItem("token");
  const wsBaseUrl = resolveWsBaseUrl();
  const urlBase = `${wsBaseUrl}/ws/${type}`;
  const cb = getCallbacks(type);
  cb.onMessage = onMessage;
  cb.onClose = onClose;

  // Close existing socket if any
  if (sockets[type]) {
    intentionalClose[type] = true;
    sockets[type].close();
  }

  const protocols = token ? [`chat.${token}`] : undefined;
  const ws = protocols ? new WebSocket(urlBase, protocols) : new WebSocket(urlBase);
  ws.__hasActivity = false;
  sockets[type] = ws;

  ws.onopen = () => {
    ws.__hasActivity = false;
    console.log(`✅ ${type} WebSocket Connected`);
  };
  intentionalClose[type] = false;

  ws.onmessage = (event) => {
    const current = getCallbacks(type);
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "chunk") {
        ws.__hasActivity = true;
        current.onMessage(msg.data);
      }
      if (msg.type === "end") {
        ws.__hasActivity = false;
        current.onMessage("[END]");
      }
      if (msg.type === "error") {
        ws.__hasActivity = false;
        console.error(`❌ ${type} Server Error:`, msg.data);
        if (msg.data) {
          current.onMessage(`\n\n${msg.data}`);
        }
        current.onMessage("[END]");
      }
    } catch {
      // fallback for plain text
      ws.__hasActivity = true;
      current.onMessage(event.data);
    }
  };

  ws.onerror = (error) => {
    const current = getCallbacks(type);
    // Browsers may emit onerror when a CONNECTING socket is intentionally closed during teardown.
    if (intentionalClose[type]) return;
    console.error(`❌ ${type} WebSocket Error:`, error);
    if (!ws.__hasActivity) {
      return;
    }
    current.onMessage(
      "\n\n⚠️ Connection error while contacting the AI server. Verifying backend health..."
    );
    current.onMessage("[END]");
  };

  ws.onclose = (event) => {
    const current = getCallbacks(type);
    const wasIntentional = Boolean(intentionalClose[type]);
    intentionalClose[type] = false;
    // 1008 = Policy Violation — backend sends this when JWT is missing/expired
    if (event.code === 1008) {
      console.warn(`🔒 ${type} WebSocket closed: session expired (1008)`);
      dispatchSessionExpired();
      return;
    }
    console.log(`🔌 ${type} WebSocket Closed (code ${event.code})`);
    const shouldShowCloseHint = !wasIntentional
      && Boolean(ws.__hasActivity)
      && event.code !== 1000
      && event.code !== 1001
      && event.code !== 1005;
    if (shouldShowCloseHint) {
      buildRuntimeHint(event.code).then((hint) => {
        current.onMessage(`\n\n${hint}`);
      });
    }
    current.onClose();
    current.onMessage("[END]");
  };

  return ws;
}

/**
 * Send message via WebSocket
 * @param {string} type - 'ask' | 'lesson' | 'quiz'
 * @param {object|string} message
 * @param {function} onMessage - streaming callback for this message
 */
export function sendMessage(type = "ask", message, onMessage) {
  // Backward-compatible call shape: sendMessage(message)
  if (typeof type === "object" && message === undefined) {
    message = type;
    type = "ask";
  }

  if (onMessage) {
    const cb = getCallbacks(type);
    cb.onMessage = onMessage;
  }

  if (!sockets[type] || sockets[type].readyState === WebSocket.CLOSED) {
    console.warn(`⚠️ ${type} WebSocket not connected, connecting...`);
    const cb = getCallbacks(type);
    connectWebSocket(cb.onMessage, cb.onClose, type);
  }

  const ws = sockets[type];
  if (!ws) {
    console.error(`❌ ${type} WebSocket unavailable`);
    return;
  }

  try {
    const payload = typeof message === "object" ? JSON.stringify(message) : message;
    ws.__hasActivity = true;
    sendWhenOpen(ws, payload);
  } catch (err) {
    console.error(`❌ ${type} Send Error:`, err);
  }
}

/**
 * Close WebSocket manually
 * @param {string} type - 'ask' | 'lesson' | 'quiz'
 */
export function closeSocket(type = "ask") {
  if (sockets[type]) {
    intentionalClose[type] = true;
    sockets[type].close();
    sockets[type] = null;
    console.log(`🛑 ${type} WebSocket manually closed`);
  }
}