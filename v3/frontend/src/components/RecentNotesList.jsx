import React from "react";
import { formatNoteDate } from "../utils/roleHubUtils";

export function RecentNotesList({
  filteredNotes = [],
  editingNoteId = null,
  editingNoteText = "",
  editingNoteVisibility = "all",
  noteVisibilityFilter = "all",
  noteBusyKey = "",
  canEditNote = false,
  onVisibilityFilterChange = null,
  onStartEdit = null,
  onCancelEdit = null,
  onEditTextChange = null,
  onEditVisibilityChange = null,
  onSave = null,
  onDelete = null,
}) {
  if (filteredNotes.length === 0) {
    return null;
  }

  return (
    <div className="role-hub-panel__note-box" style={{ marginTop: 12 }}>
      <strong>Recent Notes</strong>
      <p className="sidebar-note">Shared coaching notes and reflections.</p>

      <div className="role-hub-panel__note-actions" style={{ marginTop: 8 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span>Filter by note visibility</span>
          <select
            aria-label="Filter notes by visibility"
            value={noteVisibilityFilter}
            onChange={(event) => onVisibilityFilterChange?.(event.target.value)}
          >
            <option value="all">All visibility levels</option>
            <option value="private">Private</option>
            <option value="shared">Shared</option>
            <option value="public">Public</option>
          </select>
        </label>
      </div>

      {filteredNotes.map((note) => {
        const busy = noteBusyKey === `edit:${note.id}` || noteBusyKey === `delete:${note.id}`;
        const isEditingNote = editingNoteId === note.id;
        const createdDate = formatNoteDate(note.created_at);

        return (
          <div key={note.id} className="role-hub-panel__note-box" style={{ marginTop: 8 }}>
            {isEditingNote ? (
              <>
                <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <span>Edit note</span>
                  <textarea
                    aria-label="Edit note"
                    rows={3}
                    value={editingNoteText}
                    onChange={(event) => onEditTextChange?.(event.target.value)}
                  />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
                  <span>Visibility</span>
                  <select
                    aria-label="Note visibility"
                    value={editingNoteVisibility}
                    onChange={(event) => onEditVisibilityChange?.(event.target.value)}
                  >
                    <option value="private">Private</option>
                    <option value="shared">Shared</option>
                    <option value="public">Public</option>
                  </select>
                </label>
                <div className="role-hub-panel__note-actions" style={{ marginTop: 8 }}>
                  <button
                    type="button"
                    className="primary-button"
                    onClick={() => onSave?.(note.id)}
                    disabled={busy || !editingNoteText.trim()}
                  >
                    Save Note
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={onCancelEdit}
                    disabled={busy}
                  >
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
                <p>{note.note_text}</p>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
                  <span className="sidebar-note">
                    {note.author_role || "Note"} · {createdDate}
                  </span>
                  {note.visibility && (
                    <span className={`progress-pill progress-pill--neutral`}>
                      {note.visibility}
                    </span>
                  )}
                </div>
              </>
            )}

            {!isEditingNote && canEditNote && (
              <div className="role-hub-panel__note-actions" style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => onStartEdit?.(note)}
                  disabled={busy}
                >
                  Edit Note
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => onDelete?.(note.id)}
                  disabled={busy}
                >
                  Delete Note
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
