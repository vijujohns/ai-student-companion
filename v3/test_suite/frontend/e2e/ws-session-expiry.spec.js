import { test, expect } from "@playwright/test";

test("logs out automatically and shows a session expired message after websocket auth expiry", async ({ page }) => {
  await page.addInitScript(() => {
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

        setTimeout(() => {
          this.readyState = MockWebSocket.OPEN;
          if (this.onopen) this.onopen({ type: "open" });
          for (const handler of this._listeners.open) {
            handler({ type: "open" });
          }

          setTimeout(() => {
            this.readyState = MockWebSocket.CLOSED;
            const event = { code: 1008, reason: "Token expired" };
            if (this.onclose) this.onclose(event);
            for (const handler of this._listeners.close) {
              handler(event);
            }
          }, 50);
        }, 10);
      }

      addEventListener(type, handler) {
        if (!this._listeners[type]) {
          this._listeners[type] = [];
        }
        this._listeners[type].push(handler);
      }

      send() {}

      close() {
        this.readyState = MockWebSocket.CLOSED;
      }
    }

    window.WebSocket = MockWebSocket;
  });

  await page.route("http://127.0.0.1:8011/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;

    if (pathname === "/login" && request.method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "fake-jwt-token",
          token_type: "bearer",
          role: "student",
        }),
      });
      return;
    }

    if (pathname === "/sessions" || pathname === "/classes") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await page.goto("/");

  await page.getByPlaceholder("Email").fill("student@example.com");
  await page.getByPlaceholder("Password").fill("student123");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByText("Your session has expired. Please log in again.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Login" })).toBeVisible();
  await expect(page.getByPlaceholder("Email")).toBeVisible();

  const token = await page.evaluate(() => localStorage.getItem("token"));
  expect(token).toBeNull();
});
