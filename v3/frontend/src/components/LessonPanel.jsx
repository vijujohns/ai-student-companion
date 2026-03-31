import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  FiBookOpen,
  FiCheckSquare,
  FiChevronDown,
  FiChevronUp,
  FiLayers,
  FiRefreshCw,
  FiSave,
  FiZap,
} from "react-icons/fi";
import { apiFetch, parseApiError } from "../services/api";

function createSessionId() {
  return `${Date.now()}`;
}

const GENERATE_PHASES = [
  "Reading selected content...",
  "Designing lesson structure...",
  "Creating activities and checks...",
  "Finalizing lesson cards...",
];

export default function LessonPanel({
  sessionId,
  lessonSessionId,
  onLessonSessionChange,
  onLessonSessionsChange,
  planSummary = null,
  defaultChapter = "",
  currentContextLabel = null,
  hasLinkedContent = false,
  isContextViewerVisible = false,
  onOpenContext = null,
  onResultReady = null,
}) {
  const [chapter, setChapter] = useState(defaultChapter || "");
  const [lessonContext, setLessonContext] = useState("");
  const [plan, setPlan] = useState(null);
  const [cards, setCards] = useState([]);
  const [cardActionLoading, setCardActionLoading] = useState({});
  const [artifactByCard, setArtifactByCard] = useState({});
  const [artifactMetaByCard, setArtifactMetaByCard] = useState({});
  const [loading, setLoading] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState(0);
  const [error, setError] = useState("");
  const [expandedSteps, setExpandedSteps] = useState({});

  const getLimitState = useCallback(
    (action) => {
      if (!planSummary) return { blocked: false, used: 0, limit: 0 };
      const fieldByAction = {
        lesson: "lesson_count",
        quiz: "quiz_count",
        flashcard: "flashcard_count",
      };
      const field = fieldByAction[action];
      if (!field) return { blocked: false, used: 0, limit: 0 };
      const used = Number(planSummary.usage?.[field] || 0);
      const limit = Number(planSummary.limits?.[field] || 0);
      const blocked = limit > 0 ? used >= limit : false;
      return { blocked, used, limit };
    },
    [planSummary]
  );

  const lessonLimit = getLimitState("lesson");
  const quizLimit = getLimitState("quiz");
  const flashcardLimit = getLimitState("flashcard");

  const ensureLessonSession = useCallback(() => {
    if (lessonSessionId) return lessonSessionId;
    const sid = sessionId || createSessionId();
    if (onLessonSessionChange) {
      onLessonSessionChange(sid);
    }
    return sid;
  }, [lessonSessionId, onLessonSessionChange, sessionId]);

  const setCardLoading = (cardId, value) => {
    setCardActionLoading((prev) => ({
      ...prev,
      [cardId]: value,
    }));
  };

  const loadLessonCards = useCallback(
    async (lessonPlanId) => {
      if (!lessonPlanId) {
        setCards([]);
        return;
      }

      try {
        const res = await apiFetch(`/lesson-plan/${lessonPlanId}/cards`);
        if (!res.ok) {
          setCards([]);
          return;
        }

        const data = await res.json();
        const items = Array.isArray(data?.cards) ? data.cards : [];
        setCards(items);
        if (items.length > 0 && onResultReady) {
          onResultReady();
        }
      } catch (err) {
        console.error("Failed to load lesson cards", err);
        setCards([]);
      }
    },
    [onResultReady]
  );

  const loadArtifact = useCallback(async (artifactId, explicitCardId = null) => {
    if (!artifactId) return;

    try {
      const res = await apiFetch(`/artifacts/${artifactId}`);
      if (!res.ok) return;
      const data = await res.json();
      const artifact = data?.artifact;
      if (!artifact) return;
      const cardId = explicitCardId || artifact.card_id;
      if (!cardId) return;

      setArtifactByCard((prev) => ({
        ...prev,
        [cardId]: artifact,
      }));

      setArtifactMetaByCard((prev) => {
        if (prev[cardId]) return prev;
        const tags = Array.isArray(artifact.tags)
          ? artifact.tags.join(", ")
          : typeof artifact.tags === "string"
            ? artifact.tags
            : "";
        return {
          ...prev,
          [cardId]: {
            title: artifact.title || "",
            tags,
          },
        };
      });
    } catch (err) {
      console.error("Failed to load artifact", err);
    }
  }, []);

  const loadLessonForSession = useCallback(
    async (sid) => {
      if (!sid) return;
      try {
        const planRes = await apiFetch(`/lesson-plan?session_id=${encodeURIComponent(sid)}`);

        if (planRes.ok) {
          const planData = await planRes.json();
          const hasPlan = planData && Array.isArray(planData.steps) && planData.steps.length > 0;
          setPlan(hasPlan ? planData : null);
          setArtifactByCard({});
          setArtifactMetaByCard({});
          if (planData?.lesson_plan_id) {
            await loadLessonCards(planData.lesson_plan_id);
          } else if (hasPlan) {
            setCards([]);
          }
          if (hasPlan && onResultReady) {
            onResultReady();
          }
          if (planData?.chapter) {
            setChapter(planData.chapter);
          }
        } else if (planRes.status === 404) {
          setPlan(null);
          setCards([]);
        }
      } catch (err) {
        console.error("Failed to load lesson session", err);
      }
    },
    [loadLessonCards, onResultReady]
  );

  const runGeneratePlan = async ({ reuseSession = false } = {}) => {
    if (lessonLimit.blocked) {
      setError(
        `Lesson generation limit reached (${lessonLimit.used}/${lessonLimit.limit}). Upgrade plan to continue.`
      );
      return;
    }

    const selectedChapter = (currentContextLabel || defaultChapter || chapter || "").trim();
    if (!selectedChapter) {
      setError("Select content in Knowledge Base before generating a lesson plan.");
      return;
    }

    setError("");
    setLoadingPhase(0);
    setLoading(true);

    let sid;
    if (reuseSession) {
      sid = lessonSessionId || ensureLessonSession();
      if (!sid) {
        setLoading(false);
        return;
      }
      const confirmed = window.confirm(
        "This will overwrite the current lesson plan in the same session. Continue?"
      );
      if (!confirmed) {
        setLoading(false);
        return;
      }
    } else {
      sid = createSessionId();
      onLessonSessionChange?.(sid);
    }

    try {
      const res = await apiFetch("/lesson-plan/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sid,
          chapter: selectedChapter,
          lesson_context: lessonContext.trim() || undefined,
        }),
      });

      if (!res.ok) {
        setError(await parseApiError(res, "Failed to generate lesson plan."));
        return;
      }

      const data = await res.json();
      setPlan(data);
      setArtifactByCard({});
      setArtifactMetaByCard({});
      setExpandedSteps({});
      if (data?.lesson_plan_id) {
        await loadLessonCards(data.lesson_plan_id);
      }
      if (onResultReady) {
        onResultReady();
      }
      if (onLessonSessionsChange) {
        await onLessonSessionsChange();
      }
    } catch (err) {
      console.error("Failed to generate lesson plan", err);
      setError("Failed to generate lesson plan.");
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePlan = () => runGeneratePlan({ reuseSession: false });
  const handleRegeneratePlan = () => runGeneratePlan({ reuseSession: true });

  const handleCompleteCard = async (cardId) => {
    if (!plan?.lesson_plan_id || !cardId) return;

    setCardLoading(cardId, true);

    try {
      const res = await apiFetch(`/lesson-plan/${plan.lesson_plan_id}/cards/${cardId}/complete`, {
        method: "POST",
      });

      if (!res.ok) {
        setError(await parseApiError(res, "Failed to update lesson card progress."));
        return;
      }

      await loadLessonCards(plan.lesson_plan_id);
    } catch (err) {
      console.error("Failed to update lesson card", err);
      setError("Failed to update lesson card progress.");
    } finally {
      setCardLoading(cardId, false);
    }
  };

  const handleGenerateCardArtifact = async (cardId, type, hasPersistedCard) => {
    if (!cardId || !hasPersistedCard) {
      setError("Save or regenerate this lesson plan before creating quiz/flashcards for its cards.");
      return;
    }

    const endpoint =
      type === "quiz" ? `/cards/${cardId}/quiz/generate` : `/cards/${cardId}/flashcards/generate`;

    setCardLoading(cardId, true);
    setError("");

    try {
      const res = await apiFetch(endpoint, { method: "POST" });
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        setError(await parseApiError(res, "Failed to generate artifact for this card."));
        return;
      }

      if (data?.artifact_id) {
        await loadArtifact(data.artifact_id, cardId);
      } else {
        setError("Artifact generation succeeded but no artifact ID was returned.");
      }
    } catch (err) {
      console.error("Failed to generate card artifact", err);
      setError("Failed to generate card artifact.");
    } finally {
      setCardLoading(cardId, false);
    }
  };

  const handleSaveArtifactMeta = async (cardId) => {
    const artifact = artifactByCard[cardId];
    if (!artifact?.artifact_id) return;

    const meta = artifactMetaByCard[cardId] || { title: "", tags: "" };
    const formData = new FormData();
    if (meta.title?.trim()) {
      formData.append("title", meta.title.trim());
    }
    if (meta.tags?.trim()) {
      formData.append("tags", meta.tags.trim());
    }

    setCardLoading(cardId, true);
    try {
      const res = await apiFetch(`/artifacts/${artifact.artifact_id}/save`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        setError(await parseApiError(res, "Failed to save artifact metadata."));
        return;
      }
      await loadArtifact(artifact.artifact_id, cardId);
    } catch (err) {
      console.error("Failed to save artifact metadata", err);
      setError("Failed to save artifact metadata.");
    } finally {
      setCardLoading(cardId, false);
    }
  };

  const toggleExpandStep = (stepId) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [stepId]: !prev[stepId],
    }));
  };

  useEffect(() => {
    setChapter(defaultChapter || "");
  }, [defaultChapter]);

  useEffect(() => {
    if (lessonSessionId) {
      loadLessonForSession(lessonSessionId);
    }
  }, [lessonSessionId, loadLessonForSession]);

  useEffect(() => {
    if (!loading) return undefined;
    const timer = setInterval(() => {
      setLoadingPhase((prev) => (prev + 1) % GENERATE_PHASES.length);
    }, 2400);
    return () => clearInterval(timer);
  }, [loading]);

  const chapterLabel = useMemo(() => plan?.chapter || chapter || "Selected chapter", [chapter, plan]);

  return (
    <div className="workspace-panel lesson-panel">
      <div className="workspace-panel__header">
        <div>
          <div className="workspace-panel__eyebrow">
            <FiBookOpen />
            <span>Lessons</span>
          </div>
          <h3>Contextual lesson plans</h3>
          <p>Generate and save lesson plans using your selected Knowledge Base content.</p>
        </div>
        {!isContextViewerVisible && (
          <button
            type="button"
            className={`status-pill status-pill--button workspace-context-pill ${currentContextLabel ? "status-pill--accent" : ""}`}
            onClick={() => hasLinkedContent && onOpenContext && onOpenContext()}
            disabled={!hasLinkedContent}
            title={hasLinkedContent ? "Show source viewer" : "Select a file in Knowledge Base to enable preview"}
          >
            <FiBookOpen />
            <span className="workspace-context-pill__text">
              {currentContextLabel ? `Current Context: ${currentContextLabel}` : "Current Context: Not selected"}
            </span>
          </button>
        )}
      </div>

      <section className="panel-card panel-card--stretch">
        <div className="lesson-toolbar">
          <div className="lesson-toolbar__actions">
            <button
              type="button"
              className="primary-button"
              onClick={handleGeneratePlan}
              disabled={loading}
            >
              <FiRefreshCw />
              <span>{loading ? "Creating Lesson Plan..." : "New Lesson Plan"}</span>
            </button>
            {Boolean(lessonSessionId && plan) && (
              <button
                type="button"
                className="secondary-button"
                onClick={handleRegeneratePlan}
                disabled={loading}
              >
                <FiRefreshCw />
                <span>{loading ? "Regenerating..." : "Regenerate Plan"}</span>
              </button>
            )}
          </div>

          <div className="lesson-toolbar__context">
            <label htmlFor="lesson-plan-context">Optional lesson focus</label>
            <input
              id="lesson-plan-context"
              type="text"
              className="lesson-context-input"
              placeholder="Example: exam-oriented, simple explanations, real-life examples"
              value={lessonContext}
              onChange={(event) => setLessonContext(event.target.value)}
            />
          </div>
        </div>

        {loading && <div className="stream-status"><span>{GENERATE_PHASES[loadingPhase]}</span></div>}

        {lessonLimit.blocked && (
          <div className="sidebar-note">
            Lesson generation limit reached ({lessonLimit.used}/{lessonLimit.limit}).
          </div>
        )}

        {error && <div className="sidebar-note">{error}</div>}

        {!plan && !loading && (
          <div className="empty-state panel-empty-state">
            <FiBookOpen />
            <h4>No lesson plan generated</h4>
            <p>Create a lesson plan for the selected chapter to start guided study.</p>
          </div>
        )}

        {plan && (
          <>
            <div className="workspace-sidebar__section-title">
              <FiBookOpen />
              <span>{chapterLabel}</span>
            </div>

            <div className="lesson-steps lesson-steps--full">
              {(cards.length > 0 ? cards : plan.steps || []).map((stepLike, idx) => {
                const card = cards.length > 0
                  ? stepLike
                  : {
                      card_id: idx + 1,
                      order: stepLike.id || idx + 1,
                      title: stepLike.title,
                      card_type: stepLike.type,
                      content: stepLike.content,
                      status: stepLike.status,
                    };
                const cardId = card.card_id;
                const isCurrent = card.status !== "completed";
                const isExpanded = expandedSteps[cardId] ?? true;
                const artifact = artifactByCard[cardId] || null;
                const artifactMeta = artifactMetaByCard[cardId] || { title: "", tags: "" };
                const isBusy = Boolean(cardActionLoading[cardId]);
                const hasPersistedCard = cards.length > 0;

                return (
                  <div key={cardId} className={`lesson-step ${isCurrent ? "lesson-step--current" : ""}`}>
                    <div className="lesson-step__header">
                      <button
                        type="button"
                        className="lesson-step__toggle"
                        onClick={() => toggleExpandStep(cardId)}
                        aria-expanded={isExpanded}
                      >
                        {isExpanded ? <FiChevronUp /> : <FiChevronDown />}
                        <div className="lesson-step__title">
                          <strong>{card.order || cardId}. {card.title}</strong>
                        </div>
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => handleCompleteCard(cardId)}
                        title="Mark this card as completed"
                        disabled={isBusy || card.status === "completed" || !plan?.lesson_plan_id || !hasPersistedCard}
                      >
                        <FiCheckSquare />
                        <span>{card.status === "completed" ? "Completed" : "Complete"}</span>
                      </button>
                    </div>
                    {isExpanded && (
                      <div className="lesson-step__content">
                        {card.content && <p>{card.content}</p>}
                        {!card.content && (
                          <p className="sidebar-note">No detailed content available for this step.</p>
                        )}

                        <div className="lesson-card-actions">
                          <button
                            type="button"
                            className="secondary-button"
                            onClick={() => handleGenerateCardArtifact(cardId, "quiz", hasPersistedCard)}
                            disabled={isBusy || !plan?.lesson_plan_id || quizLimit.blocked || !hasPersistedCard}
                          >
                            <FiZap />
                            <span>Generate Quiz</span>
                          </button>
                          <button
                            type="button"
                            className="secondary-button"
                            onClick={() => handleGenerateCardArtifact(cardId, "flashcard", hasPersistedCard)}
                            disabled={isBusy || !plan?.lesson_plan_id || flashcardLimit.blocked || !hasPersistedCard}
                          >
                            <FiLayers />
                            <span>Generate Flashcards</span>
                          </button>
                          {artifact?.artifact_id && (
                            <button
                              type="button"
                              className="secondary-button"
                              onClick={() => loadArtifact(artifact.artifact_id, cardId)}
                              disabled={isBusy}
                            >
                              <FiRefreshCw />
                              <span>Reload Artifact</span>
                            </button>
                          )}
                        </div>

                        {!hasPersistedCard && (
                          <div className="sidebar-note">
                            Regenerate this lesson plan to enable quiz and flashcard generation for each card.
                          </div>
                        )}

                        {artifact && (
                          <div className="lesson-artifact-panel">
                            <div className="lesson-artifact-header">
                              <strong>{artifact.artifact_type} · #{artifact.artifact_id}</strong>
                            </div>

                            {artifact.artifact_type === "QUIZ" && Array.isArray(artifact.payload?.quiz) && (
                              <div className="lesson-artifact-body">
                                {artifact.payload.quiz.slice(0, 3).map((q) => (
                                  <p key={q.id || q.question}>{q.question}</p>
                                ))}
                              </div>
                            )}

                            {artifact.artifact_type === "FLASHCARD" && Array.isArray(artifact.payload?.flashcards) && (
                              <div className="lesson-artifact-body">
                                {artifact.payload.flashcards.slice(0, 3).map((f, fIdx) => (
                                  <p key={`${artifact.artifact_id}-${fIdx}`}>{f.question}</p>
                                ))}
                              </div>
                            )}

                            <div className="lesson-artifact-meta">
                              <input
                                type="text"
                                placeholder="Artifact title"
                                value={artifactMeta.title}
                                onChange={(event) =>
                                  setArtifactMetaByCard((prev) => ({
                                    ...prev,
                                    [cardId]: {
                                      ...(prev[cardId] || {}),
                                      title: event.target.value,
                                    },
                                  }))
                                }
                              />
                              <input
                                type="text"
                                placeholder="tags (comma-separated)"
                                value={artifactMeta.tags}
                                onChange={(event) =>
                                  setArtifactMetaByCard((prev) => ({
                                    ...prev,
                                    [cardId]: {
                                      ...(prev[cardId] || {}),
                                      tags: event.target.value,
                                    },
                                  }))
                                }
                              />
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() => handleSaveArtifactMeta(cardId)}
                                disabled={isBusy}
                              >
                                <FiSave />
                                <span>Save Artifact</span>
                              </button>
                            </div>
                          </div>
                        )}

                        {(quizLimit.blocked || flashcardLimit.blocked) && (
                          <div className="sidebar-note">
                            {quizLimit.blocked && `Quiz limit reached (${quizLimit.used}/${quizLimit.limit}). `}
                            {flashcardLimit.blocked &&
                              `Flashcard limit reached (${flashcardLimit.used}/${flashcardLimit.limit}).`}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {cards.length > 0 && cards.every((card) => card.status === "completed") && (
              <div className="status-pill status-pill--accent">
                <FiCheckSquare />
                <span>Lesson cards completed</span>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
