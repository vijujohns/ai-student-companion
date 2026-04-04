import { expect, test } from "@playwright/test";

test("lesson plan generation flow works", async ({ page }) => {
  let authenticated = false;

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

    if (pathname === "/sessions") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      return;
    }

    if (pathname === "/classes") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(["Class 8"]) });
      return;
    }

    if (pathname === "/subjects") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(["English-1"]) });
      return;
    }

    if (pathname === "/folders") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(["Text Books"]) });
      return;
    }

    if (pathname === "/contents") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{ title: "Chapter 1", content_id: "kb:Y2xhc3MtOC9lbmdsaXNoLTEvdGV4dC1ib29rcy9DaGFwdGVyIDEucGRm" }]),
      });
      return;
    }

    if (pathname === "/pdf") {
      await route.fulfill({
        status: 200,
        contentType: "application/pdf",
        body: "%PDF-1.4 fake",
      });
      return;
    }

    if (pathname.startsWith("/lesson-plan/sessions")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{ id: "s1", title: "Lesson - Chapter 1" }]),
      });
      return;
    }

    if (pathname.startsWith("/lesson-plan/create")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          chapter: "Chapter 1",
          steps: [{ step_id: 1, title: "Introduction", content: "Start with key ideas." }],
        }),
      });
      return;
    }

    if (pathname.startsWith("/lesson-plan") && !pathname.includes("/next")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          chapter: "Chapter 1",
          steps: [{ step_id: 1, title: "Introduction", content: "Start with key ideas." }],
        }),
      });
      return;
    }

    if (pathname.startsWith("/lesson-plan/next")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: 1, title: "Introduction" }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.goto("/");
  await page.getByPlaceholder("Email").fill("student@example.com");
  await page.getByPlaceholder("Password").fill("student123");
  await page.getByRole("button", { name: "Continue" }).click();

  const selectors = page.locator(".workspace-context-bar select");
  await selectors.nth(0).selectOption({ label: "Class 8" });
  await selectors.nth(1).selectOption({ label: "English-1" });
  await selectors.nth(2).selectOption({ label: "Text Books" });
  await expect(selectors.nth(3).locator("option", { hasText: "Chapter 1" })).toHaveCount(1);
  await selectors.nth(3).selectOption({ label: "Chapter 1" });

  await page.getByRole("button", { name: "Lesson" }).click();
  await page.getByRole("button", { name: "New Lesson Plan" }).click();

  await expect(page.getByRole("button", { name: "1. Introduction" })).toBeVisible();
  await expect(page.getByText("Lesson - Chapter 1").first()).toBeVisible();
});
