import React from "react";

export function AssignmentRecipientSelector({
  students = [],
  assignmentTargets = [],
  assignmentTargetUsers = [],
  onToggleTarget = null,
  onUseAllTargets = null,
  onUseActiveTarget = null,
}) {
  if ((students || []).length <= 1) return null;

  return (
    <div className="role-hub-panel__note-box" style={{ marginBottom: 12 }}>
      <strong>Assignment Recipients</strong>
      <p className="sidebar-note">Select which learners will receive this assignment.</p>

      <div className="role-hub-panel__note-actions">
        <span>
          {assignmentTargetUsers.length > 0
            ? `${assignmentTargetUsers.length} learner(s) selected`
            : "No learners selected"}
        </span>
        <button
          type="button"
          className="secondary-button"
          onClick={onUseAllTargets}
        >
          Select All
        </button>
        <button
          type="button"
          className="secondary-button"
          onClick={onUseActiveTarget}
        >
          Select Active Only
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
        {(students || []).map((student) => {
          const username = student?.username;
          const isSelected = assignmentTargetUsers.includes(username);
          return (
            <label key={username} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => onToggleTarget?.(username)}
              />
              <span>
                {student?.first_name || student?.email || username}
                {student?.relation_label && ` (${student.relation_label})`}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
