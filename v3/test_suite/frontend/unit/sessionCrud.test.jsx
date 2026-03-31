import { describe, expect, it, vi } from "vitest";
import { deleteScopedSession, renameScopedSession } from "../../../frontend/src/utils/sessionCrud";

describe("sessionCrud helpers", () => {
  it("renames a session on successful API response", async () => {
    let sessions = [
      { id: "1", title: "Old" },
      { id: "2", title: "Keep" },
    ];

    const setSessions = (updater) => {
      sessions = updater(sessions);
    };

    const ok = await renameScopedSession({
      session: { id: "1" },
      endpointPrefix: "/quiz/sessions",
      nextTitle: "New",
      setSessions,
      apiFetch: vi.fn().mockResolvedValue({ ok: true }),
      parseApiError: vi.fn(),
      failureLabel: "quiz session",
    });

    expect(ok).toBe(true);
    expect(sessions).toEqual([
      { id: "1", title: "New" },
      { id: "2", title: "Keep" },
    ]);
  });

  it("does not mutate sessions when rename API fails", async () => {
    let sessions = [{ id: "1", title: "Old" }];

    const setSessions = (updater) => {
      sessions = updater(sessions);
    };

    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const ok = await renameScopedSession({
      session: { id: "1" },
      endpointPrefix: "/quiz/sessions",
      nextTitle: "New",
      setSessions,
      apiFetch: vi.fn().mockResolvedValue({ ok: false }),
      parseApiError: vi.fn().mockResolvedValue("Rename failed"),
      failureLabel: "quiz session",
    });

    expect(ok).toBe(false);
    expect(sessions).toEqual([{ id: "1", title: "Old" }]);
    expect(errorSpy).toHaveBeenCalled();

    errorSpy.mockRestore();
  });

  it("deletes a session on successful API response", async () => {
    let sessions = [
      { id: "1", title: "Remove" },
      { id: "2", title: "Keep" },
    ];

    const setSessions = (updater) => {
      sessions = updater(sessions);
    };

    const ok = await deleteScopedSession({
      session: { id: "1" },
      endpointPrefix: "/flashcards/sessions",
      setSessions,
      apiFetch: vi.fn().mockResolvedValue({ ok: true }),
      parseApiError: vi.fn(),
      failureLabel: "cards session",
    });

    expect(ok).toBe(true);
    expect(sessions).toEqual([{ id: "2", title: "Keep" }]);
  });
});
