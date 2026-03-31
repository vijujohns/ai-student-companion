import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useSessionLoaders } from "../../../frontend/src/hooks/useSessionLoaders";

function makeResponse(payload, ok = true) {
  return {
    ok,
    json: async () => payload,
  };
}

describe("useSessionLoaders", () => {
  it("loads chat sessions from array response", async () => {
    const apiFetch = vi.fn(async () => makeResponse([{ id: "a" }]));
    const { result } = renderHook(() => useSessionLoaders({ apiFetch }));

    await act(async () => {
      await result.current.loadSessions();
    });

    expect(result.current.sessions).toEqual([{ id: "a" }]);
  });

  it("loads lesson sessions from envelope response", async () => {
    const apiFetch = vi.fn(async () => makeResponse({ sessions: [{ id: "l1" }] }));
    const { result } = renderHook(() => useSessionLoaders({ apiFetch }));

    await act(async () => {
      await result.current.loadLessonSessions();
    });

    expect(result.current.lessonSessions).toEqual([{ id: "l1" }]);
  });

  it("loads quiz and flashcard sessions independently", async () => {
    const apiFetch = vi
      .fn()
      .mockResolvedValueOnce(makeResponse({ sessions: [{ id: "q1" }] }))
      .mockResolvedValueOnce(makeResponse([{ id: "f1" }]));

    const { result } = renderHook(() => useSessionLoaders({ apiFetch }));

    await act(async () => {
      await result.current.loadQuizSessions();
      await result.current.loadFlashcardSessions();
    });

    expect(result.current.quizSessions).toEqual([{ id: "q1" }]);
    expect(result.current.flashcardSessions).toEqual([{ id: "f1" }]);
  });
});
