import React from "react";
import { DEFAULT_ASSIGNMENT_TEMPLATES, formatTemplateTypeLabel } from "../utils/roleHubUtils";

export function AssignmentCreatorForm({
  assignmentType = "lesson",
  templateCategory = "general",
  assignmentSubject = "",
  assignmentNote = "",
  assignmentDueLabel = "",
  assignmentTargetUsers = [],
  assignmentSubmitting = false,
  onTypeChange = null,
  onCategoryChange = null,
  onSubjectChange = null,
  onNoteChange = null,
  onDueChange = null,
  onApplyTemplate = null,
  onAssign = null,
}) {
  const assignmentButtonLabel = assignmentSubmitting
    ? "Assigning..."
    : assignmentTargetUsers.length > 1
      ? `Assign to ${assignmentTargetUsers.length} Learners`
      : "Assign Task";

  return (
    <div className="role-hub-panel__note-box" style={{ marginBottom: 12 }}>
      <strong>Create Assignment</strong>
      <p className="sidebar-note">Compose a task and send it to selected learners.</p>

      <div className="role-hub-panel__note-actions">
        {DEFAULT_ASSIGNMENT_TEMPLATES.map((template) => (
          <button
            key={template.id}
            type="button"
            className="secondary-button"
            onClick={() => onApplyTemplate?.(template)}
          >
            {template.label}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span>Assignment type</span>
          <select
            aria-label="Assignment type"
            value={assignmentType}
            onChange={(event) => onTypeChange?.(event.target.value)}
          >
            <option value="lesson">Lesson</option>
            <option value="quiz">Quiz</option>
            <option value="assessment">Assessment</option>
            <option value="chat">Chat</option>
            <option value="flashcards">Flashcards</option>
          </select>
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span>Category</span>
          <select
            aria-label="Assignment category"
            value={templateCategory}
            onChange={(event) => onCategoryChange?.(event.target.value)}
          >
            <option value="general">General</option>
            <option value="stem">STEM</option>
            <option value="humanities">Humanities</option>
            <option value="languages">Languages</option>
            <option value="exam">Exam Prep</option>
          </select>
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span>Subject (optional)</span>
          <input
            aria-label="Subject"
            type="text"
            placeholder="e.g., Math, Science, English"
            value={assignmentSubject}
            onChange={(event) => onSubjectChange?.(event.target.value)}
          />
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span>Assignment note</span>
          <textarea
            aria-label="Assignment note"
            rows={3}
            placeholder="Describe the assignment..."
            value={assignmentNote}
            onChange={(event) => onNoteChange?.(event.target.value)}
          />
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span>Due date (optional)</span>
          <input
            aria-label="Due date"
            type="date"
            value={assignmentDueLabel}
            onChange={(event) => onDueChange?.(event.target.value)}
          />
        </label>

        <button
          type="button"
          className="primary-button"
          onClick={onAssign}
          disabled={assignmentSubmitting || !assignmentNote.trim()}
        >
          {assignmentButtonLabel}
        </button>
      </div>
    </div>
  );
}
