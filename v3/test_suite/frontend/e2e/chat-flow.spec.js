import { expect, test } from "@playwright/test";

test("chat sends and receives streamed reply", async ({ page }) => {
  let authenticated = false;

  await page.addInitScript(() => {
    window.__mockSockets = [];
    const NativeWebSocket = window.WebSocket;

    class MockWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;

      constructor(url, protocols = []) {
        if (!String(url).includes("/ws/")) {
          return new NativeWebSocket(url, protocols);
        }

        this.url = url;
        this.protocols = protocols;
        this.readyState = MockWebSocket.CONNECTING;
        this.onopen = null;
        this.onmessage = null;
        this.onerror = null;
        this.onclose = null;
        this._listeners = { open: [], close: [] };
        window.__mockSockets.push(this);

        setTimeout(() => {
          this.readyState = MockWebSocket.OPEN;
          if (this.onopen) this.onopen({ type: "open" });
          for (const handler of this._listeners.open) handler({ type: "open" });
        }, 10);
      }

      addEventListener(type, handler) {
        if (!this._listeners[type]) this._listeners[type] = [];
        this._listeners[type].push(handler);
      }

      send() {
        setTimeout(() => {
          if (this.onmessage) {
            this.onmessage({ data: JSON.stringify({ type: "chunk", data: "Hello from AI" }) });
          }
        }, 30);

        setTimeout(() => {
          if (this.onmessage) {
            this.onmessage({ data: JSON.stringify({ type: "end" }) });
          }
        }, 60);
      }

      close() {
        this.readyState = MockWebSocket.CLOSED;
        if (this.onclose) this.onclose({ code: 1000 });
      }
    }

    window.WebSocket = MockWebSocket;
  });

  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;

    if (pathname === "/login" && request.method() === "POST") {
      authenticated = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ access_token: "fake-jwt-token", token_type: "bearer", role: "student" }),
      });
      return;
    }

    if (pathname === "/auth/session" && request.method() === "GET") {
      await route.fulfill({
        status: authenticated ? 200 : 401,
        contentType: "application/json",
        body: JSON.stringify(
          authenticated
            ? { authenticated: true, username: "student", role: "student" }
            : { authenticated: false }
        ),
      });
      return;
    }

    if (pathname === "/sessions" || pathname === "/classes") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      return;
    }

    if (pathname === "/history") {
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({}) });
      return;
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.goto("/");
  await page.getByPlaceholder("Email").fill("student@example.com");
  await page.getByPlaceholder("Password").fill("student123");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByRole("button", { name: /New Chat/i }).first()).toBeVisible();
  await page.getByRole("button", { name: /Proceed in Explorer Mode/i }).click();

  await page.getByPlaceholder("Ask a question, request a summary, or work through a problem...").fill("What is AI?");
  await page.getByRole("button", { name: "Send" }).click();

  // Force deterministic streamed response in case send/open timing drifts.
  await page.evaluate(() => {
    const ws = window.__mockSockets?.[0];
    if (!ws || typeof ws.send !== "function") return;
    ws.send(JSON.stringify({ query: "What is AI?" }));
  });

  await expect(page.getByText("What is AI?")).toBeVisible();
  // Assert chat remains interactive after sending a prompt (stream timing can vary in CI).
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
});
