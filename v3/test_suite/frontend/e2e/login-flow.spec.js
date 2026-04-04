import { expect, test } from "@playwright/test";

test("user can login from UI", async ({ page }) => {
  const email = `e2e.${Date.now()}@example.com`;
  const password = "Pass@1234";
  let authenticated = false;

  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());

    const json = async (body, status = 200) => {
      await route.fulfill({
        status,
        headers: {
          "content-type": "application/json",
          "access-control-allow-origin": "http://127.0.0.1:4174",
          "access-control-allow-credentials": "true",
          "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
          "access-control-allow-headers": "*",
        },
        body: JSON.stringify(body),
      });
    };

    if (req.method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "access-control-allow-origin": "http://127.0.0.1:4174",
          "access-control-allow-credentials": "true",
          "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
          "access-control-allow-headers": "*",
        },
      });
      return;
    }

    if (url.pathname === "/login" && req.method() === "POST") {
      authenticated = true;
      await json({ access_token: "fake-jwt-token", token_type: "bearer", role: "student" });
      return;
    }

    if (url.pathname === "/auth/session" && req.method() === "GET") {
      await json({ authenticated, username: "student", role: "student" }, authenticated ? 200 : 401);
      return;
    }

    if (url.pathname === "/sessions") {
      await json([]);
      return;
    }

    if (url.pathname === "/classes") {
      await json(["Class 8"]);
      return;
    }

    await json({});
  });

  let loginStatus = null;
  page.on("response", (response) => {
    if (response.url().includes("/login") && response.request().method() === "POST") {
      loginStatus = response.status();
    }
  });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Login" })).toBeVisible();
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: "Continue" }).click();

  // Login should render chat workspace actions after token is stored.
  await expect(page.getByRole("button", { name: /New Chat/i }).first()).toBeVisible({ timeout: 15000 });

  expect(loginStatus).toBe(200);
});
