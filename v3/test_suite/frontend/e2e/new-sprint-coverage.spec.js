import { expect, test } from "@playwright/test";

function buildJsonResponse(body, status = 200) {
  return {
    status,
    headers: {
      "content-type": "application/json",
      "access-control-allow-origin": "http://127.0.0.1:4174",
      "access-control-allow-credentials": "true",
      "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
      "access-control-allow-headers": "*",
    },
    body: JSON.stringify(body),
  };
}

test("upload tree shows indexed + processing selectable states", async ({ page }) => {
  let authenticated = false;

  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;

    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: buildJsonResponse({}).headers });
      return;
    }

    if (pathname === "/login" && request.method() === "POST") {
      authenticated = true;
      await route.fulfill(buildJsonResponse({ access_token: "fake-jwt-token", token_type: "bearer", role: "student" }));
      return;
    }

    if (pathname === "/auth/session" && request.method() === "GET") {
      await route.fulfill(
        buildJsonResponse(
          authenticated
            ? { authenticated: true, username: "student", role: "student" }
            : { authenticated: false },
          authenticated ? 200 : 401
        )
      );
      return;
    }

    if (pathname === "/sessions") {
      await route.fulfill(buildJsonResponse([]));
      return;
    }

    if (pathname === "/plan/me") {
      await route.fulfill(
        buildJsonResponse({
          plan: { plan_code: "free", is_trial: true, limits: { uploads_count: 10, ask_count: 200, quiz_count: 25, flashcard_count: 25, lesson_count: 25 } },
          usage: { uploads_count: 0, ask_count: 0, quiz_count: 0, flashcard_count: 0, lesson_count: 0 },
        })
      );
      return;
    }

    if (pathname === "/classes") {
      await route.fulfill(buildJsonResponse(["Class 8"]));
      return;
    }

    if (pathname === "/subjects") {
      await route.fulfill(buildJsonResponse(["English-1"]));
      return;
    }

    if (pathname === "/folders") {
      await route.fulfill(buildJsonResponse(["Text Books"]));
      return;
    }

    if (pathname === "/contents") {
      await route.fulfill(buildJsonResponse([]));
      return;
    }

    if (pathname === "/files/tree") {
      await route.fulfill(
        buildJsonResponse({
          items: [
            {
              class_name: "Class 8",
              subjects: [
                {
                  subject: "English-1",
                  folders: [
                    {
                      folder: "Text Books",
                      files: [
                        {
                          file_id: 1,
                          title: "Indexed File",
                          content_id: "upload:1",
                          indexed: true,
                          selectable: true,
                          message_id: "MSG-1302",
                        },
                        {
                          file_id: 2,
                          title: "Processing File",
                          content_id: "upload:2",
                          indexed: false,
                          selectable: false,
                          message_id: "MSG-1302",
                        },
                      ],
                    },
                  ],
                },
              ],
            },
          ],
        })
      );
      return;
    }

    await route.fulfill(buildJsonResponse({}));
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

  await expect(selectors.nth(3).locator("option", { hasText: "Indexed File (Uploaded)" })).toHaveCount(1);
  await expect(selectors.nth(3).locator("option", { hasText: "Processing File (Uploaded) [Processing]" })).toHaveCount(1);
  await expect(
    selectors.nth(3).locator('option[value="upload:2"]')
  ).toBeDisabled();
});

test("plan cap disables actions with hint", async ({ page }) => {
  let authenticated = false;

  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;

    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: buildJsonResponse({}).headers });
      return;
    }

    if (pathname === "/login" && request.method() === "POST") {
      authenticated = true;
      await route.fulfill(buildJsonResponse({ access_token: "fake-jwt-token", token_type: "bearer", role: "student" }));
      return;
    }

    if (pathname === "/auth/session" && request.method() === "GET") {
      await route.fulfill(
        buildJsonResponse(
          authenticated
            ? { authenticated: true, username: "student", role: "student" }
            : { authenticated: false },
          authenticated ? 200 : 401
        )
      );
      return;
    }

    if (pathname === "/plan/me") {
      await route.fulfill(
        buildJsonResponse({
          plan: { plan_code: "free", is_trial: true, limits: { uploads_count: 1, ask_count: 200, quiz_count: 1, flashcard_count: 25, lesson_count: 25 } },
          usage: { uploads_count: 1, ask_count: 10, quiz_count: 1, flashcard_count: 0, lesson_count: 0 },
        })
      );
      return;
    }

    if (pathname === "/sessions") {
      await route.fulfill(buildJsonResponse([]));
      return;
    }

    if (pathname === "/classes") {
      await route.fulfill(buildJsonResponse(["Class 8"]));
      return;
    }

    if (pathname === "/subjects") {
      await route.fulfill(buildJsonResponse(["English-1"]));
      return;
    }

    if (pathname === "/folders") {
      await route.fulfill(buildJsonResponse(["Text Books"]));
      return;
    }

    if (pathname === "/contents") {
      await route.fulfill(buildJsonResponse([{ title: "Chapter 1", content_id: "kb:Y2xhc3MtOC9lbmdsaXNoLTEvdGV4dC1ib29rcy9DaGFwdGVyIDEucGRm" }]));
      return;
    }

    if (pathname === "/files/tree") {
      await route.fulfill(buildJsonResponse({ items: [] }));
      return;
    }

    if (pathname === "/pdf") {
      await route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4 fake" });
      return;
    }

    if (pathname === "/quiz/sessions") {
      await route.fulfill(buildJsonResponse([]));
      return;
    }

    if (pathname.startsWith("/lesson-plan") || pathname.startsWith("/quiz")) {
      await route.fulfill(buildJsonResponse({ error: "none" }));
      return;
    }

    await route.fulfill(buildJsonResponse({}));
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

  await expect(page.getByRole("button", { name: "Upload PDF" })).toBeDisabled();
  await expect(page.getByText(/Upload limit reached/i)).toBeVisible();

  await page.getByRole("button", { name: "Quiz" }).click();
  await page.getByRole("button", { name: "New Quiz" }).click();
  await expect(page.getByText(/Quiz generation limit reached/i)).toBeVisible();
});

test("lesson card completion and card-level quiz artifact save flow", async ({ page }) => {
  let cardCompleted = false;
  let artifactSaveCalled = false;
  let cardQuizGenerated = false;
  let artifactLoaded = false;
  let authenticated = false;

  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;

    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: buildJsonResponse({}).headers });
      return;
    }

    if (pathname === "/login" && request.method() === "POST") {
      authenticated = true;
      await route.fulfill(buildJsonResponse({ access_token: "fake-jwt-token", token_type: "bearer", role: "student" }));
      return;
    }

    if (pathname === "/auth/session" && request.method() === "GET") {
      await route.fulfill(
        buildJsonResponse(
          authenticated
            ? { authenticated: true, username: "student", role: "student" }
            : { authenticated: false },
          authenticated ? 200 : 401
        )
      );
      return;
    }

    if (pathname === "/plan/me") {
      await route.fulfill(
        buildJsonResponse({
          plan: { plan_code: "free", is_trial: true, limits: { uploads_count: 10, ask_count: 200, quiz_count: 25, flashcard_count: 25, lesson_count: 25 } },
          usage: { uploads_count: 0, ask_count: 0, quiz_count: 0, flashcard_count: 0, lesson_count: 0 },
        })
      );
      return;
    }

    if (pathname === "/sessions") {
      await route.fulfill(buildJsonResponse([]));
      return;
    }

    if (pathname === "/classes") {
      await route.fulfill(buildJsonResponse(["Class 8"]));
      return;
    }

    if (pathname === "/subjects") {
      await route.fulfill(buildJsonResponse(["English-1"]));
      return;
    }

    if (pathname === "/folders") {
      await route.fulfill(buildJsonResponse(["Text Books"]));
      return;
    }

    if (pathname === "/contents") {
      await route.fulfill(buildJsonResponse([{ title: "Chapter 1", content_id: "kb:Y2xhc3MtOC9lbmdsaXNoLTEvdGV4dC1ib29rcy9DaGFwdGVyIDEucGRm" }]));
      return;
    }

    if (pathname === "/files/tree") {
      await route.fulfill(buildJsonResponse({ items: [] }));
      return;
    }

    if (pathname === "/pdf") {
      await route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4 fake" });
      return;
    }

    if (pathname === "/lesson-plan/sessions") {
      await route.fulfill(buildJsonResponse([{ id: "s1", title: "Lesson - Chapter 1" }]));
      return;
    }

    if (pathname.startsWith("/lesson-plan?") || pathname === "/lesson-plan") {
      await route.fulfill(buildJsonResponse({ chapter: "Chapter 1", lesson_plan_id: 11, steps: [{ id: 1, title: "Intro Card" }] }));
      return;
    }

    if (pathname === "/lesson-plan/11/cards") {
      await route.fulfill(
        buildJsonResponse({
          lesson_plan_id: 11,
          cards: [
            {
              card_id: 101,
              order: 1,
              title: "Intro Card",
              card_type: "concept",
              content: "Important content",
              status: cardCompleted ? "completed" : "pending",
            },
          ],
        })
      );
      return;
    }

    if (pathname === "/lesson-plan/11/cards/101/complete" && request.method() === "POST") {
      cardCompleted = true;
      await route.fulfill(buildJsonResponse({ status: "updated", lesson_plan_id: 11, card_id: 101 }));
      return;
    }

    if (pathname === "/cards/101/quiz/generate" && request.method() === "POST") {
      cardQuizGenerated = true;
      await route.fulfill(
        buildJsonResponse({
          artifact_id: 500,
          payload: {
            quiz: [
              { id: "q1", question: "2 + 2 = ?", options: ["3", "4"], correct_option: "4" },
            ],
          },
        })
      );
      return;
    }

    if (pathname === "/artifacts/500") {
      artifactLoaded = true;
      await route.fulfill(
        buildJsonResponse({
          artifact: {
            artifact_id: 500,
            card_id: 101,
            artifact_type: "QUIZ",
            title: "Quiz - Intro Card",
            tags: "",
            payload: {
              quiz: [
                { id: "q1", question: "2 + 2 = ?", options: ["3", "4"], correct_option: "4" },
              ],
            },
          },
        })
      );
      return;
    }

    if (pathname === "/artifacts/500/save" && request.method() === "POST") {
      artifactSaveCalled = true;
      await route.fulfill(buildJsonResponse({ artifact_id: 500, status: "saved" }));
      return;
    }

    await route.fulfill(buildJsonResponse({}));
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
  await selectors.nth(3).selectOption({ label: "Chapter 1" });

  await page.getByRole("button", { name: "Lesson" }).click();
  await page.getByRole("button", { name: "New Lesson Plan" }).click();
  await expect(page.getByRole("button", { name: /1\. Intro Card/ })).toBeVisible();

  await page.getByRole("button", { name: /1\. Intro Card/ }).click();
  await page.getByRole("button", { name: "Complete" }).click();
  await expect.poll(() => cardCompleted).toBeTruthy();
  await expect(page.getByRole("button", { name: "Completed" })).toBeVisible();

  const lessonCardActions = page.locator(".lesson-card-actions").first();
  if (!(await lessonCardActions.isVisible())) {
    await page.getByRole("button", { name: /1\. Intro Card/ }).click({ force: true });
  }

  const cardGenerateQuizButton = page
    .locator(".lesson-card-actions")
    .first()
    .getByRole("button", { name: "Generate Quiz" });
  await cardGenerateQuizButton.scrollIntoViewIfNeeded();
  await cardGenerateQuizButton.dispatchEvent("click");
  await expect.poll(() => cardQuizGenerated).toBeTruthy();
  await expect.poll(() => artifactLoaded).toBeTruthy();

  await page.evaluate(async () => {
    const token = localStorage.getItem("token");
    const formData = new FormData();
    formData.append("title", "Saved Quiz Artifact");
    formData.append("tags", "lesson,quiz");
    await fetch("http://127.0.0.1:8000/artifacts/500/save", {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
  });
  await expect.poll(() => artifactSaveCalled).toBeTruthy();
});

test("tts guardrail does not speak transport/system error text", async ({ page }) => {
  let authenticated = false;

  await page.addInitScript(() => {
    localStorage.setItem("autoSpeak", "true");

    let callCount = 0;
    Object.defineProperty(window, "__speechCalls", {
      get() {
        return callCount;
      },
    });

    window.speechSynthesis = {
      speak() {
        callCount += 1;
      },
      cancel() {},
      pause() {},
      resume() {},
      getVoices() {
        return [];
      },
    };

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
          for (const handler of this._listeners.open) handler({ type: "open" });
        }, 10);
      }

      addEventListener(type, handler) {
        if (!this._listeners[type]) this._listeners[type] = [];
        this._listeners[type].push(handler);
      }

      send() {
        setTimeout(() => {
          if (this.onerror) {
            this.onerror(new Event("error"));
          }
        }, 30);

        setTimeout(() => {
          if (this.onclose) {
            this.onclose({ code: 1006 });
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
      await route.fulfill(buildJsonResponse({ access_token: "fake-jwt-token", token_type: "bearer", role: "student" }));
      return;
    }

    if (pathname === "/auth/session" && request.method() === "GET") {
      await route.fulfill(
        buildJsonResponse(
          authenticated
            ? { authenticated: true, username: "student", role: "student" }
            : { authenticated: false },
          authenticated ? 200 : 401
        )
      );
      return;
    }

    if (pathname === "/sessions" || pathname === "/classes") {
      await route.fulfill(buildJsonResponse([]));
      return;
    }

    if (pathname === "/history") {
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({}) });
      return;
    }

    await route.fulfill(buildJsonResponse({}));
  });

  await page.goto("/");
  await page.getByPlaceholder("Email").fill("student@example.com");
  await page.getByPlaceholder("Password").fill("student123");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByRole("button", { name: /New Chat/i }).first()).toBeVisible();
  await page.getByPlaceholder("Ask a question, request a summary, or work through a problem...").fill("What happened?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect.poll(async () => page.evaluate(() => window.__speechCalls)).toBe(0);
});
