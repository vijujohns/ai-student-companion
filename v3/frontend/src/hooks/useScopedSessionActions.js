import { useCallback, useState } from "react";
import { apiFetch as defaultApiFetch, parseApiError as defaultParseApiError } from "../services/api";
import { deleteScopedSession, renameScopedSession } from "../utils/sessionCrud";

export function useScopedSessionActions({
  setActiveTab,
  setLessonResultReady,
  setQuizResultReady,
  setFlashcardResultReady,
  setLessonSessions,
  setQuizSessions,
  setFlashcardSessions,
  apiFetch = defaultApiFetch,
  parseApiError = defaultParseApiError,
} = {}) {
  const [lessonSessionId, setLessonSessionId] = useState(localStorage.getItem("lesson_session_id") || "");
  const [quizSessionId, setQuizSessionId] = useState(
    localStorage.getItem("quiz_session_id") || localStorage.getItem("lesson_session_id") || ""
  );
  const [flashcardSessionId, setFlashcardSessionId] = useState(
    localStorage.getItem("flashcard_session_id") || localStorage.getItem("lesson_session_id") || ""
  );

  const persistLessonSession = useCallback((sid) => {
    if (!sid) return;
    setLessonSessionId(sid);
    localStorage.setItem("lesson_session_id", sid);
    if (!localStorage.getItem("quiz_session_id")) {
      setQuizSessionId(sid);
      localStorage.setItem("quiz_session_id", sid);
    }
    if (!localStorage.getItem("flashcard_session_id")) {
      setFlashcardSessionId(sid);
      localStorage.setItem("flashcard_session_id", sid);
    }
  }, []);

  const persistQuizSession = useCallback((sid) => {
    if (!sid) return;
    setQuizSessionId(sid);
    localStorage.setItem("quiz_session_id", sid);
  }, []);

  const persistFlashcardSession = useCallback((sid) => {
    if (!sid) return;
    setFlashcardSessionId(sid);
    localStorage.setItem("flashcard_session_id", sid);
  }, []);

  const handleNewLessonSession = useCallback(() => {
    const sid = Date.now().toString();
    persistLessonSession(sid);
    setActiveTab("lesson");
    setLessonResultReady(false);
  }, [persistLessonSession, setActiveTab, setLessonResultReady]);

  const handleNewQuizSession = useCallback(() => {
    const sid = Date.now().toString();
    persistQuizSession(sid);
    setActiveTab("quiz");
    setQuizResultReady(false);
  }, [persistQuizSession, setActiveTab, setQuizResultReady]);

  const handleNewFlashcardSession = useCallback(() => {
    const sid = Date.now().toString();
    persistFlashcardSession(sid);
    setActiveTab("flashcards");
    setFlashcardResultReady(false);
  }, [persistFlashcardSession, setActiveTab, setFlashcardResultReady]);

  const renameLessonSession = useCallback(async (lessonSession) => {
    const nextTitle = prompt("Rename lesson plan:", lessonSession.title || "Lesson Session");
    if (!nextTitle) return;

    await renameScopedSession({
      session: lessonSession,
      endpointPrefix: "/lesson-plan/sessions",
      nextTitle,
      setSessions: setLessonSessions,
      apiFetch,
      parseApiError,
      failureLabel: "lesson session",
    });
  }, [apiFetch, parseApiError, setLessonSessions]);

  const deleteLessonSession = useCallback(async (lessonSession) => {
    const deleted = await deleteScopedSession({
      session: lessonSession,
      endpointPrefix: "/lesson-plan/sessions",
      setSessions: setLessonSessions,
      apiFetch,
      parseApiError,
      failureLabel: "lesson session",
    });
    if (!deleted) return;

    if (lessonSessionId === lessonSession.id) {
      setLessonSessionId("");
      localStorage.removeItem("lesson_session_id");
      setLessonResultReady(false);
    }
  }, [apiFetch, lessonSessionId, parseApiError, setLessonResultReady, setLessonSessions]);

  const renameQuizSession = useCallback(async (quizSession) => {
    const nextTitle = prompt("Rename quiz:", quizSession.title || "Quiz Session");
    if (!nextTitle) return;

    await renameScopedSession({
      session: quizSession,
      endpointPrefix: "/quiz/sessions",
      nextTitle,
      setSessions: setQuizSessions,
      apiFetch,
      parseApiError,
      failureLabel: "quiz session",
    });
  }, [apiFetch, parseApiError, setQuizSessions]);

  const deleteQuizSession = useCallback(async (quizSession) => {
    const deleted = await deleteScopedSession({
      session: quizSession,
      endpointPrefix: "/quiz/sessions",
      setSessions: setQuizSessions,
      apiFetch,
      parseApiError,
      failureLabel: "quiz session",
    });
    if (!deleted) return;

    if (quizSessionId === quizSession.id) {
      setQuizSessionId("");
      localStorage.removeItem("quiz_session_id");
      setQuizResultReady(false);
    }
  }, [apiFetch, parseApiError, quizSessionId, setQuizResultReady, setQuizSessions]);

  const renameFlashcardSession = useCallback(async (flashcardSession) => {
    const nextTitle = prompt("Rename cards session:", flashcardSession.title || "Cards Session");
    if (!nextTitle) return;

    await renameScopedSession({
      session: flashcardSession,
      endpointPrefix: "/flashcards/sessions",
      nextTitle,
      setSessions: setFlashcardSessions,
      apiFetch,
      parseApiError,
      failureLabel: "cards session",
    });
  }, [apiFetch, parseApiError, setFlashcardSessions]);

  const deleteFlashcardSession = useCallback(async (flashcardSession) => {
    const deleted = await deleteScopedSession({
      session: flashcardSession,
      endpointPrefix: "/flashcards/sessions",
      setSessions: setFlashcardSessions,
      apiFetch,
      parseApiError,
      failureLabel: "cards session",
    });
    if (!deleted) return;

    if (flashcardSessionId === flashcardSession.id) {
      setFlashcardSessionId("");
      localStorage.removeItem("flashcard_session_id");
      setFlashcardResultReady(false);
    }
  }, [apiFetch, flashcardSessionId, parseApiError, setFlashcardResultReady, setFlashcardSessions]);

  return {
    lessonSessionId,
    quizSessionId,
    flashcardSessionId,
    persistLessonSession,
    persistQuizSession,
    persistFlashcardSession,
    handleNewLessonSession,
    handleNewQuizSession,
    handleNewFlashcardSession,
    renameLessonSession,
    deleteLessonSession,
    renameQuizSession,
    deleteQuizSession,
    renameFlashcardSession,
    deleteFlashcardSession,
  };
}
