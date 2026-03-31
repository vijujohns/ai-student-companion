import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  apiFetch,
  clearStoredSessionState,
  dispatchSessionExpired,
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
});
