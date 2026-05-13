import React from "react";

export function RoleHubHeader({
  workspaceTitle = "Role Hub",
  workspaceDescription = "",
  previewRole = "student",
  isAdminRole = false,
}) {
  return (
    <div className="role-hub-panel__note-box" style={{ marginBottom: 12 }}>
      <div className="role-hub-panel__note-actions" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <strong>{workspaceTitle}</strong>
          <p className="sidebar-note" style={{ marginTop: 6 }}>{workspaceDescription}</p>
        </div>
        <span className="progress-pill progress-pill--neutral">
          {isAdminRole ? `Preview: ${previewRole}` : previewRole}
        </span>
      </div>
      {isAdminRole && (
        <div className="role-hub-panel__note-actions">
          <span>Admin-only controls now live in the dedicated Admin Center tab.</span>
        </div>
      )}
    </div>
  );
}
