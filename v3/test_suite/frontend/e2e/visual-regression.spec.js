import { expect, test } from "@playwright/test";

async function mockAppApi(page) {
  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

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

    if (method === "OPTIONS") {
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

    if (path === "/login" && method === "POST") {
      await json({ access_token: "visual-token", token_type: "bearer", role: "student" });
      return;
    }

    if (path === "/sessions") {
      await json([
        { id: "s1", title: "Intro Session" },
        { id: "s2", title: "Revision Session" },
      ]);
      return;
    }

    if (path === "/history") {
      await json([
        {
          question: "What is photosynthesis?",
          answer: "Photosynthesis is the process by which plants convert light energy into chemical energy.",
        },
      ]);
      return;
    }

    if (path === "/classes") {
      await json(["Class 8"]);
      return;
    }

    if (path === "/subjects") {
      await json(["English-1"]);
      return;
    }

    if (path === "/folders") {
      await json(["Text Books"]);
      return;
    }

    if (path === "/contents") {
      await json([{ title: "Chapter 1", content_id: "kb:Y2xhc3MtOC9lbmdsaXNoLTEvdGV4dC1ib29rcy9DaGFwdGVyIDEucGRm" }]);
      return;
    }

    if (path === "/pdf") {
      await route.fulfill({
        status: 200,
        headers: {
          "content-type": "application/pdf",
          "access-control-allow-origin": "http://127.0.0.1:4174",
          "access-control-allow-credentials": "true",
        },
        body: "%PDF-1.4 fake",
      });
      return;
    }

    if (path.startsWith("/lesson-plan/sessions")) {
      await json([{ id: "l1", title: "Lesson - Chapter 1" }]);
      return;
    }

    if (path.startsWith("/lesson-plan/create") || (path.startsWith("/lesson-plan") && !path.includes("/next"))) {
      await json({
        chapter: "Chapter 1",
        steps: [
          { step_id: 1, title: "Introduction", content: "Start with context and examples." },
          { step_id: 2, title: "Practice", content: "Solve 5 quick questions." },
        ],
      });
      return;
    }

    if (path.startsWith("/lesson-plan/next")) {
      await json({ id: 1, title: "Introduction" });
      return;
    }

    if (path.startsWith("/quiz/sessions")) {
      await json([{ id: "q1", title: "Quiz - Chapter 1" }]);
      return;
    }

    if (path.startsWith("/quiz/latest") || path.startsWith("/quiz/generate")) {
      await json({
        quiz_id: "quiz-1",
        quiz: [
          { id: "q1", question: "2 + 2 = ?", options: ["3", "4"] },
          { id: "q2", question: "Capital of France?", options: ["Paris", "Rome"] },
        ],
      });
      return;
    }

    if (path.startsWith("/quiz/quiz-1/submit")) {
      await json({
        q1: { is_correct: true, correct_answer: "4" },
        q2: { is_correct: true, correct_answer: "Paris" },
      });
      return;
    }

    await json({});
  });
}

async function freezeMotion(page) {
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
        caret-color: transparent !important;
      }
    `,
  });
}

async function mockWebSocket(page) {
  await page.addInitScript(() => {
    const NativeWebSocket = window.WebSocket;

    class StableWebSocket {
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
        this.readyState = StableWebSocket.CONNECTING;
        this.onopen = null;
        this.onmessage = null;
        this.onerror = null;
        this.onclose = null;
        this._listeners = { open: [], message: [], error: [], close: [] };

        setTimeout(() => {
          this.readyState = StableWebSocket.OPEN;
          const evt = { type: "open" };
          if (this.onopen) this.onopen(evt);
          for (const handler of this._listeners.open) handler(evt);
        }, 5);
      }

      addEventListener(type, handler) {
        if (!this._listeners[type]) this._listeners[type] = [];
        this._listeners[type].push(handler);
      }

      send() {}

      close() {
        this.readyState = StableWebSocket.CLOSED;
        const evt = { code: 1000 };
        if (this.onclose) this.onclose(evt);
        for (const handler of this._listeners.close) handler(evt);
      }
    }

    window.WebSocket = StableWebSocket;
  });
}

test.describe("visual ui regression", () => {
  test("login screen visual baseline", async ({ page }) => {
    await mockAppApi(page);
    await mockWebSocket(page);
    await page.goto("/");
    await freezeMotion(page);

    await expect(page).toHaveScreenshot("visual-login.png", {
      fullPage: true,
      maxDiffPixelRatio: 0.01,
    });
  });

  test("chat workspace visual baseline", async ({ page }) => {
    await mockAppApi(page);
    await mockWebSocket(page);
    await page.goto("/");
    await freezeMotion(page);

    await page.getByPlaceholder("Email").fill("student@example.com");
    await page.getByPlaceholder("Password").fill("student123");
    await page.getByRole("button", { name: "Continue" }).click();

    await expect(page.getByRole("button", { name: /New Chat/i }).first()).toBeVisible();

    const contextDialog = page.getByRole("dialog", { name: /Choose learning context/i });
    await expect(contextDialog).toBeVisible();
    await contextDialog.getByLabel("Select class").selectOption({ label: "Class 8" });
    await contextDialog.getByLabel("Select subject").selectOption({ label: "English-1" });
    await contextDialog.getByLabel("Select folder").selectOption({ label: "Text Books" });
    await contextDialog.getByLabel("Select file").selectOption({ label: "Chapter 1" });
    await contextDialog.getByRole("button", { name: /Continue with this context/i }).click();

    await expect(page).toHaveScreenshot("visual-chat-workspace.png", {
      fullPage: true,
      maxDiffPixelRatio: 0.01,
    });
  });

  test("lesson panel visual baseline", async ({ page }) => {
    await mockAppApi(page);
    await mockWebSocket(page);
    await page.goto("/");
    await freezeMotion(page);

    await page.getByPlaceholder("Email").fill("student@example.com");
    await page.getByPlaceholder("Password").fill("student123");
    await page.getByRole("button", { name: "Continue" }).click();

    await expect(page.getByRole("button", { name: /New Chat/i }).first()).toBeVisible();
    const contextDialog = page.getByRole("dialog", { name: /Choose learning context/i });
    await expect(contextDialog).toBeVisible();
    await contextDialog.getByLabel("Select class").selectOption({ label: "Class 8" });
    await contextDialog.getByLabel("Select subject").selectOption({ label: "English-1" });
    await contextDialog.getByLabel("Select folder").selectOption({ label: "Text Books" });
    await contextDialog.getByLabel("Select file").selectOption({ label: "Chapter 1" });
    await contextDialog.getByRole("button", { name: /Continue with this context/i }).click();

    await page.getByRole("button", { name: "Lesson" }).click();
    await page.getByRole("button", { name: "New Lesson Plan" }).click();

    await expect(page).toHaveScreenshot("visual-lesson-panel.png", {
      fullPage: true,
      maxDiffPixelRatio: 0.01,
    });
  });

  test("quiz panel visual baseline", async ({ page }) => {
    await mockAppApi(page);
    await mockWebSocket(page);
    await page.goto("/");
    await freezeMotion(page);

    await page.getByPlaceholder("Email").fill("student@example.com");
    await page.getByPlaceholder("Password").fill("student123");
    await page.getByRole("button", { name: "Continue" }).click();

    await expect(page.getByRole("button", { name: /New Chat/i }).first()).toBeVisible();
    const contextDialog = page.getByRole("dialog", { name: /Choose learning context/i });
    await expect(contextDialog).toBeVisible();
    await contextDialog.getByLabel("Select class").selectOption({ label: "Class 8" });
    await contextDialog.getByLabel("Select subject").selectOption({ label: "English-1" });
    await contextDialog.getByLabel("Select folder").selectOption({ label: "Text Books" });
    await contextDialog.getByLabel("Select file").selectOption({ label: "Chapter 1" });
    await contextDialog.getByRole("button", { name: /Continue with this context/i }).click();

    await page.getByRole("button", { name: "Quiz" }).click();
    await page.getByRole("button", { name: "New Quiz" }).click();

    await expect(page).toHaveScreenshot("visual-quiz-panel.png", {
      fullPage: true,
      maxDiffPixelRatio: 0.01,
    });
  });

  test("mobile login visual baseline", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockAppApi(page);
    await mockWebSocket(page);
    await page.goto("/");
    await freezeMotion(page);

    await expect(page).toHaveScreenshot("visual-mobile-login.png", {
      fullPage: true,
      maxDiffPixelRatio: 0.01,
    });
  });
});
