import React, { useCallback, useEffect, useMemo, useState } from "react";
import { FiBookOpen, FiRefreshCw, FiSave, FiTrash2 } from "react-icons/fi";
import { apiFetch, parseApiError } from "../services/api";
import MessageContent from "./MessageContent";

function formatNoteDate(value) {
  if (!value) return "Updated just now";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return `Updated ${parsed.toLocaleDateString([], { dateStyle: "medium" })}`;
}

export default function NotesPanel({ isActive = true }) {
  const [notes, setNotes] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftContent, setDraftContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectedNote = useMemo(
    () => notes.find((item) => String(item.id) === String(selectedId)) || null,
    [notes, selectedId],
  );

  const syncDrafts = useCallback((note) => {
    setDraftTitle(String(note?.title || ""));
    setDraftContent(String(note?.content || ""));
  }, []);

  const loadNotes = useCallback(async () => {
    if (!isActive) return;
    setLoading(true);
    setError("");

    try {
      const res = await apiFetch("/notes", { method: "GET" });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not load your notes."));
      }

      const payload = await res.json();
      const nextNotes = Array.isArray(payload?.notes) ? payload.notes : [];
      setNotes(nextNotes);

      if (nextNotes.length === 0) {
        setSelectedId(null);
        syncDrafts(null);
        return;
      }

      const stillExists = nextNotes.some((item) => String(item.id) === String(selectedId));
      const nextSelected = stillExists ? nextNotes.find((item) => String(item.id) === String(selectedId)) : nextNotes[0];
      setSelectedId(nextSelected?.id ?? null);
      syncDrafts(nextSelected);
    } catch (err) {
      setError(err?.message || "Could not load your notes.");
    } finally {
      setLoading(false);
    }
  }, [isActive, selectedId, syncDrafts]);

  useEffect(() => {
    loadNotes();
  }, [loadNotes]);

  useEffect(() => {
    const handleNotesUpdated = () => {
      if (isActive) {
        loadNotes();
      }
    };
    window.addEventListener("notes:updated", handleNotesUpdated);
    return () => window.removeEventListener("notes:updated", handleNotesUpdated);
  }, [isActive, loadNotes]);

  const handleSelectNote = (note) => {
    setSelectedId(note.id);
    syncDrafts(note);
    setNotice("");
  };

  const handleSave = async () => {
    if (!selectedNote) return;
    setSaving(true);
    setError("");
    setNotice("");

    try {
      const res = await apiFetch(`/notes/${encodeURIComponent(selectedNote.id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: draftTitle, content: draftContent }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not save your note changes."));
      }

      setNotice("Note updated.");
      window.dispatchEvent(new CustomEvent("notes:updated"));
      await loadNotes();
    } catch (err) {
      setError(err?.message || "Could not save your note changes.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedNote) return;
    setSaving(true);
    setError("");
    setNotice("");

    try {
      const res = await apiFetch(`/notes/${encodeURIComponent(selectedNote.id)}`, { method: "DELETE" });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not delete this note."));
      }

      setNotice("Note deleted.");
      window.dispatchEvent(new CustomEvent("notes:updated"));
      await loadNotes();
    } catch (err) {
      setError(err?.message || "Could not delete this note.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="workspace-panel progress-panel notes-panel">
      <div className="progress-panel__body">
        <section className="progress-section">
          <div className="progress-toolbar-card notes-panel__toolbar">
            <div className="progress-toolbar-card__header">
              <div>
                <div className="progress-section__title">
                  <FiBookOpen />
                  <span>Saved notes</span>
                </div>
                <p className="progress-toolbar-card__copy">
                  Save structured summaries from chat, refine them here, and keep revision notes in one workspace.
                </p>
              </div>
              <div className="progress-toolbar__actions">
                <span className="progress-pill progress-pill--neutral">{notes.length} saved</span>
                <button type="button" className="secondary-button" onClick={loadNotes} disabled={loading}>
                  <FiRefreshCw />
                  <span>{loading ? "Refreshing..." : "Refresh"}</span>
                </button>
              </div>
            </div>
            {error ? <p className="sidebar-note" role="alert">{error}</p> : null}
            {notice ? <p className="sidebar-note" role="status">{notice}</p> : null}
          </div>
        </section>

        <section className="notes-panel__layout">
          <aside className="notes-panel__list" aria-label="Saved notes list">
            {loading && notes.length === 0 ? (
              <div className="progress-panel__loading">
                <span>Loading notes…</span>
              </div>
            ) : notes.length === 0 ? (
              <div className="progress-plan-card notes-panel__empty">
                <p className="progress-plan-card__headline">No saved notes yet.</p>
                <p className="sidebar-note">Open a structured summary in chat and use <strong>Save to Notes</strong>.</p>
              </div>
            ) : (
              notes.map((note) => (
                <button
                  key={note.id}
                  type="button"
                  className={`notes-panel__list-item ${selectedNote?.id === note.id ? "is-active" : ""}`}
                  onClick={() => handleSelectNote(note)}
                  title={note.title}
                >
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", width: "100%" }}>
                    <span style={{ fontWeight: 600, fontSize: "1rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "100%" }}>{note.title}</span>
                    <span style={{ fontSize: "0.78rem", color: "var(--text-soft)", marginTop: 2 }}>{formatNoteDate(note.updated_at)}</span>
                  </div>
                </button>
              ))
            )}
          </aside>

          <div className="notes-panel__editor-card">
            {selectedNote ? (
              <>
                <label className="progress-toolbar__field progress-toolbar__field--wide">
                  <span>Note title</span>
                  <input
                    className="progress-toolbar__input"
                    value={draftTitle}
                    onChange={(event) => setDraftTitle(event.target.value)}
                    placeholder="Enter note title"
                  />
                </label>

                <label className="progress-toolbar__field progress-toolbar__field--wide">
                  <span>Note content</span>
                  <textarea
                    className="notes-panel__editor"
                    value={draftContent}
                    onChange={(event) => setDraftContent(event.target.value)}
                    placeholder="Edit your summary notes here"
                  />
                </label>

                <div className="progress-toolbar__actions notes-panel__editor-actions">
                  <button type="button" className="secondary-button" onClick={handleSave} disabled={saving}>
                    <FiSave />
                    <span>{saving ? "Saving..." : "Save changes"}</span>
                  </button>
                  <button type="button" className="secondary-button" onClick={handleDelete} disabled={saving}>
                    <FiTrash2 />
                    <span>Delete note</span>
                  </button>
                </div>

                <div className="notes-panel__preview">
                  <div className="progress-section__title">
                    <FiBookOpen />
                    <span>Preview</span>
                  </div>
                  <MessageContent content={draftContent} />
                </div>
              </>
            ) : (
              <div className="progress-empty">
                <FiBookOpen />
                <span>Select a note to review or edit it.</span>
              </div>
            )}
          </div>
        </section>
      </div>
    </section>
  );
}
