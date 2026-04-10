import React, { useMemo, useState } from "react";
import { FiBookOpen, FiCheck, FiEdit, FiExternalLink, FiSave } from "react-icons/fi";
import { apiFetch, parseApiError } from "../services/api";
import MessageContent from "./MessageContent";

export function looksLikeStructuredSummary(content = "") {
  const text = String(content || "");
  return /^##\s+/m.test(text) && /###\s+(Overview|Key Points|Section Notes|Final Takeaways)/i.test(text);
}

function normalizeHeading(value = "") {
  return String(value || "").replace(/[📘📒📝]/g, "").trim();
}

function parseStructuredSummary(content = "") {
  const text = String(content || "").trim();
  const titleMatch = text.match(/^##\s+(.+)$/m);
  const title = normalizeHeading(titleMatch?.[1] || "Summary Notes") || "Summary Notes";

  const sectionMatches = [...text.matchAll(/^###\s+(.+)$/gm)];
  if (!sectionMatches.length) {
    return { title, sections: [{ heading: "Notes", body: text.replace(/^##\s+.+$/m, "").trim() || text }] };
  }

  const sections = sectionMatches.map((match, index) => {
    const start = match.index + match[0].length;
    const end = index + 1 < sectionMatches.length ? sectionMatches[index + 1].index : text.length;
    return {
      heading: normalizeHeading(match[1]) || `Section ${index + 1}`,
      body: text.slice(start, end).trim(),
    };
  }).filter((item) => item.body);

  return { title, sections };
}

export default function SummaryViewer({
  content = "",
  sourceQuery = "",
  sessionId = null,
  selectedContent = null,
  onSave = null,
  onOpenNotes = null,
}) {
  const parsed = useMemo(() => parseStructuredSummary(content), [content]);
  const [isEditing, setIsEditing] = useState(false);
  const [draftContent, setDraftContent] = useState(String(content || ""));
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });

  if (!looksLikeStructuredSummary(content)) {
    return <MessageContent content={content} />;
  }

  const handleSave = async () => {
    // Truncate title to 200 chars to match backend schema
    const safeTitle = String(parsed.title || "").slice(0, 200);
    const payload = {
      title: safeTitle,
      content: String(draftContent || content || "").trim(),
      source_query: sourceQuery,
      session_id: sessionId,
      selected_content: selectedContent,
    };

    if (!payload.content) {
      setSaveState({ status: "error", message: "Add some note content before saving." });
      return;
    }

    setSaveState({ status: "saving", message: "Saving…" });

    try {
      if (typeof onSave === "function") {
        await onSave(payload);
      } else {
        const res = await apiFetch("/notes/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          throw new Error(await parseApiError(res, "Could not save this note."));
        }
      }

      window.dispatchEvent(new CustomEvent("notes:updated"));
      setSaveState({ status: "success", message: "Saved to Notes." });
      if (typeof onOpenNotes === "function") {
        onOpenNotes();
      }
    } catch (err) {
      setSaveState({ status: "error", message: err?.message || "Could not save this note." });
    }
  };

  return (
    <div className="summary-viewer" data-testid="summary-viewer">
      <div className="summary-viewer__header">
        <div>
          <div className="workspace-panel__eyebrow">
            <FiBookOpen />
            <span>Structured summary</span>
          </div>
          <h4>{parsed.title}</h4>
        </div>
        <div className="summary-viewer__actions">
          <button type="button" className="secondary-button" onClick={() => setIsEditing((prev) => !prev)}>
            <FiEdit />
            <span>{isEditing ? "Preview" : "Edit notes"}</span>
          </button>
          <button type="button" className="secondary-button" onClick={handleSave} disabled={saveState.status === "saving"}>
            {saveState.status === "success" ? <FiCheck /> : <FiSave />}
            <span>{saveState.status === "saving" ? "Saving..." : "Save to Notes"}</span>
          </button>
          {typeof onOpenNotes === "function" ? (
            <button type="button" className="icon-button icon-button--ghost" onClick={onOpenNotes} title="Open Notes" aria-label="Open Notes">
              <FiExternalLink />
            </button>
          ) : null}
        </div>
      </div>

      {isEditing ? (
        <textarea
          className="summary-viewer__editor"
          value={draftContent}
          onChange={(event) => setDraftContent(event.target.value)}
          aria-label="Summary note editor"
        />
      ) : (
        <div className="summary-viewer__sections">
          {parsed.sections.map((section) => (
            <section key={`${parsed.title}-${section.heading}`} className="summary-viewer__section">
              <h5>{section.heading}</h5>
              <MessageContent content={section.body} />
            </section>
          ))}
        </div>
      )}

      {saveState.message ? (
        <div className={`summary-viewer__status summary-viewer__status--${saveState.status === "error" ? "error" : "info"}`} role="status">
          {saveState.message}
        </div>
      ) : null}
    </div>
  );
}
