import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  FiCheck,
  FiClipboard,
  FiDownload,
  FiEdit,
  FiFileText,
  FiLoader,
  FiRefreshCw,
  FiX,
} from "react-icons/fi";
import { apiFetch, parseApiError } from "../services/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DIFFICULTY_OPTIONS = [
  { value: "mixed", label: "Mixed" },
  { value: "easy",  label: "Easy" },
  { value: "medium",label: "Medium" },
  { value: "hard",  label: "Hard" },
];

const HISTORY_FILTER_OPTIONS = [
  { value: "ALL", label: "All" },
  { value: "SUBJECT_QUIZ", label: "Quizzes" },
  { value: "QUESTION_PAPER", label: "Papers" },
];

function formatAssessmentDate(value) {
  if (!value) return "Saved recently";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function buildHistoryMeta(item) {
  if (!item) return "";
  if (item.paper_type === "QUESTION_PAPER") {
    const sectionCount = Number(item.section_count || 0);
    const totalMarks = Number(item.total_marks || 0);
    return [
      sectionCount > 0 ? `${sectionCount} section${sectionCount === 1 ? "" : "s"}` : null,
      totalMarks > 0 ? `${totalMarks} marks` : null,
      item.difficulty || null,
    ].filter(Boolean).join(" · ");
  }

  const questionCount = Number(item.question_count || 0);
  return [
    questionCount > 0 ? `${questionCount} question${questionCount === 1 ? "" : "s"}` : null,
    item.mode ? `${item.mode} mode` : null,
    item.difficulty || null,
  ].filter(Boolean).join(" · ");
}

function slugifyAssessment(value) {
  return String(value || "assessment")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "assessment";
}

function QuizQuestion({ q, mode, answers, onAnswer, revealed }) {
  const chosen = answers[q.id] ?? null;
  const isCorrect = chosen === q.correct_option;

  return (
    <div className={`assessment-question${revealed ? (isCorrect ? " assessment-question--correct" : " assessment-question--wrong") : ""}`}>
      <p className="assessment-question__text">
        <span className="assessment-question__id">{q.id}.</span> {q.question}
        <span className="assessment-question__marks">({q.marks} mark)</span>
      </p>
      <div className="assessment-options">
        {(q.options || []).map((opt) => {
          const isChosen = chosen === opt;
          const isRight = revealed && opt === q.correct_option;
          return (
            <button
              key={opt}
              onClick={() => !revealed && onAnswer(q.id, opt)}
              disabled={revealed}
              className={
                "assessment-option" +
                (isChosen ? " assessment-option--chosen" : "") +
                (isRight ? " assessment-option--correct" : "") +
                (revealed && isChosen && !isCorrect ? " assessment-option--wrong" : "")
              }
            >
              {isRight && <FiCheck className="assessment-option__icon" />}
              {opt}
            </button>
          );
        })}
      </div>
      {revealed && q.explanation && (
        <p className="assessment-explanation">{q.explanation}</p>
      )}
    </div>
  );
}

function PaperQuestion({ q, answers, onAnswer, showAnswerKey }) {
  const isMcq = Boolean(q.options);
  const chosen = answers[q.id] ?? null;
  const isCorrect = isMcq && chosen === q.answer;

  return (
    <div className={`assessment-question${showAnswerKey && isMcq ? (isCorrect ? " assessment-question--correct" : " assessment-question--wrong") : ""}`}>
      <p className="assessment-question__text">
        <span className="assessment-question__id">{q.id}.</span> {q.question}
        <span className="assessment-question__marks">({q.marks} marks)</span>
      </p>
      {isMcq ? (
        <div className="assessment-options">
          {(q.options || []).map((opt) => {
            const isChosen = chosen === opt;
            const isRight = showAnswerKey && opt === q.answer;
            return (
              <button
                key={opt}
                onClick={() => !showAnswerKey && onAnswer(q.id, opt)}
                disabled={showAnswerKey}
                className={
                  "assessment-option" +
                  (isChosen ? " assessment-option--chosen" : "") +
                  (isRight ? " assessment-option--correct" : "") +
                  (showAnswerKey && isChosen && !isCorrect ? " assessment-option--wrong" : "")
                }
              >
                {isRight && <FiCheck className="assessment-option__icon" />}
                {opt}
              </button>
            );
          })}
        </div>
      ) : (
        <textarea
          className="assessment-textarea"
          placeholder="Write your answer here..."
          value={answers[q.id] ?? ""}
          onChange={(e) => onAnswer(q.id, e.target.value)}
          rows={3}
        />
      )}
      {showAnswerKey && q.answer_key && (
        <div className="assessment-answer-key">
          <strong>Model Answer:</strong> {q.answer_key}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AssessmentPanel({
  planSummary = null,
  defaultSubject = "",
  selectedClass = null,
  prefillSubject = "",
  prefillContext = "",
  prefillQuizMode = "",
  prefillDifficulty = "",
  prefillNumQuestions = null,
  autoRunToken = "",
}) {
  const [view, setView] = useState("form"); // "form" | "quiz" | "paper" | "history"
  const [mode, setMode] = useState("subject-quiz"); // "subject-quiz" | "question-paper"

  // Form state
  const [subject, setSubject] = useState(defaultSubject || "");
  const [className, setClassName] = useState(selectedClass || "");
  const [difficulty, setDifficulty] = useState("mixed");
  const [quizMode, setQuizMode] = useState("practice");
  const [numQuestions, setNumQuestions] = useState(10);
  const [totalMarks, setTotalMarks] = useState(40);

  // Result state
  const [paper, setPaper] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [historyItems, setHistoryItems] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [historyFilter, setHistoryFilter] = useState("ALL");
  const [openingPaperId, setOpeningPaperId] = useState(null);
  const [exportingPaperId, setExportingPaperId] = useState(null);

  // Quiz interaction
  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [showAnswerKey, setShowAnswerKey] = useState(false);
  const [savingAttempt, setSavingAttempt] = useState(false);
  const [attemptMessage, setAttemptMessage] = useState("");
  const [attemptSummary, setAttemptSummary] = useState(null);
  const lastAutoRunTokenRef = useRef("");

  const quizBlocked = planSummary?.limits?.quiz_count > 0
    && (planSummary?.usage?.quiz_count || 0) >= planSummary.limits.quiz_count;

  const handleAnswer = useCallback((qId, value) => {
    setAnswers((prev) => ({ ...prev, [qId]: value }));
  }, []);

  const loadHistory = useCallback(async (filterValue = historyFilter) => {
    setHistoryLoading(true);
    setHistoryError("");

    try {
      const query = filterValue && filterValue !== "ALL"
        ? `?paper_type=${encodeURIComponent(filterValue)}`
        : "";
      const res = await apiFetch(`/assessment/papers${query}`);
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not load assessment history."));
      }
      const data = await res.json();
      const payload = data?.data || data;
      setHistoryItems(Array.isArray(payload?.papers) ? payload.papers : []);
    } catch (err) {
      setHistoryError(err?.message || "Could not load assessment history.");
    } finally {
      setHistoryLoading(false);
    }
  }, [historyFilter]);

  const handleShowHistory = useCallback(() => {
    setView("history");
    setError("");
    loadHistory(historyFilter);
  }, [historyFilter, loadHistory]);

  const handleHistoryFilterChange = useCallback((filterValue) => {
    setHistoryFilter(filterValue);
    loadHistory(filterValue);
  }, [loadHistory]);

  const handleOpenHistoryItem = useCallback(async (item) => {
    if (!item?.paper_id) return;

    setOpeningPaperId(item.paper_id);
    setHistoryError("");
    setAnswers({});
    setSubmitted(false);
    setShowAnswerKey(false);
    setSavingAttempt(false);
    setAttemptMessage("");
    setAttemptSummary(null);

    try {
      const res = await apiFetch(`/assessment/papers/${item.paper_id}`);
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not open this assessment."));
      }
      const data = await res.json();
      const payload = (data?.data || data)?.paper;
      if (!payload) {
        throw new Error("Assessment details were empty.");
      }

      const fallbackAttemptSummary = Number(item?.attempt_count || 0) > 0
        ? {
            attempt_count: Number(item.attempt_count || 0),
            best_score_pct: Number(item.best_score_pct || 0),
            last_score_pct: Number(item.last_score_pct || 0),
            last_attempted_at: item.last_attempted_at || null,
            recent_scores: Array.isArray(item.recent_scores) ? item.recent_scores : [],
          }
        : null;

      setPaper(payload);
      setAttemptSummary(payload?.attempt_summary || fallbackAttemptSummary);
      setMode(payload.paper_type === "QUESTION_PAPER" ? "question-paper" : "subject-quiz");
      setView(payload.paper_type === "QUESTION_PAPER" ? "paper" : "quiz");
    } catch (err) {
      setHistoryError(err?.message || "Could not open this assessment.");
    } finally {
      setOpeningPaperId(null);
    }
  }, []);

  const handleExportHistoryItem = useCallback(async (item) => {
    if (!item?.paper_id) return;

    setExportingPaperId(item.paper_id);
    setHistoryError("");

    try {
      const res = await apiFetch(`/assessment/papers/${item.paper_id}`);
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not export this assessment."));
      }

      const data = await res.json();
      const payload = (data?.data || data)?.paper;
      if (!payload) {
        throw new Error("Assessment details were empty.");
      }

      const fileName = `${slugifyAssessment(payload.subject)}-${slugifyAssessment(payload.paper_type)}-${payload.paper_id}.json`;
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const objectUrl = window?.URL?.createObjectURL?.(blob);

      if (!objectUrl) {
        throw new Error("Export is not available in this browser.");
      }

      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL?.(objectUrl);
    } catch (err) {
      setHistoryError(err?.message || "Could not export this assessment.");
    } finally {
      setExportingPaperId(null);
    }
  }, []);

  const generateAssessment = useCallback(async (overrides = {}) => {
    const nextMode = overrides.mode || mode;
    const nextSubject = String(overrides.subject ?? subject).trim();
    const nextClassName = String(overrides.className ?? className).trim();
    const nextDifficulty = String(overrides.difficulty || difficulty || "mixed");
    const nextQuizMode = String(overrides.quizMode || quizMode || "practice");
    const nextNumQuestions = Number(overrides.numQuestions ?? numQuestions);
    const nextTotalMarks = Number(overrides.totalMarks ?? totalMarks);

    if (!nextSubject) {
      setError("Subject is required.");
      return;
    }
    setError("");
    setLoading(true);
    setPaper(null);
    setAnswers({});
    setSubmitted(false);
    setShowAnswerKey(false);
    setSavingAttempt(false);
    setAttemptMessage("");
    setAttemptSummary(null);

    const endpoint = nextMode === "subject-quiz"
      ? "/assessment/subject-quiz"
      : "/assessment/question-paper";
    const body = nextMode === "subject-quiz"
      ? { subject: nextSubject, class_name: nextClassName || undefined, num_questions: nextNumQuestions, difficulty: nextDifficulty, mode: nextQuizMode }
      : { subject: nextSubject, class_name: nextClassName || undefined, total_marks: nextTotalMarks, difficulty: nextDifficulty };

    try {
      const res = await apiFetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Generation failed."));
      }
      const data = await res.json();
      const payload = data?.data || data;
      setPaper(payload);
      setAttemptSummary(payload?.attempt_summary || null);
      setView(nextMode === "subject-quiz" ? "quiz" : "paper");
    } catch (err) {
      setError(err?.message || "Generation failed.");
    } finally {
      setLoading(false);
    }
  }, [className, difficulty, mode, numQuestions, quizMode, subject, totalMarks]);

  const handleGenerate = useCallback(async () => {
    await generateAssessment();
  }, [generateAssessment]);

  useEffect(() => {
    if (defaultSubject) {
      setSubject(defaultSubject);
    }
  }, [defaultSubject]);

  useEffect(() => {
    if (selectedClass !== null && selectedClass !== undefined) {
      setClassName(selectedClass || "");
    }
  }, [selectedClass]);

  useEffect(() => {
    if (!prefillSubject) return;
    setView("form");
    setMode("subject-quiz");
    setSubject(prefillSubject);
    if (prefillQuizMode) {
      setQuizMode(prefillQuizMode);
    }
    if (prefillDifficulty) {
      setDifficulty(prefillDifficulty);
    }
    if (prefillNumQuestions) {
      setNumQuestions(Number(prefillNumQuestions));
    }
  }, [prefillDifficulty, prefillNumQuestions, prefillQuizMode, prefillSubject]);

  useEffect(() => {
    if (!autoRunToken || autoRunToken === lastAutoRunTokenRef.current) return;
    lastAutoRunTokenRef.current = autoRunToken;

    const subjectToRun = String(prefillSubject || defaultSubject || "").trim();
    if (!subjectToRun) return;

    const nextQuizMode = prefillQuizMode || "exam";
    const nextDifficulty = prefillDifficulty || "mixed";
    const nextNumQuestions = Number(prefillNumQuestions || 5);

    setView("form");
    setMode("subject-quiz");
    setSubject(subjectToRun);
    setQuizMode(nextQuizMode);
    setDifficulty(nextDifficulty);
    setNumQuestions(nextNumQuestions);

    generateAssessment({
      mode: "subject-quiz",
      subject: subjectToRun,
      className: selectedClass || className || "",
      difficulty: nextDifficulty,
      quizMode: nextQuizMode,
      numQuestions: nextNumQuestions,
    });
  }, [autoRunToken, className, defaultSubject, generateAssessment, prefillDifficulty, prefillNumQuestions, prefillQuizMode, prefillSubject, selectedClass]);

  const calcScore = useCallback(() => {
    if (!paper?.questions?.length) return null;
    const total = paper.questions.length;
    const correct = paper.questions.filter((q) => answers[q.id] === q.correct_option).length;
    return { correct, total, pct: Math.round((correct / total) * 100) };
  }, [answers, paper]);

  const handleSubmitQuiz = useCallback(async () => {
    setSubmitted(true);

    const score = calcScore();
    const isPractice = (paper?.mode || quizMode) === "practice";
    if (!score || isPractice || !paper?.paper_id) {
      return;
    }

    setSavingAttempt(true);
    setAttemptMessage("");

    try {
      const res = await apiFetch(`/assessment/papers/${paper.paper_id}/attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          correct_count: score.correct,
          total_questions: score.total,
          score_pct: score.pct,
        }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not save this attempt to history."));
      }

      const data = await res.json();
      const summary = (data?.data || data)?.attempt_summary || null;
      setAttemptSummary(summary);
      setAttemptMessage("Attempt saved to history.");
      setPaper((prev) => (prev ? { ...prev, attempt_summary: summary } : prev));
    } catch (err) {
      setAttemptMessage(err?.message || "Score calculated, but the attempt could not be saved to history.");
    } finally {
      setSavingAttempt(false);
    }
  }, [calcScore, paper, quizMode]);

  // ---------------------------------------------------------------------------
  // Render: form
  // ---------------------------------------------------------------------------
  const renderForm = () => (
    <div className="assessment-form">
      <div className="assessment-mode-toggle">
        <button
          className={mode === "subject-quiz" ? "active" : ""}
          onClick={() => setMode("subject-quiz")}
        >
          <FiClipboard /> Subject Quiz
        </button>
        <button
          className={mode === "question-paper" ? "active" : ""}
          onClick={() => setMode("question-paper")}
        >
          <FiFileText /> Question Paper
        </button>
      </div>

      <div className="assessment-form__fields">
        <label className="assessment-form__label">
          Subject
          <input
            type="text"
            className="assessment-form__input"
            placeholder="e.g. Science, Mathematics"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
          />
        </label>

        <label className="assessment-form__label">
          Class / Grade <span className="assessment-form__optional">(optional)</span>
          <input
            type="text"
            className="assessment-form__input"
            placeholder="e.g. Class 10"
            value={className}
            onChange={(e) => setClassName(e.target.value)}
          />
        </label>

        <label className="assessment-form__label">
          Difficulty
          <select
            className="assessment-form__select"
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value)}
          >
            {DIFFICULTY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>

        {mode === "subject-quiz" ? (
          <>
            <label className="assessment-form__label">
              Number of questions
              <input
                type="number"
                className="assessment-form__input"
                min={1}
                max={30}
                value={numQuestions}
                onChange={(e) => setNumQuestions(Number(e.target.value))}
              />
            </label>
            <label className="assessment-form__label">
              Mode
              <select
                className="assessment-form__select"
                value={quizMode}
                onChange={(e) => setQuizMode(e.target.value)}
              >
                <option value="practice">Practice (immediate feedback)</option>
                <option value="exam">Exam (submit all at end)</option>
              </select>
            </label>
          </>
        ) : (
          <label className="assessment-form__label">
            Total marks
            <input
              type="number"
              className="assessment-form__input"
              min={10}
              max={200}
              value={totalMarks}
              onChange={(e) => setTotalMarks(Number(e.target.value))}
            />
          </label>
        )}
      </div>

      {error && <p className="assessment-error">{error}</p>}

      {quizBlocked && (
        <p className="sidebar-note assessment-quota-warn">
          Quiz quota reached for this period. Upgrade your plan to generate more assessments.
        </p>
      )}

      <button
        className="btn-primary assessment-generate-btn"
        onClick={handleGenerate}
        disabled={loading || quizBlocked}
      >
        {loading ? (
          <><FiRefreshCw className="spin" /> Generating...</>
        ) : (
          <><FiEdit /> Generate {mode === "subject-quiz" ? "Subject Quiz" : "Question Paper"}</>
        )}
      </button>
    </div>
  );

  // ---------------------------------------------------------------------------
  // Render: subject quiz result
  // ---------------------------------------------------------------------------
  const renderQuiz = () => {
    if (!paper?.questions?.length) return null;
    const isPractice = (paper.mode || quizMode) === "practice";
    const score = submitted ? calcScore() : null;

    return (
      <div className="assessment-result">
        <div className="assessment-result__header">
          <div>
            <h3>{paper.subject}{paper.class_name ? ` — ${paper.class_name}` : ""}</h3>
            <p className="sidebar-note">{paper.questions.length} questions · {paper.difficulty} · {isPractice ? "practice" : "exam"} mode</p>
          </div>
          <button className="icon-button icon-button--ghost" onClick={() => { setPaper(null); setView("form"); setAnswers({}); setSubmitted(false); setSavingAttempt(false); setAttemptMessage(""); setAttemptSummary(null); }}>
            <FiX />
          </button>
        </div>

        {score && (
          <div className={`assessment-score${score.pct >= 70 ? " assessment-score--pass" : " assessment-score--fail"}`}>
            Score: <strong>{score.correct}/{score.total}</strong> ({score.pct}%)
          </div>
        )}

        {(Number(attemptSummary?.attempt_count || 0) > 0 || (!isPractice && submitted && (savingAttempt || attemptMessage))) && (
          <div className="assessment-attempt-feedback">
            {savingAttempt && <p className="sidebar-note">Saving attempt…</p>}
            {attemptMessage && <p className="sidebar-note">{attemptMessage}</p>}
            {attemptSummary?.attempt_count > 0 && (
              <>
                <p className="sidebar-note">
                  Best {attemptSummary.best_score_pct}% across {attemptSummary.attempt_count} attempt{attemptSummary.attempt_count === 1 ? "" : "s"}
                  {typeof attemptSummary.last_score_pct === "number" ? ` · latest ${attemptSummary.last_score_pct}%` : ""}
                </p>
                {attemptSummary.last_attempted_at && (
                  <p className="sidebar-note">Last saved {formatAssessmentDate(attemptSummary.last_attempted_at)}</p>
                )}
                {Array.isArray(attemptSummary.recent_scores) && attemptSummary.recent_scores.length > 0 && (
                  <p className="sidebar-note">
                    Recent scores: {attemptSummary.recent_scores.map((value) => `${value}%`).join(" · ")}
                  </p>
                )}
              </>
            )}
          </div>
        )}

        <div className="assessment-questions-list">
          {paper.questions.map((q) => (
            <QuizQuestion
              key={q.id}
              q={q}
              mode={isPractice ? "practice" : "exam"}
              answers={answers}
              onAnswer={isPractice ? handleAnswer : (id, val) => !submitted && handleAnswer(id, val)}
              revealed={isPractice ? Boolean(answers[q.id]) : submitted}
            />
          ))}
        </div>

        {!isPractice && !submitted && (
          <button
            className="btn-primary assessment-submit-btn"
            onClick={handleSubmitQuiz}
            disabled={Object.keys(answers).length === 0 || savingAttempt}
          >
            Submit Answers
          </button>
        )}

        <button className="btn-secondary assessment-retry-btn" onClick={() => { setView("form"); setAnswers({}); setSubmitted(false); setSavingAttempt(false); setAttemptMessage(""); setAttemptSummary(null); setPaper(null); }}>
          <FiRefreshCw /> New Assessment
        </button>
      </div>
    );
  };

  // ---------------------------------------------------------------------------
  // Render: question paper result
  // ---------------------------------------------------------------------------
  const renderPaper = () => {
    if (!paper?.sections?.length) return null;
    return (
      <div className="assessment-result">
        <div className="assessment-result__header">
          <div>
            <h3>{paper.subject}{paper.class_name ? ` — ${paper.class_name}` : ""}</h3>
            <p className="sidebar-note">Total marks: {paper.total_marks} · {paper.difficulty} difficulty</p>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button
              className={`icon-button${showAnswerKey ? " icon-button--active" : ""}`}
              onClick={() => setShowAnswerKey((v) => !v)}
              title={showAnswerKey ? "Hide answer key" : "Show answer key"}
            >
              {showAnswerKey ? <FiCheck /> : <FiFileText />}
            </button>
            <button className="icon-button icon-button--ghost" onClick={() => { setPaper(null); setView("form"); setAnswers({}); setShowAnswerKey(false); }}>
              <FiX />
            </button>
          </div>
        </div>

        {paper.sections.map((sec) => (
          <div key={sec.name} className="assessment-section">
            <div className="assessment-section__header">
              <strong>{sec.name}</strong>
              <span className="assessment-section__meta">{sec.description} · {sec.marks_per_q} mark(s) each · {sec.section_total} marks</span>
            </div>
            {(sec.questions || []).map((q) => (
              <PaperQuestion
                key={q.id}
                q={q}
                answers={answers}
                onAnswer={handleAnswer}
                showAnswerKey={showAnswerKey}
              />
            ))}
          </div>
        ))}

        <button className="btn-secondary assessment-retry-btn" onClick={() => { setView("form"); setAnswers({}); setShowAnswerKey(false); setPaper(null); }}>
          <FiRefreshCw /> New Paper
        </button>
      </div>
    );
  };

  const renderHistory = () => (
    <div className="assessment-history">
      <div className="assessment-history__header">
        <div>
          <h4>Recent Assessments</h4>
          <p className="sidebar-note">Reopen any saved quiz or question paper from your earlier practice.</p>
        </div>
        <button
          className="icon-button icon-button--ghost"
          onClick={() => loadHistory(historyFilter)}
          disabled={historyLoading}
          title="Refresh history"
        >
          <FiRefreshCw className={historyLoading ? "spin" : ""} />
        </button>
      </div>

      <div className="assessment-history__filters" role="group" aria-label="Assessment history filters">
        {HISTORY_FILTER_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            className={`assessment-history__filter${historyFilter === option.value ? " active" : ""}`}
            onClick={() => handleHistoryFilterChange(option.value)}
            disabled={historyLoading}
          >
            {option.label}
          </button>
        ))}
      </div>

      {historyError && <p className="assessment-error">{historyError}</p>}

      {historyLoading ? (
        <div className="assessment-history__empty">
          <FiLoader className="spin" />
          <span>Loading assessment history…</span>
        </div>
      ) : historyItems.length === 0 ? (
        <div className="assessment-history__empty">
          <p>No saved assessments yet for this filter. Generate a quiz or paper to see it here.</p>
        </div>
      ) : (
        <div className="assessment-history__list">
          {historyItems.map((item) => {
            const isPaper = item.paper_type === "QUESTION_PAPER";
            const isOpening = openingPaperId === item.paper_id;
            const isExporting = exportingPaperId === item.paper_id;
            return (
              <article key={item.paper_id} className="assessment-history-card">
                <div className="assessment-history-card__top">
                  <span className={`assessment-history-card__badge${isPaper ? " is-paper" : " is-quiz"}`}>
                    {isPaper ? "Question Paper" : "Subject Quiz"}
                  </span>
                  <span className="assessment-history-card__date">{formatAssessmentDate(item.created_at)}</span>
                </div>

                <h4>{item.subject}{item.class_name ? ` — ${item.class_name}` : ""}</h4>
                <p className="sidebar-note">{buildHistoryMeta(item)}</p>
                {Number(item.attempt_count || 0) > 0 && (
                  <>
                    <p className="sidebar-note">
                      Best {item.best_score_pct}% across {item.attempt_count} attempt{Number(item.attempt_count) === 1 ? "" : "s"}
                      {typeof item.last_score_pct === "number" ? ` · latest ${item.last_score_pct}%` : ""}
                    </p>
                    {item.last_attempted_at && (
                      <p className="sidebar-note">Last saved {formatAssessmentDate(item.last_attempted_at)}</p>
                    )}
                    {Array.isArray(item.recent_scores) && item.recent_scores.length > 0 && (
                      <p className="sidebar-note">
                        Recent scores: {item.recent_scores.map((value) => `${value}%`).join(" · ")}
                      </p>
                    )}
                  </>
                )}

                <div className="assessment-history-card__actions">
                  <button
                    className="btn-secondary assessment-history-card__open"
                    onClick={() => handleOpenHistoryItem(item)}
                    disabled={isOpening || isExporting}
                  >
                    {isOpening ? <FiLoader className="spin" /> : isPaper ? <FiFileText /> : <FiClipboard />}
                    {isPaper ? "Open Paper" : "Open Quiz"}
                  </button>
                  <button
                    className="btn-secondary assessment-history-card__export"
                    onClick={() => handleExportHistoryItem(item)}
                    disabled={isExporting || isOpening}
                  >
                    {isExporting ? <FiLoader className="spin" /> : <FiDownload />}
                    Export JSON
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );

  // ---------------------------------------------------------------------------
  // Entry
  // ---------------------------------------------------------------------------
  return (
    <div className="assessment-panel workspace-panel">
      <div className="workspace-panel__header">
        <div className="assessment-panel__header-copy">
          <div className="workspace-panel__title-row">
            <h3>Assessment Workspace</h3>
            <div className="workspace-panel__eyebrow">
              <FiEdit />
              <span>Assessment</span>
            </div>
          </div>
          <h4 className="assessment-panel__mode-heading">
            {view === "form"
              ? "Generate Assessment"
              : view === "history"
              ? "Assessment History"
              : view === "quiz"
              ? "Subject Quiz"
              : "Question Paper"}
          </h4>
          <p>Generate timed quizzes and question papers in the same focused workspace style as your other study tools.</p>
        </div>
        <div className="assessment-panel__header-actions">
          <button
            type="button"
            className={`secondary-button ${view === "form" ? "is-active" : ""}`}
            onClick={() => setView("form")}
          >
            <FiEdit />
            <span>New</span>
          </button>
          <button
            type="button"
            className={`secondary-button ${view === "history" ? "is-active" : ""}`}
            onClick={handleShowHistory}
          >
            <FiClipboard />
            <span>History</span>
          </button>
        </div>
      </div>

      <div className="assessment-panel__body">
        {view === "form" && renderForm()}
        {view === "history" && renderHistory()}
        {view === "quiz" && renderQuiz()}
        {view === "paper" && renderPaper()}
      </div>
    </div>
  );
}
