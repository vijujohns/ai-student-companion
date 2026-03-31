import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const deleteScopedSessionMock = vi.fn();
const renameScopedSessionMock = vi.fn();

vi.mock("../../../frontend/src/utils/sessionCrud", () => ({
  deleteScopedSession: (...args) => deleteScopedSessionMock(...args),
  renameScopedSession: (...args) => renameScopedSessionMock(...args),
}));

import { useScopedSessionActions } from "../../../frontend/src/hooks/useScopedSessionActions";

describe("useScopedSessionActions", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    deleteScopedSessionMock.mockReset();
    renameScopedSessionMock.mockReset();
    localStorage.clear();
  });

  function setup() {
    return renderHook(() =>
      useScopedSessionActions({
        setActiveTab: vi.fn(),
        setLessonResultReady: vi.fn(),
        setQuizResultReady: vi.fn(),
        setFlashcardResultReady: vi.fn(),
        setLessonSessions: vi.fn(),
        setQuizSessions: vi.fn(),
        setFlashcardSessions: vi.fn(),
      })
    );
  }

  it("persistLessonSession seeds lesson and missing quiz/flashcard ids", () => {
    const { result } = setup();

    act(() => {
      result.current.persistLessonSession("L-1");
    });

    expect(result.current.lessonSessionId).toBe("L-1");
    expect(result.current.quizSessionId).toBe("L-1");
    expect(result.current.flashcardSessionId).toBe("L-1");
    expect(localStorage.getItem("lesson_session_id")).toBe("L-1");
    expect(localStorage.getItem("quiz_session_id")).toBe("L-1");
    expect(localStorage.getItem("flashcard_session_id")).toBe("L-1");
  });

  it("handleNewQuizSession sets active tab and clears ready state", () => {
    const setActiveTab = vi.fn();
    const setQuizResultReady = vi.fn();

    const { result } = renderHook(() =>
      useScopedSessionActions({
        setActiveTab,
        setLessonResultReady: vi.fn(),
        setQuizResultReady,
        setFlashcardResultReady: vi.fn(),
        setLessonSessions: vi.fn(),
        setQuizSessions: vi.fn(),
        setFlashcardSessions: vi.fn(),
      })
    );

    act(() => {
      result.current.handleNewQuizSession();
    });

    expect(setActiveTab).toHaveBeenCalledWith("quiz");
    expect(setQuizResultReady).toHaveBeenCalledWith(false);
    expect(localStorage.getItem("quiz_session_id")).toBeTruthy();
  });

  it("deleteQuizSession clears active id on successful deletion", async () => {
    deleteScopedSessionMock.mockResolvedValue(true);
    const setQuizResultReady = vi.fn();

    localStorage.setItem("quiz_session_id", "Q-1");
    const { result } = renderHook(() =>
      useScopedSessionActions({
        setActiveTab: vi.fn(),
        setLessonResultReady: vi.fn(),
        setQuizResultReady,
        setFlashcardResultReady: vi.fn(),
        setLessonSessions: vi.fn(),
        setQuizSessions: vi.fn(),
        setFlashcardSessions: vi.fn(),
      })
    );

    await act(async () => {
      await result.current.deleteQuizSession({ id: "Q-1" });
    });

    expect(result.current.quizSessionId).toBe("");
    expect(localStorage.getItem("quiz_session_id")).toBeNull();
    expect(setQuizResultReady).toHaveBeenCalledWith(false);
  });
});
