import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FiBookOpen, FiEdit, FiEye, FiEyeOff, FiFileText, FiLink, FiSave, FiTrash2 } from "react-icons/fi";
import { apiFetch, parseApiError } from "../services/api";

function formatNoteDate(value) {
  if (!value) return "Updated just now";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return `Updated ${parsed.toLocaleDateString([], { dateStyle: "medium" })}`;
}

function escapeHtml(value = "") {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function applyInlineMarkdown(value = "") {
  let html = escapeHtml(value);
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return html;
}

function markdownToEditableHtml(markdown = "") {
  if (!String(markdown || "").trim()) {
    return "";
  }
  const lines = String(markdown || "").replace(/\r/g, "").split("\n");
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      blocks.push("<p><br></p>");
      index += 1;
      continue;
    }

    if (/^##\s+/.test(trimmed) && !/^###\s+/.test(trimmed)) {
      blocks.push(`<h2>${applyInlineMarkdown(trimmed.replace(/^##\s+/, ""))}</h2>`);
      index += 1;
      continue;
    }

    if (/^###\s+/.test(trimmed)) {
      blocks.push(`<h3>${applyInlineMarkdown(trimmed.replace(/^###\s+/, ""))}</h3>`);
      index += 1;
      continue;
    }

    if (/^>\s?/.test(trimmed)) {
      const quoteLines = [];
      while (index < lines.length && /^>\s?/.test(lines[index].trim())) {
        quoteLines.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }
      blocks.push(`<blockquote>${quoteLines.map((entry) => `<p>${applyInlineMarkdown(entry)}</p>`).join("")}</blockquote>`);
      continue;
    }

    if (/^(?:-|\*)\s+/.test(trimmed)) {
      const items = [];
      while (index < lines.length && /^(?:-|\*)\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^(?:-|\*)\s+/, ""));
        index += 1;
      }
      blocks.push(`<ul>${items.map((entry) => `<li>${applyInlineMarkdown(entry)}</li>`).join("")}</ul>`);
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s+/, ""));
        index += 1;
      }
      blocks.push(`<ol>${items.map((entry) => `<li>${applyInlineMarkdown(entry)}</li>`).join("")}</ol>`);
      continue;
    }

    const paragraphLines = [trimmed];
    index += 1;
    while (index < lines.length) {
      const nextTrimmed = lines[index].trim();
      if (!nextTrimmed || /^(##|###)\s+/.test(nextTrimmed) || /^>\s?/.test(nextTrimmed) || /^(?:-|\*)\s+/.test(nextTrimmed) || /^\d+\.\s+/.test(nextTrimmed)) {
        break;
      }
      paragraphLines.push(nextTrimmed);
      index += 1;
    }
    blocks.push(`<p>${applyInlineMarkdown(paragraphLines.join(" "))}</p>`);
  }

  return blocks.join("");
}

function serializeInlineNode(node) {
  if (!node) return "";
  if (node.nodeType === Node.TEXT_NODE) {
    return String(node.textContent || "").replace(/\u00a0/g, " ");
  }
  if (node.nodeName === "BR") return "\n";

  const children = Array.from(node.childNodes || []).map(serializeInlineNode).join("");
  switch (node.nodeName) {
    case "STRONG":
    case "B":
      return `**${children}**`;
    case "EM":
    case "I":
      return `*${children}*`;
    case "CODE":
      return `\`${children}\``;
    case "A": {
      const href = node.getAttribute?.("href") || "";
      return href ? `[${children}](${href})` : children;
    }
    default:
      return children;
  }
}

function flattenBlockText(node) {
  return serializeInlineNode(node).replace(/\n+/g, " ").replace(/[ \t]+/g, " ").trim();
}

function serializeBlockNode(node, depth = 0, listType = "") {
  if (!node) return [];

  if (node.nodeType === Node.TEXT_NODE) {
    const text = String(node.textContent || "").trim();
    return text ? [text] : [];
  }

  const tag = node.nodeName;

  if (tag === "H2") return [`## ${flattenBlockText(node)}`];
  if (tag === "H3") return [`### ${flattenBlockText(node)}`];

  if (tag === "P" || tag === "DIV") {
    const text = flattenBlockText(node);
    return text ? [text] : [""];
  }

  if (tag === "BLOCKQUOTE") {
    return Array.from(node.childNodes || [])
      .flatMap((child) => serializeBlockNode(child))
      .map((line) => (line ? `> ${line}` : ">"));
  }

  if (tag === "UL" || tag === "OL") {
    return Array.from(node.children || []).flatMap((child) => serializeBlockNode(child, depth, tag));
  }

  if (tag === "LI") {
    const indent = "  ".repeat(depth);
    const prefix = listType === "OL" ? "1." : "-";
    const nestedLines = [];
    let leadText = "";

    Array.from(node.childNodes || []).forEach((child) => {
      if (child.nodeType === Node.TEXT_NODE) {
        leadText += serializeInlineNode(child);
        return;
      }

      if (child.nodeName === "UL" || child.nodeName === "OL") {
        nestedLines.push(...serializeBlockNode(child, depth + 1));
        return;
      }

      leadText += serializeInlineNode(child);
    });

    const cleanedLead = leadText.replace(/\n+/g, " ").replace(/[ \t]+/g, " ").trim();
    const lines = cleanedLead ? [`${indent}${prefix} ${cleanedLead}`] : [];
    return [...lines, ...nestedLines];
  }

  return Array.from(node.childNodes || []).flatMap((child) => serializeBlockNode(child, depth, listType));
}

function normalizeMarkdownWhitespace(value = "") {
  return String(value || "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function serializeEditorContent(root) {
  if (!root) return "";
  const lines = Array.from(root.childNodes || []).flatMap((node) => serializeBlockNode(node));
  return normalizeMarkdownWhitespace(lines.join("\n\n"));
}

function isModKey(event) {
  return Boolean(event.metaKey || event.ctrlKey);
}

export default function NotesPanel({
  isActive = true,
  contextPillItems = [],
  hasLinkedContent = false,
  hasViewerContent = false,
  isContextViewerVisible = false,
  onToggleViewer = () => {},
  onOpenContext = () => {},
}) {
  const [notes, setNotes] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftContent, setDraftContent] = useState("");
  const [editorSeed, setEditorSeed] = useState(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [linkDraft, setLinkDraft] = useState({ text: "", url: "" });
  const [showLinkForm, setShowLinkForm] = useState(false);
  const editorRef = useRef(null);

  const selectedNote = useMemo(
    () => notes.find((item) => String(item.id) === String(selectedId)) || null,
    [notes, selectedId],
  );

  const wordCount = useMemo(
    () => draftContent.trim().split(/\s+/).filter(Boolean).length,
    [draftContent],
  );

  const syncDrafts = useCallback((note) => {
    setDraftTitle(String(note?.title || ""));
    setDraftContent(String(note?.content || ""));
    setLinkDraft({ text: "", url: "" });
    setShowLinkForm(false);
    setEditorSeed((prev) => prev + 1);
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
        window.dispatchEvent(new CustomEvent("notes:selected", { detail: { selectedId: null } }));
        return;
      }

      const stillExists = nextNotes.some((item) => String(item.id) === String(selectedId));
      const nextSelected = stillExists ? nextNotes.find((item) => String(item.id) === String(selectedId)) : nextNotes[0];
      setSelectedId(nextSelected?.id ?? null);
      syncDrafts(nextSelected);
      window.dispatchEvent(new CustomEvent("notes:selected", { detail: { selectedId: String(nextSelected?.id || "") } }));
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
    const handleExternalSelection = (event) => {
      const nextId = String(event?.detail?.selectedId || "").trim();
      if (!nextId) return;
      const nextNote = notes.find((item) => String(item.id) === nextId);
      if (!nextNote) return;
      setSelectedId(nextId);
      syncDrafts(nextNote);
      setNotice("");
    };
    window.addEventListener("notes:updated", handleNotesUpdated);
    window.addEventListener("notes:selected", handleExternalSelection);
    return () => {
      window.removeEventListener("notes:updated", handleNotesUpdated);
      window.removeEventListener("notes:selected", handleExternalSelection);
    };
  }, [isActive, loadNotes, notes, syncDrafts]);

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

  useEffect(() => {
    if (!editorRef.current) return;
    editorRef.current.innerHTML = selectedNote ? markdownToEditableHtml(draftContent) : "";
  }, [editorSeed, selectedNote]);

  const syncDraftFromEditor = useCallback(() => {
    if (!editorRef.current) return;
    setDraftContent(serializeEditorContent(editorRef.current));
  }, []);

  const handleEditorInput = useCallback(() => {
    syncDraftFromEditor();
  }, [syncDraftFromEditor]);

  const applyEditorCommand = useCallback((command, value = null) => {
    if (!editorRef.current) return;
    editorRef.current.focus();
    document.execCommand(command, false, value);
    syncDraftFromEditor();
  }, [syncDraftFromEditor]);

  const handleBlockFormat = useCallback((tagName) => {
    if (!editorRef.current) return;
    editorRef.current.focus();
    document.execCommand("formatBlock", false, tagName);
    syncDraftFromEditor();
  }, [syncDraftFromEditor]);

  const openLinkForm = useCallback(() => {
    const selection = window.getSelection?.();
    const selectionText = selection ? String(selection.toString() || "").trim() : "";
    setLinkDraft((prev) => ({ text: selectionText || prev.text, url: prev.url }));
    setShowLinkForm(true);
  }, []);

  const handleInsertLink = useCallback(() => {
    const url = String(linkDraft.url || "").trim();
    const text = String(linkDraft.text || "").trim();
    if (!url || !editorRef.current) return;

    editorRef.current.focus();
    const selection = window.getSelection?.();
    const selectionText = selection ? String(selection.toString() || "").trim() : "";
    const label = text || selectionText || url;
    document.execCommand("insertHTML", false, `<a href="${escapeHtml(url)}">${escapeHtml(label)}</a>`);

    setShowLinkForm(false);
    setLinkDraft({ text: "", url: "" });
    syncDraftFromEditor();
  }, [linkDraft, syncDraftFromEditor]);

  useEffect(() => {
    const handleShortcut = (event) => {
      if (!selectedNote || !editorRef.current) return;
      const activeElement = document.activeElement;
      const inEditor = activeElement === editorRef.current || editorRef.current.contains(activeElement);
      const inTitle = activeElement?.classList?.contains("notes-panel__title-input");
      if (!inEditor && !inTitle) return;
      if (!isModKey(event)) return;

      const key = String(event.key || "").toLowerCase();
      if (key === "b") {
        event.preventDefault();
        applyEditorCommand("bold");
      } else if (key === "i") {
        event.preventDefault();
        applyEditorCommand("italic");
      } else if (key === "s") {
        event.preventDefault();
        handleSave();
      } else if (key === "k" && inEditor) {
        event.preventDefault();
        openLinkForm();
      }
    };

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setShowLinkForm(false);
      }
    };

    window.addEventListener("keydown", handleShortcut);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("keydown", handleShortcut);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [applyEditorCommand, handleSave, openLinkForm, selectedNote]);

  return (
    <div className="workspace-panel notes-panel">
      <div className="workspace-panel__header">
        <div>
          <div className="workspace-panel__title-row">
            <h3>Revision note</h3>
            <div className="workspace-panel__eyebrow">
              <FiFileText />
              <span>Document editor</span>
            </div>
          </div>
          <p className="notes-panel__description">Edit the note directly in a single formatted document surface.</p>
        </div>
      </div>

      <div className="panel-grid panel-grid--stacked notes-panel__editor-shell">
        {selectedNote ? (
          <>
            <section className="panel-card">
              <div className="notes-panel__title-row notes-panel__top-row">
                <label className="notes-panel__title-wrap notes-panel__title-wrap--wide">
                  <span className="notes-panel__field-label">Title</span>
                  <input
                    className="notes-panel__title-input"
                    value={draftTitle}
                    onChange={(event) => setDraftTitle(event.target.value)}
                    placeholder="Enter note title"
                  />
                </label>
                <div className="notes-panel__header-actions">
                  <button type="button" className="primary-button" onClick={handleSave} disabled={saving || !selectedNote}>
                    <FiSave />
                    <span>{saving ? "Saving..." : "Save Note"}</span>
                  </button>
                  <button type="button" className="secondary-button" onClick={handleDelete} disabled={saving || !selectedNote}>
                    <FiTrash2 />
                    <span>Delete</span>
                  </button>
                </div>
              </div>

              <div className="notes-panel__document-footer notes-panel__meta-row">
                <span>{formatNoteDate(selectedNote.updated_at)}</span>
                <span>{wordCount} words</span>
              </div>
            </section>

            <section className="panel-card panel-card--stretch">
              <label className="notes-panel__content-wrap">
                <span className="notes-panel__field-label">Content</span>
                <div className="notes-panel__format-toolbar" role="toolbar" aria-label="Formatting tools">
                  <button type="button" className="secondary-button notes-panel__format-button" onClick={() => applyEditorCommand("bold")}> 
                    Bold
                  </button>
                  <button type="button" className="secondary-button notes-panel__format-button" onClick={() => applyEditorCommand("italic")}> 
                    Italic
                  </button>
                  <button type="button" className="secondary-button notes-panel__format-button" onClick={() => handleBlockFormat("h2")}> 
                    H2
                  </button>
                  <button type="button" className="secondary-button notes-panel__format-button" onClick={() => handleBlockFormat("h3")}> 
                    H3
                  </button>
                  <button type="button" className="secondary-button notes-panel__format-button" onClick={() => applyEditorCommand("insertUnorderedList")}> 
                    Bullet
                  </button>
                  <button type="button" className="secondary-button notes-panel__format-button" onClick={() => applyEditorCommand("insertOrderedList")}> 
                    Numbered
                  </button>
                  <button type="button" className="secondary-button notes-panel__format-button" onClick={() => handleBlockFormat("blockquote")}> 
                    Quote
                  </button>
                  <button type="button" className="secondary-button notes-panel__format-button" onClick={openLinkForm}>
                    <FiLink />
                    <span>Link</span>
                  </button>
                </div>

                {showLinkForm ? (
                  <div className="notes-panel__link-form">
                    <input
                      className="notes-panel__link-input"
                      value={linkDraft.text}
                      onChange={(event) => setLinkDraft((prev) => ({ ...prev, text: event.target.value }))}
                      placeholder="Link text"
                    />
                    <input
                      className="notes-panel__link-input"
                      value={linkDraft.url}
                      onChange={(event) => setLinkDraft((prev) => ({ ...prev, url: event.target.value }))}
                      placeholder="https://example.com"
                    />
                    <button type="button" className="secondary-button notes-panel__format-button" onClick={handleInsertLink}>
                      Insert
                    </button>
                  </div>
                ) : null}

                <div
                  ref={editorRef}
                  className="notes-panel__editor notes-panel__editor--document notes-panel__editor--rich"
                  contentEditable
                  suppressContentEditableWarning
                  data-placeholder="Edit your summary notes here"
                  onInput={handleEditorInput}
                />
              </label>
            </section>
          </>
        ) : (
          <section className="panel-card notes-panel__empty-state">
            <FiBookOpen />
            <strong>Select a note to open it in the editor.</strong>
            <span>Your saved summaries will open here in a document-style workspace.</span>
          </section>
        )}
      </div>
    </div>
  );
}
