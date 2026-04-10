import React, { useCallback, useEffect, useRef, useState } from "react";
import { FiCheckCircle, FiClipboard, FiLayers, FiRefreshCw } from "react-icons/fi";
import { apiFetch, parseApiError } from "../services/api";

function createSessionId() {
  return `${Date.now()}`;
}

const GENERATE_PHASES = [
  "Scanning the selected chapter...",
  "Composing balanced quiz questions...",
  "Checking distractors and answers...",
  "Packing the quiz for review...",
];

export default function QuizPanel({
  sessionId,
  quizSessionId,
  onQuizSessionChange,
  onQuizSessionsChange,
  planSummary = null,
  defaultChapter = "",
  prefillContext = "",
  autoRunToken = "",
  prefilledQuizData = null,
  currentContextLabel = null,
  selectedContentId = null,
  hasLinkedContent = false,
  isContextViewerVisible = false,
  onOpenContext = null,
  onResultReady = null,
}) {
  const [chapter, setChapter] = useState(defaultChapter || "");
  const [quizContext, setQuizContext] = useState("");
  const [quizId, setQuizId] = useState("");
  const [quizSource, setQuizSource] = useState("session");
  const [generationMode, setGenerationMode] = useState("context");
  const [lessonSourceSessions, setLessonSourceSessions] = useState([]);
  const [lessonSourceSessionId, setLessonSourceSessionId] = useState("");
  const [lessonPlanId, setLessonPlanId] = useState(null);
  const [lessonCards, setLessonCards] = useState([]);
  const [selectedCardId, setSelectedCardId] = useState("");
  const [artifactId, setArtifactId] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const pendingGeneratedSessionRef = useRef("");
  const skipNextSessionLoadRef = useRef(false);
  const loadingRef = useRef(false);
  const onResultReadyRef = useRef(onResultReady);

  const quizUsage = Number(planSummary?.usage?.quiz_count || 0);
  const quizLimit = Number(planSummary?.limits?.quiz_count || 0);
  const quizBlocked = quizLimit > 0 ? quizUsage >= quizLimit : false;
  const selectedChapter = (currentContextLabel || defaultChapter || chapter || "").trim();

  const ensureQuizSession = useCallback(() => {
    if (quizSessionId) return quizSessionId;
    const sid = sessionId || createSessionId();
    onQuizSessionChange?.(sid);
    return sid;
  }, [onQuizSessionChange, quizSessionId, sessionId]);

  useEffect(() => {
    loadingRef.current = loading;
  }, [loading]);

  useEffect(() => {
    onResultReadyRef.current = onResultReady;
  }, [onResultReady]);

  const normalizeQuizQuestions = useCallback((items) => {
    if (!Array.isArray(items)) return [];
    return items.map((item, index) => {
      const options = Array.isArray(item.options) ? item.options : ["A", "B", "C", "D"];
      const rawCorrect = item.correct_option || item.correct_answer || item.answer || "A";
      const upper = typeof rawCorrect === "string" ? rawCorrect.trim().toUpperCase() : "";
      const optionIndex = ["A", "B", "C", "D"].indexOf(upper);
      const normalizedCorrect =
        optionIndex >= 0 && optionIndex < options.length ? options[optionIndex] : rawCorrect;

      return {
        id: item.id || `q${index + 1}`,
        question: item.question || `Question ${index + 1}`,
        options,
        correct_option: normalizedCorrect,
        correct_option_label: optionIndex >= 0 ? upper : "",
        correct_answer: normalizedCorrect,
      };
    });
  }, []);

  const resetQuizView = useCallback(() => {
    setQuizId("");
    setArtifactId(null);
    setQuestions([]);
    setAnswers({});
    setResults({});
    setQuizSource("session");
  }, []);

  const loadLessonCardsForSession = useCallback(async (sid) => {
    if (!sid) {
      setLessonPlanId(null);
      setLessonCards([]);
      setSelectedCardId("");
      return;
    }

    try {
      const planRes = await apiFetch(`/lesson-plan?session_id=${encodeURIComponent(sid)}`);
      if (!planRes.ok) {
        setLessonPlanId(null);
        setLessonCards([]);
        setSelectedCardId("");
        return;
      }

      const planData = await planRes.json();
      const planId = planData?.lesson_plan_id;
      if (!planId) {
        setLessonPlanId(null);
        setLessonCards([]);
        setSelectedCardId("");
        return;
      }

      setLessonPlanId(planId);

      const cardsRes = await apiFetch(`/lesson-plan/${planId}/cards`);
      if (!cardsRes.ok) {
        setLessonCards([]);
        setSelectedCardId("");
        return;
      }

      const cardsData = await cardsRes.json();
      const cards = Array.isArray(cardsData?.cards) ? cardsData.cards : [];
      setLessonCards(cards);
      setSelectedCardId((prev) => {
        if (prev && cards.some((card) => String(card.card_id) === String(prev))) {
          return String(prev);
        }
        return cards.length > 0 ? String(cards[0].card_id) : "";
      });
    } catch (err) {
      console.error("Failed to load lesson cards for quiz panel", err);
      setLessonPlanId(null);
      setLessonCards([]);
      setSelectedCardId("");
    }
  }, []);

  const loadLessonSourceSessions = useCallback(async () => {
    try {
      const res = await apiFetch("/lesson-plan/sessions");
      if (!res.ok) {
        setLessonSourceSessions([]);
        return;
      }
      const data = await res.json();
      const list = Array.isArray(data)
        ? data
        : Array.isArray(data?.sessions)
          ? data.sessions
          : [];
      setLessonSourceSessions(list);
    } catch (err) {
      console.error("Failed to load lesson source sessions", err);
      setLessonSourceSessions([]);
    }
  }, []);

  const loadLatestQuiz = useCallback(
    async (sid) => {
      if (!sid) {
        if (!loadingRef.current) {
          resetQuizView();
        }
        return;
      }

      try {
        const res = await apiFetch(`/quiz/latest?session_id=${encodeURIComponent(sid)}`);
        if (!res.ok) {
          if (!loadingRef.current && pendingGeneratedSessionRef.current !== String(sid)) {
            resetQuizView();
          }
          return;
        }

        const data = await res.json();
        const normalized = normalizeQuizQuestions(data?.quiz || []);
        const hasQuizPayload = Boolean(data?.quiz_id) || normalized.length > 0;

        if (!hasQuizPayload) {
          if (!loadingRef.current && pendingGeneratedSessionRef.current !== String(sid)) {
            resetQuizView();
          }
          return;
        }

        pendingGeneratedSessionRef.current = "";
        setQuizId(data.quiz_id || "");
        setArtifactId(null);
        setQuestions(normalized);
        setAnswers({});
        setResults({});
        setQuizSource("session");
        if (normalized.length > 0 && onResultReadyRef.current) {
          onResultReadyRef.current();
        }
      } catch (err) {
        console.error("Failed to load latest quiz", err);
        if (!loadingRef.current) {
          resetQuizView();
        }
      }
    },
    [normalizeQuizQuestions, resetQuizView]
  );

  const runGenerateQuiz = async ({ reuseSession = false, preferCurrentSession = false } = {}) => {
    if (quizBlocked) {
      setError(`Quiz limit reached (${quizUsage}/${quizLimit}). Upgrade plan to continue.`);
      return;
    }

    const wantsCardQuiz = generationMode === "lesson_card";
    if (!wantsCardQuiz && !selectedChapter) {
      setError("Select content in Knowledge Base before generating a quiz.");
      return;
    }

    setError("");
    setLoadingPhase(0);
    setLoading(true);

    let sid;
    if (reuseSession) {
      sid = quizSessionId || ensureQuizSession();
      if (!sid) {
        setLoading(false);
        return;
      }
      const confirmed = window.confirm(
        "This will overwrite the current quiz in the same session. Continue?"
      );
      if (!confirmed) {
        setLoading(false);
        return;
      }
    } else {
      sid = preferCurrentSession && quizSessionId ? quizSessionId : createSessionId();
      pendingGeneratedSessionRef.current = sid;
      if (!preferCurrentSession || !quizSessionId) {
        onQuizSessionChange?.(sid);
      }
    }

    try {
      if (wantsCardQuiz) {
        const selectedLessonSession = lessonSourceSessions.find(
          (session) => String(session?.id || "") === String(lessonSourceSessionId || "")
        );

        if (!selectedLessonSession) {
          setError("Select a lesson session before generating from lesson context.");
          return;
        }

        const activeCardId = selectedCardId || (lessonCards[0] ? String(lessonCards[0].card_id) : "");
        if (!activeCardId) {
          setError("Select a lesson card before generating a lesson-based quiz.");
          return;
        }

        const res = await apiFetch(`/cards/${activeCardId}/quiz/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            context: quizContext.trim() || undefined,
            content_id: selectedContentId || undefined,
          }),
        });
        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
          setError(await parseApiError(res, "Failed to generate quiz from selected card."));
          return;
        }

        const payloadQuestions = normalizeQuizQuestions(data?.payload?.quiz || []);
        setQuizId(data?.artifact_id ? `artifact-${data.artifact_id}` : "card-quiz");
        setArtifactId(data?.artifact_id || null);
        setQuestions(payloadQuestions);
        setAnswers({});
        setResults({});
        setQuizSource("card");

        if (payloadQuestions.length > 0 && onResultReady) {
          onResultReady();
        }
      } else {
        const res = await apiFetch("/quiz/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sid,
            chapter: selectedChapter,
            quiz_context: quizContext.trim() || undefined,
            content_id: selectedContentId || undefined,
          }),
        });

        if (!res.ok) {
          setError(await parseApiError(res, "Failed to generate quiz."));
          return;
        }

        const data = await res.json();
        const normalized = normalizeQuizQuestions(data.quiz || []);
        setQuizId(data.quiz_id || "");
        setArtifactId(null);
        setQuestions(normalized);
        setAnswers({});
        setResults({});
        setQuizSource("session");
        pendingGeneratedSessionRef.current = "";
        if (normalized.length > 0 && onResultReady) {
          onResultReady();
        }
      }

      await onQuizSessionsChange?.();
    } catch (err) {
      console.error("Failed to generate quiz", err);
      setError("Failed to generate quiz.");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateQuiz = () => runGenerateQuiz({ reuseSession: false });
  const handleRegenerateQuiz = () => runGenerateQuiz({ reuseSession: true });

  const handleSubmitQuiz = async () => {
    if (quizSource === "card") {
      if (questions.length === 0) {
        setError("Generate a card quiz before submitting.");
        return;
      }

      const localResults = {};
      questions.forEach((question) => {
        const selected = answers[question.id];
        localResults[question.id] = {
          is_correct: selected === question.correct_option,
          correct_answer: question.correct_option,
        };
      });
      setResults(localResults);
      return;
    }

    if (!quizId || !quizSessionId) {
      setError("Generate or load a quiz before submitting.");
      return;
    }

    setError("");
    setSubmitting(true);

    try {
      const res = await apiFetch(`/quiz/${encodeURIComponent(quizId)}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: quizSessionId, answers }),
      });

      if (!res.ok) {
        setError(await parseApiError(res, "Failed to submit quiz."));
        return;
      }

      const data = await res.json();
      setResults(data || {});
    } catch (err) {
      console.error("Failed to submit quiz", err);
      setError("Failed to submit quiz.");
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    setChapter(defaultChapter || "");
  }, [defaultChapter]);

  useEffect(() => {
    if (prefillContext) {
      setQuizContext(prefillContext);
      setGenerationMode("context");
    }
  }, [prefillContext]);

  useEffect(() => {
    const normalized = normalizeQuizQuestions(prefilledQuizData?.quiz || []);
    if (normalized.length === 0) return;

    setQuizId(prefilledQuizData?.quiz_id || "");
    setArtifactId(prefilledQuizData?.artifact_id || null);
    setQuestions(normalized);
    setAnswers({});
    setResults({});
    setQuizSource("session");
    onResultReady?.();
  }, [normalizeQuizQuestions, onResultReady, prefilledQuizData]);

  useEffect(() => {
    if (!autoRunToken) return;
    skipNextSessionLoadRef.current = true;
    runGenerateQuiz({ reuseSession: false, preferCurrentSession: true });
  }, [autoRunToken]);

  useEffect(() => {
    if (!quizSessionId && sessionId) {
      onQuizSessionChange?.(sessionId);
    }
  }, [onQuizSessionChange, quizSessionId, sessionId]);

  useEffect(() => {
    loadLessonSourceSessions();
  }, [loadLessonSourceSessions]);

  useEffect(() => {
    if (lessonSourceSessionId) return;
    if (lessonSourceSessions.length > 0) {
      setLessonSourceSessionId(String(lessonSourceSessions[0].id));
    }
  }, [lessonSourceSessionId, lessonSourceSessions]);

  useEffect(() => {
    if (!quizSessionId) {
      resetQuizView();
      return;
    }

    if (skipNextSessionLoadRef.current) {
      skipNextSessionLoadRef.current = false;
      return;
    }

    loadLatestQuiz(quizSessionId);
  }, [quizSessionId, loadLatestQuiz, resetQuizView]);

  useEffect(() => {
    if (!lessonSourceSessionId) {
      setLessonPlanId(null);
      setLessonCards([]);
      setSelectedCardId("");
      return;
    }
    loadLessonCardsForSession(lessonSourceSessionId);
  }, [lessonSourceSessionId, loadLessonCardsForSession]);

  useEffect(() => {
    if (!loading) return undefined;
    const timer = setInterval(() => {
      setLoadingPhase((prev) => (prev + 1) % GENERATE_PHASES.length);
    }, 2200);
    return () => clearInterval(timer);
  }, [loading]);

  const scoreTotal = questions.length;
  const scoreCorrect = Object.values(results).filter((result) => result?.is_correct).length;
  const scorePct = scoreTotal > 0 ? Math.round((scoreCorrect / scoreTotal) * 100) : 0;
  const hasScore = Object.keys(results).length > 0;

  return (
    <div className="workspace-panel quiz-panel">
      <div className="workspace-panel__header">
        <div>
          <div className="workspace-panel__title-row">
            <h3>Contextual chapter quiz</h3>
            <div className="workspace-panel__eyebrow">
              <FiClipboard />
              <span>Quiz</span>
            </div>
          </div>
          <p>Generate quizzes from selected content, or switch source to a lesson card from your lesson plan.</p>
        </div>
      </div>

      <div className="panel-grid panel-grid--stacked">
        <section className="panel-card">
          <div className="study-generator-toolbar">
            <div className="study-generator-toolbar__top">
              <div className="lesson-toolbar__actions">
                <button type="button" className="primary-button" onClick={handleGenerateQuiz} disabled={loading}>
                  <FiClipboard />
                  <span>{loading ? "Creating Quiz..." : "New Quiz"}</span>
                </button>
                {Boolean(quizSessionId) && (
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={handleRegenerateQuiz}
                    disabled={loading}
                  >
                    <FiRefreshCw />
                    <span>{loading ? "Regenerating..." : "Regenerate Quiz"}</span>
                  </button>
                )}
              </div>

              <div className="quiz-source-picker">
                <div className="workspace-sidebar__section-title">
                  <FiLayers />
                  <span>Choose context for generating quiz</span>
                </div>
                <div className="quiz-source-toggle" role="group" aria-label="Quiz source selector">
                  <button
                    type="button"
                    className={`secondary-button ${generationMode === "context" ? "quiz-source-toggle__option--active" : ""}`}
                    onClick={() => setGenerationMode("context")}
                  >
                    Current Context
                  </button>
                  <button
                    type="button"
                    className={`secondary-button ${generationMode === "lesson_card" ? "quiz-source-toggle__option--active" : ""}`}
                    onClick={() => setGenerationMode("lesson_card")}
                  >
                    Lesson Card
                  </button>
                </div>
              </div>
            </div>

            <div className="lesson-toolbar__context lesson-toolbar__context--full">
              <label htmlFor="quiz-context">Optional quiz focus</label>
              <input
                id="quiz-context"
                type="text"
                className="lesson-context-input"
                placeholder="Example: exam-level MCQs, common mistakes, short recall"
                value={quizContext}
                onChange={(event) => setQuizContext(event.target.value)}
              />
            </div>
          </div>

          {loading && <div className="stream-status"><span>{GENERATE_PHASES[loadingPhase]}</span></div>}

          {quizBlocked && (
            <div className="sidebar-note">
              Quiz generation limit reached ({quizUsage}/{quizLimit}).
            </div>
          )}

          {generationMode === "lesson_card" && (
            <div className="quiz-card-controls">
              <div className="workspace-sidebar__section-title">
                <FiLayers />
                <span>Lesson Card Source</span>
              </div>
              <div className="workspace-select-wrap workspace-select-wrap--compact">
                <FiLayers />
                <select
                  value={lessonSourceSessionId || ""}
                  onChange={(event) => setLessonSourceSessionId(event.target.value || "")}
                  disabled={lessonSourceSessions.length === 0}
                >
                  <option value="">Select lesson session</option>
                  {lessonSourceSessions.map((session) => (
                    <option key={session.id} value={session.id}>
                      {session.title || session.id}
                    </option>
                  ))}
                </select>
              </div>
              <div className="workspace-select-wrap workspace-select-wrap--compact">
                <FiClipboard />
                <select
                  value={selectedCardId || ""}
                  onChange={(event) => setSelectedCardId(event.target.value || "")}
                  disabled={!lessonSourceSessionId || lessonCards.length === 0}
                >
                  <option value="">Select lesson card</option>
                  {lessonCards.map((card) => (
                    <option key={card.card_id} value={card.card_id}>
                      {card.order || card.card_id}. {card.title}
                    </option>
                  ))}
                </select>
              </div>
              {!lessonSourceSessionId && (
                <div className="sidebar-note">Select a lesson session to use lesson context.</div>
              )}
              {lessonSourceSessionId && !lessonPlanId && (
                <div className="sidebar-note">No lesson plan found for selected session. Pick another lesson session.</div>
              )}
            </div>
          )}

          {error && <div className="sidebar-note">{error}</div>}
        </section>

        <section className="panel-card panel-card--stretch">
          {questions.length === 0 && (
            <div className="empty-state panel-empty-state">
              <FiClipboard />
              <h4>No quiz loaded</h4>
              <p>Use the source selector and generate a quiz from your current context or a lesson card.</p>
            </div>
          )}

          {questions.length > 0 && (
            <>
              <div className="workspace-sidebar__section-title">
                <FiClipboard />
                <span>
                  {quizSource === "card" ? "Card Quiz" : "Session Quiz"}: {quizId}
                  {artifactId ? ` (Artifact #${artifactId})` : ""}
                </span>
              </div>

              <div className="quiz-questions lesson-steps--full">
                {questions.map((question) => {
                  const questionResult = results?.[question.id];
                  return (
                    <div key={question.id} className="quiz-question-card">
                      <div className="lesson-step__content quiz-question-card__body">
                        <strong>{question.question}</strong>
                        <div className="quiz-options">
                          {(question.options || []).map((option, idx) => (
                            <label key={`${question.id}-${idx}`} className="quiz-option">
                              <input
                                type="radio"
                                name={question.id}
                                value={option}
                                checked={answers[question.id] === option}
                                onChange={(e) =>
                                  setAnswers((prev) => ({
                                    ...prev,
                                    [question.id]: e.target.value,
                                  }))
                                }
                              />
                              <span>{option}</span>
                            </label>
                          ))}
                        </div>

                        {questionResult && (
                          <div className={`quiz-feedback ${questionResult.is_correct ? "ok" : "bad"}`}>
                            <FiCheckCircle />
                            <span>
                              {questionResult.is_correct
                                ? "Correct"
                                : `Incorrect. Correct answer: ${questionResult.correct_answer}`}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}

                <div className="quiz-submit-row">
                  <button type="button" className="primary-button" onClick={handleSubmitQuiz} disabled={submitting}>
                    <FiCheckCircle />
                    <span>{submitting ? "Submitting..." : "Submit Answers"}</span>
                  </button>
                  {hasScore && (
                    <div className="quiz-score-summary">
                      <div className="quiz-score-summary__bar">
                        <div
                          className="quiz-score-summary__fill"
                          style={{ width: `${scorePct}%`, background: scorePct >= 70 ? "#10a37f" : scorePct >= 40 ? "#f5a623" : "#e74c3c" }}
                        />
                      </div>
                      <span className="quiz-score-summary__label">
                        <FiCheckCircle />
                        {scoreCorrect} / {scoreTotal} right — {scorePct}%
                      </span>
                    </div>
                  )}
                </div>
              </div>

            </>
          )}
        </section>
      </div>
    </div>
  );
}
