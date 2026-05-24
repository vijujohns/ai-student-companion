import { useCallback, useState } from "react";
import { apiFetch as defaultApiFetch } from "../services/api";

function normalizeSessionList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.sessions)) return data.sessions;
  return [];
}

export function useSessionLoaders({ apiFetch = defaultApiFetch } = {}) {
  const [sessions, setSessions] = useState([]);
  const [lessonSessions, setLessonSessions] = useState([]);
  const [quizSessions, setQuizSessions] = useState([]);
  const [flashcardSessions, setFlashcardSessions] = useState([]);
  const [notesSessions, setNotesSessions] = useState([]);

  const loadSessions = useCallback(async () => {
    try {
      const res = await apiFetch("/sessions");
      if (!res.ok) return;
      const data = await res.json();
      setSessions(normalizeSessionList(data));
    } catch (err) {
      console.error("❌ Failed to load sessions:", err);
    }
  }, [apiFetch]);

  const loadLessonSessions = useCallback(async () => {
    try {
      const res = await apiFetch("/lesson-plan/sessions");
      if (!res.ok) return;
      const data = await res.json();
      setLessonSessions(normalizeSessionList(data));
    } catch (err) {
      console.error("❌ Failed to load lesson sessions:", err);
    }
  }, [apiFetch]);

  const loadQuizSessions = useCallback(async () => {
    try {
      const res = await apiFetch("/quiz/sessions");
      if (!res.ok) return;
      const data = await res.json();
      setQuizSessions(normalizeSessionList(data));
    } catch (err) {
      console.error("❌ Failed to load quiz sessions:", err);
    }
  }, [apiFetch]);

  const loadFlashcardSessions = useCallback(async () => {
    try {
      const res = await apiFetch("/flashcards/sessions");
      if (!res.ok) return;
      const data = await res.json();
      setFlashcardSessions(normalizeSessionList(data));
    } catch (err) {
      console.error("❌ Failed to load flashcard sessions:", err);
    }
  }, [apiFetch]);

  const loadNotesSessions = useCallback(async () => {
    try {
      const res = await apiFetch("/notes/sessions");
      if (!res.ok) return;
      const data = await res.json();
      setNotesSessions(normalizeSessionList(data));
    } catch (err) {
      console.error("❌ Failed to load notes sessions:", err);
    }
  }, [apiFetch]);

  return {
    sessions,
    setSessions,
    lessonSessions,
    setLessonSessions,
    quizSessions,
    setQuizSessions,
    flashcardSessions,
    setFlashcardSessions,
    notesSessions,
    setNotesSessions,
    loadSessions,
    loadLessonSessions,
    loadQuizSessions,
    loadFlashcardSessions,
    loadNotesSessions,
  };
}
