import React from "react";
import {
  getAssignmentDueMeta,
  buildRecentActivityAction,
  buildTopSubjectAction,
} from "../utils/roleHubUtils";

export function AssignmentListWithBulkActions({
  filteredAssignments = [],
  studentMastery = [],
  topSubjects = [],
  recentActivity = [],
  bulkAssignmentSummary = {},
  editingAssignmentId = null,
  editingAssignmentTitle = "",
  editingAssignmentDescription = "",
  editingAssignmentType = "lesson",
  editingAssignmentDueLabel = "",
  assignmentBusyKey = "",
  onBulkUpdate = null,
  onStartEdit = null,
  onCancelEdit = null,
  onSave = null,
  onUpdateStatus = null,
  onDelete = null,
  onEditTitleChange = null,
  onEditDescriptionChange = null,
  onEditTypeChange = null,
  onEditDueChange = null,
  onPlanAction = null,
}) {
  if (
    filteredAssignments.length === 0 &&
    studentMastery.length === 0 &&
    topSubjects.length === 0 &&
    recentActivity.length === 0
  ) {
    return null;
  }

  return (
    <div className="role-hub-panel__insights">
      {filteredAssignments.length > 0 && (
        <div className="role-hub-panel__insight-card">
          <strong>Assigned Tasks</strong>
          <div className="role-hub-panel__note-box" style={{ marginTop: 12 }}>
            <strong>Bulk Assignment Actions</strong>
            <p className="sidebar-note">Apply quick updates to the assignments currently visible.</p>
            <div className="role-hub-panel__note-actions">
              <span>{bulkAssignmentSummary.openVisibleCount} open visible</span>
              <span>{bulkAssignmentSummary.overdueVisibleCount} overdue</span>
              {bulkAssignmentSummary.dismissedVisibleCount > 0 && (
                <span>{bulkAssignmentSummary.dismissedVisibleCount} dismissed</span>
              )}
            </div>
            <div className="role-hub-panel__note-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => onBulkUpdate?.("complete-open")}
                disabled={assignmentBusyKey.startsWith("bulk:") || bulkAssignmentSummary.openVisibleCount === 0}
              >
                Mark Open Done
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() => onBulkUpdate?.("dismiss-overdue")}
                disabled={assignmentBusyKey.startsWith("bulk:") || bulkAssignmentSummary.overdueVisibleCount === 0}
              >
                Dismiss Overdue
              </button>
              {bulkAssignmentSummary.dismissedVisibleCount > 0 && (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => onBulkUpdate?.("reopen-dismissed")}
                  disabled={assignmentBusyKey.startsWith("bulk:")}
                >
                  Reopen Dismissed
                </button>
              )}
            </div>
          </div>

          {filteredAssignments.length === 0 ? (
            <p className="sidebar-note">No assignments match the current filters.</p>
          ) : (
            filteredAssignments.map((item) => {
              const busy =
                assignmentBusyKey === `edit:${item.id}` ||
                assignmentBusyKey === `update:${item.id}` ||
                assignmentBusyKey === `delete:${item.id}` ||
                assignmentBusyKey.startsWith("bulk:");
              const dueMeta = getAssignmentDueMeta(item.due_label);
              const statusLabel =
                item.status === "completed" ? "Done" : item.status === "dismissed" ? "Dismissed" : "Assigned";
              const isEditingAssignment = editingAssignmentId === item.id;

              return (
                <div key={item.id || item.title} style={{ marginTop: 12 }}>
                  {isEditingAssignment ? (
                    <div className="role-hub-panel__note-box">
                      <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <span>Assignment title</span>
                        <input
                          aria-label="Assignment title"
                          type="text"
                          value={editingAssignmentTitle}
                          onChange={(event) => onEditTitleChange?.(event.target.value)}
                        />
                      </label>
                      <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <span>Assignment note</span>
                        <textarea
                          aria-label="Assignment note"
                          rows={3}
                          value={editingAssignmentDescription}
                          onChange={(event) => onEditDescriptionChange?.(event.target.value)}
                        />
                      </label>
                      <div className="role-hub-panel__note-actions">
                        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          <span>Assignment type</span>
                          <select
                            aria-label="Assignment type"
                            value={editingAssignmentType}
                            onChange={(event) => onEditTypeChange?.(event.target.value)}
                          >
                            <option value="lesson">Lesson</option>
                            <option value="quiz">Quiz</option>
                            <option value="assessment">Assessment</option>
                            <option value="chat">Chat</option>
                            <option value="flashcards">Flashcards</option>
                          </select>
                        </label>
                        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          <span>Assignment due</span>
                          <input
                            aria-label="Assignment due"
                            type="date"
                            value={editingAssignmentDueLabel}
                            onChange={(event) => onEditDueChange?.(event.target.value)}
                            placeholder="Optional due date"
                          />
                        </label>
                        <button
                          type="button"
                          className="primary-button"
                          onClick={() => onSave?.(item.id)}
                          disabled={busy || !editingAssignmentTitle.trim() || !editingAssignmentDescription.trim()}
                        >
                          Save Assignment
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
                    </div>
                  ) : (
                    <>
                      <p>{item.title}</p>
                      <span>{item.description}</span>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                        <span>
                          {statusLabel}
                          {item.due_label ? ` · Due ${item.due_label}` : ""}
                        </span>
                        {dueMeta.label && (
                          <span className={`progress-pill progress-pill--${dueMeta.tone}`}>
                            {dueMeta.label}
                          </span>
                        )}
                      </div>
                    </>
                  )}
                  {!isEditingAssignment && item.cta_label && (
                    <button
                      type="button"
                      className="secondary-button progress-plan-item__action"
                      onClick={() => onPlanAction?.(item)}
                      disabled={!onPlanAction}
                    >
                      {item.cta_label}
                    </button>
                  )}
                  {isEditingAssignment ? null : (
                    <button
                      type="button"
                      className="secondary-button progress-plan-item__action"
                      onClick={() => onStartEdit?.(item)}
                      disabled={busy}
                    >
                      Edit Assignment
                    </button>
                  )}
                  {isEditingAssignment ? null : (
                    <button
                      type="button"
                      className="secondary-button progress-plan-item__action"
                      onClick={() =>
                        onUpdateStatus?.(item.id, { status: item.status === "dismissed" ? "assigned" : "dismissed" })
                      }
                      disabled={busy}
                    >
                      {item.status === "dismissed" ? "Reopen Assignment" : "Dismiss Assignment"}
                    </button>
                  )}
                  <button
                    type="button"
                    className="secondary-button progress-plan-item__action"
                    onClick={() => onDelete?.(item.id)}
                    disabled={busy}
                  >
                    Delete Assignment
                  </button>
                </div>
              );
            })
          )}
        </div>
      )}

      {studentMastery.length > 0 && (
        <div className="role-hub-panel__insight-card">
          <strong>Subject Mastery</strong>
          {studentMastery.slice(0, 3).map((item) => {
            const subjectLabel = item.subject || item.chapter || "Topic";
            return (
              <div key={`${item.subject}-${item.chapter}`} style={{ marginTop: 12 }}>
                <p>
                  {item.subject}
                  {item.chapter ? ` — ${item.chapter}` : ""} · {item.mastery_pct || 0}% mastery
                </p>
                {onPlanAction && (
                  <button
                    type="button"
                    className="secondary-button progress-plan-item__action"
                    onClick={() =>
                      onPlanAction({
                        id: `mastery-${String(subjectLabel).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
                        action_tab: "quiz",
                        cta_label: `Practice ${subjectLabel} Quiz`,
                        chapter_hint: subjectLabel,
                        context_hint: `Practice ${subjectLabel} with a short quiz to strengthen mastery.`,
                      })
                    }
                  >
                    {`Practice ${subjectLabel} Quiz`}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {topSubjects.length > 0 && (
        <div className="role-hub-panel__insight-card">
          <strong>Time by Subject</strong>
          {topSubjects.slice(0, 3).map((item, index) => {
            const subjectLabel = item.subject || item.chapter || "Topic";
            const action = buildTopSubjectAction(item);
            return (
              <div key={`${subjectLabel}-${index}`} style={{ marginTop: 12 }}>
                <p>{subjectLabel}</p>
                <span>{Math.max(1, Math.round(Number(item.study_seconds || 0) / 60))} min</span>
                {action?.cta_label && onPlanAction && (
                  <button
                    type="button"
                    className="secondary-button progress-plan-item__action"
                    onClick={() => onPlanAction?.(action)}
                    disabled={!onPlanAction}
                  >
                    {action.cta_label}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {recentActivity.length > 0 && (
        <div className="role-hub-panel__insight-card">
          <strong>Recent Activity</strong>
          {recentActivity.slice(0, 3).map((item, index) => {
            const primaryLabel =
              item.subject && item.chapter && item.subject !== item.chapter
                ? `${item.subject} — ${item.chapter}`
                : item.subject || item.chapter || item.activity_type;
            const detailParts = [];
            const action = buildRecentActivityAction(item);
            if (item.activity_type) {
              detailParts.push(String(item.activity_type).replace(/_/g, " "));
            }
            if (Number(item.duration_seconds || 0) > 0) {
              detailParts.push(
                `${Math.max(1, Math.round(Number(item.duration_seconds || 0) / 60))} min`
              );
            }
            return (
              <div key={`${item.activity_type}-${item.subject}-${index}`} style={{ marginTop: 12 }}>
                <p>{primaryLabel}</p>
                {detailParts.length > 0 && <span>{detailParts.join(" · ")}</span>}
                {action?.cta_label && onPlanAction && (
                  <button
                    type="button"
                    className="secondary-button progress-plan-item__action"
                    onClick={() => onPlanAction?.(action)}
                    disabled={!onPlanAction}
                  >
                    {action.cta_label}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
