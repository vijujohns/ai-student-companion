import { expect, test } from "@playwright/test";

const jsonResponse = async (route, body, status = 200) => {
  await route.fulfill({
    status,
    headers: {
      "content-type": "application/json",
      "access-control-allow-origin": "*",
      "access-control-allow-credentials": "true",
      "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
      "access-control-allow-headers": "*",
    },
    body: JSON.stringify(body),
  });
};

test("login page includes keyboard skip-link and mobile-friendly layout", async ({ page }) => {
  let authenticated = false;

  await page.route(/.*\/auth\/session$/, async (route) => {
    await jsonResponse(route, authenticated ? { authenticated: true, username: "student", role: "student" } : { authenticated: false }, authenticated ? 200 : 401);
  });

  await page.route(/.*\/login$/, async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      authenticated = true;
      await jsonResponse(route, { access_token: "fake-jwt-token", token_type: "bearer", username: "student", role: "student" });
      return;
    }
    await route.continue();
  });

  await page.route(/.*\/classes$/, async (route) => {
    await jsonResponse(route, ["Class 8"]);
  });

  await page.route(/.*\/sessions$/, async (route) => {
    await jsonResponse(route, []);
  });

  await page.setViewportSize({ width: 640, height: 900 });
  await page.goto("/");

  const skipLink = page.getByRole("link", { name: /skip to main content/i });
  await expect(skipLink).toBeVisible();
  expect(await skipLink.getAttribute("href")).toBe("#main-content");

  await page.keyboard.press("Tab");
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");

  const main = page.getByRole("main", { name: /application content/i });
  await expect(main).toBeVisible();

  const loginShell = page.locator(".login-shell");
  await expect(loginShell).toHaveCount(1);
  const gridCols = await loginShell.evaluate((el) => getComputedStyle(el).gridTemplateColumns);
  expect(gridCols.trim().split(/\s+/).length).toBe(1);
});
