import { expect, test } from "@playwright/test";

test("quiz generation and submission flow works", async ({ page }) => {
  let generateCalled = false;
  let submitCalled = false;
  let authenticated = false;
  const corsHeaders = {
    "access-control-allow-origin": "http://127.0.0.1:4174",
    "access-control-allow-credentials": "true",
    "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
    "access-control-allow-headers": "*",
  };

  const fulfillJson = async (route, body, status = 200) => {
    await route.fulfill({
      status,
      headers: {
        ...corsHeaders,
        "content-type": "application/json",
      },
      body: JSON.stringify(body),
    });
  };

  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;
    const method = request.method();

    if (method === "OPTIONS") {
      await route.fulfill({ status: 204, headers: corsHeaders });
      return;
    }

    if (pathname === "/login" && method === "POST") {
      authenticated = true;
      await fulfillJson(route, { access_token: "fake-jwt-token", token_type: "bearer", role: "student" });
      return;
    }

    if (pathname === "/auth/session" && method === "GET") {
      await fulfillJson(
        route,
        authenticated
          ? { authenticated: true, username: "student", role: "student" }
          : { authenticated: false },
        authenticated ? 200 : 401
      );
      return;
    }

    if (pathname === "/sessions") {
      await fulfillJson(route, []);
      return;
    }

    if (pathname === "/classes") {
      await fulfillJson(route, ["Class 8"]);
      return;
    }

    if (pathname === "/subjects") {
      await fulfillJson(route, ["English-1"]);
      return;
    }

    if (pathname === "/folders") {
      await fulfillJson(route, ["Text Books"]);
      return;
    }

    if (pathname === "/contents") {
      await fulfillJson(route, [{ title: "Chapter 1", content_id: "kb:Y2xhc3MtOC9lbmdsaXNoLTEvdGV4dC1ib29rcy9DaGFwdGVyIDEucGRm" }]);
      return;
    }

    if (pathname === "/pdf") {
      await route.fulfill({
        status: 200,
        headers: {
          ...corsHeaders,
          "content-type": "application/pdf",
        },
        body: "%PDF-1.4 fake",
      });
      return;
    }

    if (pathname.startsWith("/quiz/sessions")) {
      await fulfillJson(route, []);
      return;
    }

    if (pathname.startsWith("/quiz/latest")) {
      if (generateCalled) {
        await fulfillJson(route, {
          quiz_id: "quiz-1",
          quiz: [{ id: "q1", question: "2 + 2 = ?", options: ["3", "4"] }],
        });
      } else {
        await fulfillJson(route, { error: "No quiz" });
      }
      return;
    }

    if (pathname.startsWith("/quiz/generate") && method === "POST") {
      generateCalled = true;
      await fulfillJson(route, {
        quiz_id: "quiz-1",
        quiz: [
          { id: "q1", question: "2 + 2 = ?", options: ["3", "4"] },
        ],
      });
      return;
    }

    if (pathname.startsWith("/quiz/quiz-1/submit") && method === "POST") {
      submitCalled = true;
      await fulfillJson(route, {
        q1: { is_correct: true, correct_answer: "4" },
      });
      return;
    }

    await fulfillJson(route, {});
  });

  await page.goto("/");
  await page.getByPlaceholder("Email").fill("student@example.com");
  await page.getByPlaceholder("Password").fill("student123");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("button", { name: /New Chat/i }).first()).toBeVisible();

  const selectors = page.locator(".workspace-context-bar select");
  await expect(selectors.first()).toBeVisible();
  await selectors.nth(0).selectOption({ label: "Class 8" });
  await selectors.nth(1).selectOption({ label: "English-1" });
  await selectors.nth(2).selectOption({ label: "Text Books" });
  await expect(selectors.nth(3).locator("option", { hasText: "Chapter 1" })).toHaveCount(1);
  await selectors.nth(3).selectOption({ label: "Chapter 1" });

  await page.getByRole("button", { name: "Quiz" }).click();
  const quizPanel = page.locator(".quiz-panel");
  await quizPanel.getByRole("button", { name: "New Quiz" }).click();
  await expect.poll(() => generateCalled).toBeTruthy();

  await expect(quizPanel.getByText("Session Quiz: quiz-1")).toBeVisible();

  // Use script-level click to avoid pointer interception from viewer splitter overlays.
  await page.evaluate(() => {
    const radio = document.querySelector('input[type="radio"][name="q1"][value="4"]');
    if (!radio) throw new Error("Quiz answer radio not found");
    radio.click();
  });

  await page.evaluate(() => {
    const submitButtons = Array.from(document.querySelectorAll("button"));
    const submit = submitButtons.find((btn) => btn.textContent?.includes("Submit Answers"));
    if (!submit) throw new Error("Submit Answers button not found");
    submit.click();
  });

  await expect.poll(() => submitCalled).toBeTruthy();
  await expect(quizPanel.getByText("Correct")).toBeVisible();
});
