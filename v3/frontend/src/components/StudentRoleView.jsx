import React from "react";

export function StudentRoleView({ mentors = [], loading = false, onPlanAction = null }) {
  return (
    <div className="role-hub-panel__note-box" style={{ marginBottom: 12 }}>
      <strong>My Mentors</strong>
      <p className="sidebar-note">Your connected teachers and parents who can guide your learning.</p>

      {loading ? (
        <p className="sidebar-note" style={{ marginTop: 12 }}>Loading mentors...</p>
      ) : mentors.length === 0 ? (
        <p className="sidebar-note" style={{ marginTop: 12 }}>No mentors connected yet.</p>
      ) : (
        <div style={{ marginTop: 12 }}>
          {mentors.map((mentor) => (
            <div key={mentor.username} style={{ marginBottom: 8 }}>
              <p>{mentor.first_name || mentor.email || mentor.username}</p>
              {mentor.relation_label && <span className="sidebar-note">{mentor.relation_label}</span>}
            </div>
          ))}
        </div>
      )}

      {onPlanAction && (
        <button
          type="button"
          className="secondary-button"
          onClick={() =>
            onPlanAction({
              id: "view-assignments",
              action_tab: "assignments",
              cta_label: "View My Assignments",
              context_hint: "Check work assigned by your mentors.",
            })
          }
          style={{ marginTop: 12 }}
        >
          View My Assignments
        </button>
      )}
    </div>
  );
}
