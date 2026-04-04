import React, { useCallback, useEffect, useMemo, useState } from "react";
import { FiBookOpen, FiEye, FiRefreshCw, FiSettings, FiShield, FiZap } from "react-icons/fi";
import settings from "../../../configs/settings.json";
import { apiFetch, parseApiError } from "../services/api";

function formatRoleLabel(role = "admin") {
  const normalized = String(role || "admin").trim().toLowerCase();
  const labels = {
    admin: "Admin",
    student: "Student",
    teacher: "Teacher",
    parent: "Parent",
  };
  return labels[normalized] || (normalized ? `${normalized.charAt(0).toUpperCase()}${normalized.slice(1)}` : "Admin");
}

function getConfiguredModelProfiles() {
  const configuredProfiles = settings?.model_profiles;
  if (!configuredProfiles || typeof configuredProfiles !== "object") {
    return [
      { key: "balanced", label: "Balanced", description: "Recommended mix of quality and speed for daily use.", task_models: {} },
      { key: "best-quality", label: "Best Quality", description: "Use stronger explanation and reasoning models where possible.", task_models: {} },
      { key: "fastest", label: "Fastest", description: "Favor the quickest local responses for all users.", task_models: {} },
    ];
  }

  return Object.entries(configuredProfiles).map(([key, entry]) => {
    const item = entry && typeof entry === "object" ? entry : {};
    return {
      key,
      label: String(item.label || key.replace(/-/g, " ").replace(/\b\w/g, (char) => char.toUpperCase())),
      description: String(item.description || ""),
      task_models: item.task_models && typeof item.task_models === "object" ? item.task_models : {},
    };
  });
}

const FALLBACK_MODEL_PROFILES = getConfiguredModelProfiles();
const DEFAULT_MODEL_PROFILE = String(settings?.active_model_profile || FALLBACK_MODEL_PROFILES[0]?.key || "balanced").trim().toLowerCase() || "balanced";

export default function AdminPanel({
  viewRole = "admin",
  onAdminViewRoleChange = null,
  onAdminReindex = null,
  onAdminIncrementalReindex = null,
  adminRunning = false,
  adminMessage = "",
  isActive = true,
}) {
  const [availableModelProfiles, setAvailableModelProfiles] = useState(FALLBACK_MODEL_PROFILES);
  const [selectedModelProfile, setSelectedModelProfile] = useState(DEFAULT_MODEL_PROFILE);
  const [modelProfileLoading, setModelProfileLoading] = useState(false);
  const [modelProfileSaving, setModelProfileSaving] = useState(false);
  const [modelProfileStatus, setModelProfileStatus] = useState("");
  const [modelProfileNotice, setModelProfileNotice] = useState("");
  const [error, setError] = useState("");

  const selectedModelProfileDetails = useMemo(
    () => (availableModelProfiles || []).find((item) => item?.key === selectedModelProfile) || null,
    [availableModelProfiles, selectedModelProfile],
  );

  const loadAdminModelProfiles = useCallback(async () => {
    setModelProfileLoading(true);
    setError("");
    try {
      const res = await apiFetch("/admin/model-profiles", { method: "GET" });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to load global model profile settings."));
      }
      const payload = await res.json();
      const profiles = Array.isArray(payload?.profiles) && payload.profiles.length > 0 ? payload.profiles : FALLBACK_MODEL_PROFILES;
      const activeProfile = payload?.active_profile || profiles[0]?.key || DEFAULT_MODEL_PROFILE;
      setAvailableModelProfiles(profiles);
      setSelectedModelProfile(activeProfile);
      setModelProfileStatus("");
      setModelProfileNotice("");
    } catch (_err) {
      setAvailableModelProfiles(FALLBACK_MODEL_PROFILES);
      setSelectedModelProfile((current) => {
        const availableKeys = FALLBACK_MODEL_PROFILES.map((item) => item.key);
        return availableKeys.includes(current) ? current : DEFAULT_MODEL_PROFILE;
      });
      setModelProfileNotice("Admin state is unavailable right now — showing the configured profile options locally.");
      setError("");
    } finally {
      setModelProfileLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isActive) return;
    loadAdminModelProfiles();
  }, [isActive, loadAdminModelProfiles]);

  const handleApplyGlobalModelProfile = async () => {
    if (!selectedModelProfile) return;

    setModelProfileSaving(true);
    setModelProfileStatus("");
    setModelProfileNotice("");
    setError("");
    try {
      const res = await apiFetch("/admin/model-profiles", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_key: selectedModelProfile }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to update the global model profile."));
      }
      const payload = await res.json();
      const profiles = Array.isArray(payload?.profiles) ? payload.profiles : availableModelProfiles;
      const activeProfile = payload?.active_profile || selectedModelProfile;
      setAvailableModelProfiles(profiles);
      setSelectedModelProfile(activeProfile);
      setModelProfileStatus(`Global profile updated to ${activeProfile}.`);
    } catch (err) {
      setError(String(err?.message || err));
    } finally {
      setModelProfileSaving(false);
    }
  };

  return (
    <section className="workspace-panel profile-panel admin-center-panel">
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
        <button
          type="button"
          className="secondary-button"
          onClick={loadAdminModelProfiles}
          disabled={modelProfileLoading || modelProfileSaving}
        >
          <FiRefreshCw />
          <span>{modelProfileLoading ? "Refreshing..." : "Refresh Admin State"}</span>
        </button>
      </div>

      {error ? <div className="subscription-modal__error">{error}</div> : null}

      <div className="progress-toolbar-card">
        <div className="progress-toolbar-card__header">
          <div>
            <div className="workspace-panel__eyebrow">
              <FiShield />
              <span>Admin Center</span>
            </div>
            <p className="progress-toolbar-card__copy">
              Keep all admin-only controls here so role previews stay clean and the controls stay visually consistent with the rest of the workspace.
            </p>
          </div>
          <span className="progress-pill progress-pill--neutral">Previewing as {formatRoleLabel(viewRole)}</span>
        </div>
      </div>

      <div className="profile-panel__grid">
        <article className="profile-panel__card">
          <div className="profile-panel__card-top">
            <strong>Workspace Preview</strong>
            <span className="progress-pill progress-pill--neutral">{formatRoleLabel(viewRole)}</span>
          </div>
          <p className="sidebar-note">Switch the visible workspace between admin, student, teacher, and parent views without mixing these controls into those pages.</p>
          <label className="progress-toolbar__field">
            <span>View workspace as</span>
            <div className="workspace-select-wrap workspace-select-wrap--compact">
              <select
                aria-label="View workspace as"
                value={viewRole}
                onChange={(event) => onAdminViewRoleChange?.(event.target.value)}
              >
                <option value="admin">Admin</option>
                <option value="student">Student</option>
                <option value="teacher">Teacher</option>
                <option value="parent">Parent</option>
              </select>
            </div>
          </label>
          <div className="profile-panel__summary-list">
            <div>
              <span>Current preview</span>
              <strong><FiEye style={{ marginRight: 6 }} />{formatRoleLabel(viewRole)}</strong>
            </div>
          </div>
        </article>

        <article className="profile-panel__card">
          <div className="profile-panel__card-top">
            <strong>Global AI Behavior</strong>
            <span className="progress-pill progress-pill--neutral">App-wide</span>
          </div>
          <p className="sidebar-note">Choose the model behavior profile that every user will experience.</p>
          {modelProfileNotice ? <p className="sidebar-note" role="status">{modelProfileNotice}</p> : null}
          <label className="progress-toolbar__field">
            <span>Model behavior profile</span>
            <div className="workspace-select-wrap workspace-select-wrap--compact">
              <select
                aria-label="Model behavior profile"
                value={selectedModelProfile}
                onChange={(event) => setSelectedModelProfile(event.target.value)}
                disabled={modelProfileLoading || modelProfileSaving}
              >
                {availableModelProfiles.length > 0 ? (
                  availableModelProfiles.map((profile) => (
                    <option key={profile.key} value={profile.key}>
                      {profile.label || profile.key}
                    </option>
                  ))
                ) : (
                  <option value={selectedModelProfile}>{selectedModelProfile || "balanced"}</option>
                )}
              </select>
            </div>
          </label>
          {selectedModelProfileDetails?.description ? (
            <p className="sidebar-note">{selectedModelProfileDetails.description}</p>
          ) : null}
          {selectedModelProfileDetails?.task_models ? (
            <p className="sidebar-note">
              {Object.entries(selectedModelProfileDetails.task_models)
                .map(([taskName, modelName]) => `${taskName}: ${modelName}`)
                .join(" · ")}
            </p>
          ) : null}
          <div className="profile-panel__summary-list">
            <div>
              <span>Current selected profile</span>
              <strong>{selectedModelProfileDetails?.label || selectedModelProfile || "balanced"}</strong>
            </div>
          </div>
          <div className="admin-center-panel__actions">
            <button
              type="button"
              className="primary-button"
              onClick={handleApplyGlobalModelProfile}
              disabled={modelProfileLoading || modelProfileSaving || !selectedModelProfile}
            >
              <FiSettings />
              <span>{modelProfileSaving ? "Applying..." : "Apply Global Profile"}</span>
            </button>
          </div>
          {modelProfileStatus ? <div className="profile-panel__success" role="status"><span>{modelProfileStatus}</span></div> : null}
        </article>

        <article className="profile-panel__card">
          <div className="profile-panel__card-top">
            <strong>Admin Actions</strong>
            <span className={`progress-pill progress-pill--${adminRunning ? "medium" : "neutral"}`}>{adminRunning ? "Running" : "Ready"}</span>
          </div>
          <p className="sidebar-note">Run indexing or maintenance actions here without cluttering the role preview workspaces.</p>
          <div className="admin-center-panel__actions">
            <button
              type="button"
              className="secondary-button"
              onClick={() => onAdminReindex?.()}
              disabled={adminRunning}
            >
              <FiBookOpen />
              <span>Reindex Knowledge Base</span>
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => onAdminIncrementalReindex?.()}
              disabled={adminRunning}
            >
              <FiZap />
              <span>Incremental Reindex</span>
            </button>
          </div>
          {(adminRunning || adminMessage) ? (
            <div className="profile-panel__summary-list">
              <div>
                <span>Status</span>
                <strong>{adminRunning ? "Admin action running…" : adminMessage}</strong>
              </div>
            </div>
          ) : null}
        </article>
      </div>
    </section>
  );
}
