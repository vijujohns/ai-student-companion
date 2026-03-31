import React, { useCallback, useEffect, useState } from "react";
import { FiBookOpen, FiLayers, FiRefreshCw, FiSave } from "react-icons/fi";
import { apiFetch, parseApiError } from "../services/api";

function createSessionId() {
  return `${Date.now()}`;
}

const GENERATE_PHASES = [
  "Reading the lesson card...",
  "Extracting revision prompts...",
  "Shaping concise flashcards...",
  "Saving the card set for review...",
];

export default function FlashcardPanel({
  sessionId,
  flashcardSessionId,
  onFlashcardSessionChange,
  onFlashcardSessionsChange,
  planSummary = null,
  defaultChapter = "",
  selectedClass = null,
  selectedSubject = null,
  selectedFolder = null,
  currentContextLabel = null,
  hasLinkedContent = false,
  isContextViewerVisible = false,
  onOpenContext = null,
  onResultReady = null,
}) {
  const [flashcardContext, setFlashcardContext] = useState("");
  const [generationMode, setGenerationMode] = useState("context");
  const [lessonSourceSessions, setLessonSourceSessions] = useState([]);
  const [lessonSourceSessionId, setLessonSourceSessionId] = useState("");
  const [lessonPlanId, setLessonPlanId] = useState(null);
  const [lessonCards, setLessonCards] = useState([]);
  const [selectedCardId, setSelectedCardId] = useState("");
  const [artifact, setArtifact] = useState(null);
  const [meta, setMeta] = useState({ title: "", tags: "" });
  const [loading, setLoading] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState(0);
  const [error, setError] = useState("");

  const flashcardUsage = Number(planSummary?.usage?.flashcard_count || 0);
  const flashcardLimit = Number(planSummary?.limits?.flashcard_count || 0);
  const flashcardBlocked = flashcardLimit > 0 ? flashcardUsage >= flashcardLimit : false;
  const selectedContext = (currentContextLabel || defaultChapter || "").trim();

  const ensureSession = useCallback(() => {
    if (flashcardSessionId) return flashcardSessionId;
    const sid = sessionId || createSessionId();
    onFlashcardSessionChange?.(sid);
    return sid;
  }, [flashcardSessionId, onFlashcardSessionChange, sessionId]);

  const resetArtifactState = useCallback(() => {
    setArtifact(null);
    setMeta({ title: "", tags: "" });
  }, []);

  const loadCardsForSession = useCallback(async (sid) => {
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
      console.error("Failed to load cards for flashcards", err);
      setLessonPlanId(null);
      setLessonCards([]);
      setSelectedCardId("");
    }
  }, []);

  const loadArtifact = useCallback(
    async (artifactId) => {
      if (!artifactId) {
        resetArtifactState();
        return;
      }
      try {
        const res = await apiFetch(`/artifacts/${artifactId}`);
        if (!res.ok) {
          resetArtifactState();
          return;
        }
        const data = await res.json();
        const art = data?.artifact;
        if (!art) {
          resetArtifactState();
          return;
        }
        setArtifact(art);
        setMeta({
          title: art.title || "",
          tags: Array.isArray(art.tags)
            ? art.tags.join(", ")
            : typeof art.tags === "string"
              ? art.tags
              : "",
        });
        onResultReady?.();
      } catch (err) {
        console.error("Failed to load artifact", err);
        resetArtifactState();
      }
    },
    [onResultReady, resetArtifactState]
  );

  const loadLatestArtifactForSession = useCallback(
    async (sid) => {
      if (!sid) {
        resetArtifactState();
        return;
      }

      try {
        const res = await apiFetch(`/flashcards/latest?session_id=${encodeURIComponent(sid)}`);
        if (!res.ok) {
          resetArtifactState();
          return;
        }
        const data = await res.json();
        if (!data?.artifact || data?.error) {
          resetArtifactState();
          return;
        }
        setArtifact(data.artifact);
        setMeta({
          title: data.artifact.title || "",
          tags: Array.isArray(data.artifact.tags)
            ? data.artifact.tags.join(", ")
            : typeof data.artifact.tags === "string"
              ? data.artifact.tags
              : "",
        });
        onResultReady?.();
      } catch (err) {
        console.error("Failed to load latest flashcards", err);
        resetArtifactState();
      }
    },
    [onResultReady, resetArtifactState]
  );

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
      console.error("Failed to load lesson source sessions for flashcards", err);
      setLessonSourceSessions([]);
    }
  }, []);

  const runGenerateFlashcards = async ({ reuseSession = false } = {}) => {
    if (flashcardBlocked) {
      setError(`Flashcard limit reached (${flashcardUsage}/${flashcardLimit}). Upgrade plan to continue.`);
      return;
    }

    setLoading(true);
    setLoadingPhase(0);
    setError("");

    let sid;
    if (reuseSession) {
      sid = flashcardSessionId || ensureSession();
      if (!sid) {
        setLoading(false);
        return;
      }
      const confirmed = window.confirm(
        "This will overwrite the current cards in the same session. Continue?"
      );
      if (!confirmed) {
        setLoading(false);
        return;
      }
    } else {
      sid = createSessionId();
      onFlashcardSessionChange?.(sid);
    }

    try {
      if (generationMode === "context") {
        if (!selectedClass || !selectedSubject || !selectedFolder) {
          setError("Select Class, Subject, and Folder before generating flashcards from file context.");
          return;
        }

        const chapterHint = String(currentContextLabel || defaultChapter || "").trim() || undefined;
        const res = await apiFetch("/flashcards/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            class_name: selectedClass,
            subject: selectedSubject,
            content_type: selectedFolder,
            chapter: chapterHint,
            num_cards: 10,
            session_id: sid,
          }),
        });
        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
          setError(await parseApiError(res, "Failed to generate flashcards from selected file context."));
          return;
        }

        const generatedCards = Array.isArray(data?.flashcards) ? data.flashcards : [];
        setArtifact({
          artifact_id: null,
          title: chapterHint ? `Flashcards - ${chapterHint}` : "Flashcards",
          tags: [],
          payload: { flashcards: generatedCards },
        });
        setMeta({ title: chapterHint ? `Flashcards - ${chapterHint}` : "Flashcards", tags: "" });
        onResultReady?.();
      } else {
        const selectedLessonSession = lessonSourceSessions.find(
          (session) => String(session?.id || "") === String(lessonSourceSessionId || "")
        );
        if (!selectedLessonSession) {
          setError("Select a lesson session before generating flashcards from lesson context.");
          return;
        }

        const activeCardId = selectedCardId || (lessonCards[0] ? String(lessonCards[0].card_id) : "");
        if (!activeCardId) {
          setError("No lesson cards found in selected session. Generate a lesson plan first.");
          return;
        }

        const res = await apiFetch(`/cards/${activeCardId}/flashcards/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ context: flashcardContext.trim() || undefined }),
        });
        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
          setError(await parseApiError(res, "Failed to generate flashcards from selected card."));
          return;
        }

        if (data?.artifact_id) {
          await loadArtifact(data.artifact_id);
        }
      }

      await onFlashcardSessionsChange?.();
    } catch (err) {
      console.error("Failed to generate flashcards", err);
      setError("Failed to generate flashcards.");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateFlashcards = () => runGenerateFlashcards({ reuseSession: false });
  const handleRegenerateFlashcards = () => runGenerateFlashcards({ reuseSession: true });

  const handleSaveArtifact = async () => {
    if (!artifact?.artifact_id) return;

    const formData = new FormData();
    if (meta.title?.trim()) formData.append("title", meta.title.trim());
    if (meta.tags?.trim()) formData.append("tags", meta.tags.trim());

    setLoading(true);
    setError("");

    try {
      const res = await apiFetch(`/artifacts/${artifact.artifact_id}/save`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        setError(await parseApiError(res, "Failed to save artifact metadata."));
        return;
      }
      await loadArtifact(artifact.artifact_id);
    } catch (err) {
      console.error("Failed to save flashcard artifact", err);
      setError("Failed to save artifact metadata.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!flashcardSessionId && sessionId) {
      onFlashcardSessionChange?.(sessionId);
    }
  }, [flashcardSessionId, onFlashcardSessionChange, sessionId]);

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
    if (!flashcardSessionId) {
      resetArtifactState();
      return;
    }

    loadLatestArtifactForSession(flashcardSessionId);
  }, [flashcardSessionId, loadLatestArtifactForSession, resetArtifactState]);

  useEffect(() => {
    if (!lessonSourceSessionId) {
      setLessonPlanId(null);
      setLessonCards([]);
      setSelectedCardId("");
      return;
    }

    loadCardsForSession(lessonSourceSessionId);
  }, [lessonSourceSessionId, loadCardsForSession]);

  useEffect(() => {
    if (!loading) return undefined;
    const timer = setInterval(() => {
      setLoadingPhase((prev) => (prev + 1) % GENERATE_PHASES.length);
    }, 2200);
    return () => clearInterval(timer);
  }, [loading]);

  return (
    <div className="workspace-panel quiz-panel">
      <div className="workspace-panel__header">
        <div>
          <div className="workspace-panel__eyebrow">
            <FiLayers />
            <span>Flashcards</span>
          </div>
          <h3>Lesson-based flashcards</h3>
          <p>Generate revision cards from lesson cards, with history managed in the sidebar.</p>
        </div>
        {!isContextViewerVisible && (
          <button
            type="button"
            className={`status-pill status-pill--button workspace-context-pill ${selectedContext ? "status-pill--accent" : ""}`}
            onClick={() => hasLinkedContent && onOpenContext && onOpenContext()}
            disabled={!hasLinkedContent}
            title={hasLinkedContent ? "Show source viewer" : "Select a file in Knowledge Base to enable preview"}
          >
            <FiBookOpen />
            <span className="workspace-context-pill__text">
              {selectedContext ? `Current Context: ${selectedContext}` : "Current Context: Not selected"}
            </span>
          </button>
        )}
      </div>

      <div className="panel-grid panel-grid--split">
        <section className="panel-card">
          <div className="lesson-toolbar">
            <div className="lesson-toolbar__actions">
              <button
                type="button"
                className="primary-button"
                onClick={handleGenerateFlashcards}
                disabled={loading || flashcardBlocked}
              >
                <span>{loading ? "Creating Flashcards..." : "New Flashcards"}</span>
              </button>
              {Boolean(flashcardSessionId) && (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={handleRegenerateFlashcards}
                  disabled={loading || flashcardBlocked}
                >
                  <FiRefreshCw />
                  <span>{loading ? "Regenerating..." : "Regenerate Flashcards"}</span>
                </button>
              )}
            </div>

            <div className="quiz-source-picker">
              <div className="workspace-sidebar__section-title">
                <FiLayers />
                <span>Choose context for generating flashcards</span>
              </div>
              <div className="quiz-source-toggle" role="group" aria-label="Flashcard source selector">
                <button
                  type="button"
                  className={`secondary-button ${generationMode === "context" ? "quiz-source-toggle__option--active" : ""}`}
                  onClick={() => setGenerationMode("context")}
                >
                  File Context
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

            <div className="lesson-toolbar__context">
              <label htmlFor="flashcard-context">Optional flashcard focus</label>
              <input
                id="flashcard-context"
                type="text"
                className="lesson-context-input"
                placeholder="Example: one-line revision, definitions only, memory hooks"
                value={flashcardContext}
                onChange={(event) => setFlashcardContext(event.target.value)}
              />
            </div>
          </div>

          {loading && <div className="stream-status"><span>{GENERATE_PHASES[loadingPhase]}</span></div>}

          {flashcardBlocked && (
            <div className="sidebar-note">
              Flashcard generation limit reached ({flashcardUsage}/{flashcardLimit}).
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
                <FiLayers />
                <select
                  value={selectedCardId || ""}
                  onChange={(event) => setSelectedCardId(event.target.value || "")}
                  disabled={!lessonSourceSessionId || lessonCards.length === 0}
                >
                  <option value="">Any card in selected session (optional)</option>
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
                <div className="sidebar-note">No lesson plan found for selected session. Choose another session.</div>
              )}
            </div>
          )}

          {error && <div className="sidebar-note">{error}</div>}
        </section>

        <section className="panel-card panel-card--stretch">
          {!artifact && (
            <div className="empty-state panel-empty-state">
              <FiLayers />
              <h4>No flashcards generated</h4>
              <p>Use the context selector above to generate flashcards from file context or lesson card context.</p>
            </div>
          )}

          {artifact && (
            <>
              <div className="workspace-sidebar__section-title">
                <FiLayers />
                <span>{artifact.artifact_id ? `Artifact #${artifact.artifact_id}` : "Generated Flashcards"}</span>
              </div>

              {(() => {
                const cardCount = artifact.payload?.flashcards?.length || 0;
                return (
                  <div className="workspace-pill-row">
                    <span className="status-pill status-pill--accent">
                      <FiLayers />
                      <span>{cardCount} flashcard{cardCount !== 1 ? "s" : ""} generated</span>
                    </span>
                  </div>
                );
              })()}

              <div className="flashcard-grid">
                {(artifact.payload?.flashcards || []).map((item, index) => (
                  <div key={`${artifact.artifact_id}-${index}`} className="flashcard-card">
                    <strong>Q. {item.question || `Card ${index + 1}`}</strong>
                    <p>{item.answer || "No answer available."}</p>
                  </div>
                ))}
              </div>

              {artifact.artifact_id && (
                <div className="lesson-artifact-meta">
                  <input
                    type="text"
                    placeholder="Artifact title"
                    value={meta.title}
                    onChange={(event) => setMeta((prev) => ({ ...prev, title: event.target.value }))}
                  />
                  <input
                    type="text"
                    placeholder="tags (comma-separated)"
                    value={meta.tags}
                    onChange={(event) => setMeta((prev) => ({ ...prev, tags: event.target.value }))}
                  />
                  <button type="button" className="secondary-button" onClick={handleSaveArtifact} disabled={loading}>
                    <FiSave />
                    <span>Save Artifact</span>
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => loadArtifact(artifact.artifact_id)}
                    disabled={loading}
                  >
                    <FiRefreshCw />
                    <span>Reload Artifact</span>
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
