import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  apiFetch,
  clearStoredSessionState,
  dispatchSessionExpired,
  flushOfflineMutationQueue,
  getOfflinePendingCount,
  getEnvelopeMessage,
  messageSummary,
  parseApiError,
} from "../../../frontend/src/services/api";
import { connectWebSocket, closeSocket, sendMessage } from "../../../frontend/src/services/websocket";

class FakeWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;

  constructor(url, protocols) {
    this.url = url;
    this.protocols = protocols;
    this.readyState = FakeWebSocket.OPEN;
    this.onopen = null;
    this.onmessage = null;
    this.onerror = null;
    this.onclose = null;
    this.sent = [];
    this.listeners = {};
  }

  send(payload) {
    this.sent.push(payload);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
    if (this.onclose) this.onclose({ code: 1000 });
  }

  addEventListener(event, handler) {
    this.listeners[event] = handler;
  }
}

describe("API service", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("apiFetch injects bearer token", async () => {
    localStorage.setItem("token", "jwt-123");
    fetch.mockResolvedValue({ status: 200, ok: true });

    await apiFetch("/sessions", { method: "GET" });

    expect(fetch).toHaveBeenCalledTimes(1);
    const [, options] = fetch.mock.calls[0];
    expect(options.headers.Authorization).toBe("Bearer jwt-123");
    expect(options.credentials).toBe("include");
  });

  it("clearStoredSessionState removes local auth markers without emitting events", () => {
    localStorage.setItem("token", "t");
    localStorage.setItem("username", "student");

    clearStoredSessionState();

    expect(localStorage.getItem("token")).toBeNull();
    expect(localStorage.getItem("username")).toBeNull();
  });

  it("dispatchSessionExpired clears auth state and emits event", () => {
    localStorage.setItem("token", "t");
    localStorage.setItem("session_id", "s");

    const handler = vi.fn();
    window.addEventListener("session:expired", handler);

    dispatchSessionExpired();

    expect(localStorage.getItem("token")).toBeNull();
    expect(localStorage.getItem("session_id")).toBeNull();
    expect(handler).toHaveBeenCalledTimes(1);

    window.removeEventListener("session:expired", handler);
  });

  it("apiFetch handles 401 by expiring session", async () => {
    localStorage.setItem("token", "t");
    fetch.mockResolvedValue({ status: 401, ok: false });

    const handler = vi.fn();
    window.addEventListener("session:expired", handler);

    await apiFetch("/secure");

    expect(localStorage.getItem("token")).toBeNull();
    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener("session:expired", handler);
  });

  it("envelope helpers parse valid message", () => {
    const payload = {
      message: {
        message_id: "MSG-1001",
        level: "info",
        user_text: "Saved",
      },
    };

    const msg = getEnvelopeMessage(payload);
    expect(msg).not.toBeNull();
    expect(messageSummary(msg)).toContain("MSG-1001");
  });

  it("parseApiError supports array/object fallback shapes", async () => {
    const res1 = { json: vi.fn().mockResolvedValue({ detail: [{ msg: "bad input" }] }) };
    const res2 = { json: vi.fn().mockResolvedValue({ detail: { message: "oops" } }) };

    await expect(parseApiError(res1)).resolves.toBe("bad input");
    await expect(parseApiError(res2)).resolves.toBe("oops");
  });

  it("queues mutation requests while offline", async () => {
    Object.defineProperty(window.navigator, "onLine", {
      configurable: true,
      value: false,
    });

    const response = await apiFetch("/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Offline session" }),
    });

    expect(response.status).toBe(202);
    expect(getOfflinePendingCount()).toBe(1);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("returns cached GET response when network fetch fails", async () => {
    fetch
      .mockResolvedValueOnce({
        status: 200,
        ok: true,
        clone: () => ({ json: async () => ({ items: [1, 2] }) }),
      })
      .mockRejectedValueOnce(new Error("offline"));

    const onlineRes = await apiFetch("/languages", { method: "GET" });
    expect(onlineRes.ok).toBe(true);

    const cachedRes = await apiFetch("/languages", { method: "GET" });
    const payload = await cachedRes.json();
    expect(payload.items).toEqual([1, 2]);
    expect(cachedRes.headers.get("X-Offline-Cache")).toBe("1");
  });

  it("flushes queued offline mutations after reconnect", async () => {
    Object.defineProperty(window.navigator, "onLine", {
      configurable: true,
      value: false,
    });

    await apiFetch("/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preferred_language: "hi" }),
    });
    expect(getOfflinePendingCount()).toBe(1);

    Object.defineProperty(window.navigator, "onLine", {
      configurable: true,
      value: true,
    });
    fetch.mockResolvedValue({ status: 200, ok: true });

    const result = await flushOfflineMutationQueue();
    expect(result.flushed).toBe(1);
    expect(result.remaining).toBe(0);
    expect(getOfflinePendingCount()).toBe(0);
  });
});

describe("WebSocket service", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    global.WebSocket = FakeWebSocket;
  });

  afterEach(() => {
    closeSocket("ask");
    closeSocket("lesson");
    closeSocket("quiz");
    vi.restoreAllMocks();
  });

  it("connectWebSocket includes chat token subprotocol", () => {
    localStorage.setItem("token", "abc.def.ghi");

    const ws = connectWebSocket(() => {}, () => {}, "ask");

    expect(ws.url).toContain("/ws/ask");
    expect(ws.protocols).toEqual(["chat.abc.def.ghi"]);
  });

  it("sendMessage sends serialized payload", () => {
    const ws = connectWebSocket(() => {}, () => {}, "lesson");

    sendMessage("lesson", { query: "hello" });

    expect(ws.sent.length).toBe(1);
    expect(ws.sent[0]).toContain("query");
  });

  it("onmessage chunk and end call callback", () => {
    const cb = vi.fn();
    const ws = connectWebSocket(cb, () => {}, "quiz");

    ws.onmessage({ data: JSON.stringify({ type: "chunk", data: "A" }) });
    ws.onmessage({ data: JSON.stringify({ type: "end" }) });

    expect(cb).toHaveBeenCalledWith("A");
    expect(cb).toHaveBeenCalledWith("[END]");
  });

  it("close code 1008 triggers session expiration", () => {
    localStorage.setItem("token", "t");
    const cb = vi.fn();
    const ws = connectWebSocket(cb, () => {}, "ask");

    const expiredHandler = vi.fn();
    window.addEventListener("session:expired", expiredHandler);

    ws.onclose({ code: 1008 });

    expect(localStorage.getItem("token")).toBeNull();
    expect(expiredHandler).toHaveBeenCalledTimes(1);
    window.removeEventListener("session:expired", expiredHandler);
  });

  it("does not surface a connection warning for idle websocket errors", () => {
    const cb = vi.fn();
    const ws = connectWebSocket(cb, () => {}, "ask");

    ws.onerror({ message: "idle reconnect noise" });

    expect(cb).not.toHaveBeenCalledWith(
      expect.stringContaining("Connection error while contacting the AI server")
    );
  });

  it("surfaces a connection warning when an active chat request fails", () => {
    const cb = vi.fn();
    connectWebSocket(cb, () => {}, "ask");

    sendMessage("ask", { query: "hello" });
    const activeWs = connectWebSocket(cb, () => {}, "ask");
    activeWs.__hasActivity = true;
    activeWs.onerror({ message: "network failure" });

    expect(cb).toHaveBeenCalledWith(
      expect.stringContaining("Connection error while contacting the AI server")
    );
    expect(cb).toHaveBeenCalledWith("[END]");
  });

  it("surfaces server error payloads before ending the stream", () => {
    const cb = vi.fn();
    const ws = connectWebSocket(cb, () => {}, "ask");

    ws.onmessage({ data: JSON.stringify({ type: "error", data: "Plan limit reached for this action." }) });

    expect(cb).toHaveBeenCalledWith(expect.stringContaining("Plan limit reached"));
    expect(cb).toHaveBeenCalledWith("[END]");
  });
});
