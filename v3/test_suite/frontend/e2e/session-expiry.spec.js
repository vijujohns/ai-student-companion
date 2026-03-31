import { test, expect } from "@playwright/test";

test("logs out automatically and shows a session expired message after a 401", async ({ page }) => {
  let expireSession = false;

  await page.route("http://127.0.0.1:8011/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;
    const auth = request.headers()["authorization"];

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

    if (pathname === "/sessions") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
      return;
    }

    if (pathname === "/classes") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(["Class 8"]),
      });
      return;
    }

    if (pathname === "/subjects") {
      if (expireSession) {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Token expired" }),
        });
        return;
      }

      await route.fulfill({
        status: auth ? 200 : 401,
        contentType: "application/json",
        body: JSON.stringify(auth ? ["Math"] : { detail: "Unauthorized" }),
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

  await expect(page.getByRole("button", { name: /New Chat/i })).toBeVisible();
  await expect(page.locator(".workspace-context-bar select").first()).toBeVisible();

  expireSession = true;
  await page.locator(".workspace-context-bar select").first().selectOption({ label: "Class 8" });

  await expect(page.getByText("Your session has expired. Please log in again.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Login" })).toBeVisible();
  await expect(page.getByPlaceholder("Email")).toBeVisible();

  const token = await page.evaluate(() => localStorage.getItem("token"));
  expect(token).toBeNull();
});
