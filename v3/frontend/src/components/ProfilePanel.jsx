import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  FiCalendar,
  FiCheckCircle,
  FiCreditCard,
  FiMail,
  FiRefreshCw,
  FiSave,
  FiShield,
  FiUser,
} from "react-icons/fi";
import { apiFetch, parseApiError } from "../services/api";

function formatDateLabel(value) {
  if (!value) return "Not set";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString([], { dateStyle: "medium" });
}

function formatEntitlementLabel(value) {
  return String(value || "feature")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function ProfilePanel({
  planSummary = null,
  onOpenSubscription = null,
  onProfileUpdated = null,
  isActive = true,
}) {
  const [profile, setProfile] = useState({
    username: "",
    email: "",
    role: "student",
    first_name: "",
    last_name: "",
    dob: "",
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const activeClasses = useMemo(
    () => (Array.isArray(planSummary?.classes) ? planSummary.classes : []),
    [planSummary?.classes]
  );

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const profileRes = await apiFetch("/profile");
      if (!profileRes.ok) {
        throw new Error(await parseApiError(profileRes, "Unable to load profile details."));
      }

      const data = await profileRes.json();
      const payload = data?.profile || data?.data?.profile || data || {};
      setProfile({
        username: payload.username || "",
        email: payload.email || "",
        role: payload.role || "student",
        first_name: payload.first_name || "",
        last_name: payload.last_name || "",
        dob: payload.dob || "",
      });
    } catch (err) {
      setError(err?.message || "Unable to load profile details.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isActive === false) return;
    loadProfile();
  }, [isActive, loadProfile]);

  const handleFieldChange = (field, value) => {
    setProfile((current) => ({
      ...current,
      [field]: value,
    }));
    setMessage("");
    setError("");
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setMessage("");

    try {
      const res = await apiFetch("/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: profile.first_name,
          last_name: profile.last_name,
          dob: profile.dob || null,
        }),
      });

      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to save profile changes."));
      }

      const data = await res.json();
      const updated = data?.profile || data?.data?.profile || {};
      setProfile((current) => ({
        ...current,
        first_name: updated.first_name || current.first_name,
        last_name: updated.last_name || current.last_name,
        dob: updated.dob || current.dob,
      }));
      setMessage("Profile updated successfully.");
      onProfileUpdated?.(updated);
    } catch (err) {
      setError(err?.message || "Unable to save profile changes.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="workspace-panel profile-panel">
      {error ? <div className="subscription-modal__error">{error}</div> : null}
      {message ? (
        <div className="profile-panel__success" role="status">
          <FiCheckCircle />
          <span>{message}</span>
        </div>
      ) : null}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end", marginBottom: 12 }}>
        <button type="button" className="secondary-button" onClick={loadProfile} disabled={loading}>
          <FiRefreshCw />
          <span>{loading ? "Refreshing..." : "Refresh"}</span>
        </button>
        <button type="button" className="secondary-button" onClick={onOpenSubscription} disabled={!onOpenSubscription}>
          <FiCreditCard />
          <span>Manage Subscription</span>
        </button>
      </div>

      <div className="profile-panel__grid">
        <article className="profile-panel__card">
          <div className="profile-panel__card-top">
            <strong>Account details</strong>
            <span className="progress-pill progress-pill--neutral">{profile.role || "user"}</span>
          </div>

          <label className="profile-panel__field">
            <span>First name</span>
            <input
              aria-label="First name"
              type="text"
              value={profile.first_name}
              onChange={(event) => handleFieldChange("first_name", event.target.value)}
              placeholder="First name"
            />
          </label>

          <label className="profile-panel__field">
            <span>Last name</span>
            <input
              aria-label="Last name"
              type="text"
              value={profile.last_name}
              onChange={(event) => handleFieldChange("last_name", event.target.value)}
              placeholder="Last name"
            />
          </label>

          <label className="profile-panel__field">
            <span>Date of birth</span>
            <div className="profile-panel__inline-field">
              <FiCalendar />
              <input
                aria-label="Date of birth"
                type="date"
                value={profile.dob || ""}
                onChange={(event) => handleFieldChange("dob", event.target.value)}
              />
            </div>
          </label>

          <label className="profile-panel__field">
            <span>Email</span>
            <div className="profile-panel__inline-field is-readonly">
              <FiMail />
              <input aria-label="Email" type="email" value={profile.email || ""} readOnly />
            </div>
          </label>

          <label className="profile-panel__field">
            <span>Role</span>
            <div className="profile-panel__inline-field is-readonly">
              <FiShield />
              <input aria-label="Role" type="text" value={profile.role || "student"} readOnly />
            </div>
          </label>

          <button type="button" className="primary-button profile-panel__save" onClick={handleSave} disabled={saving || loading}>
            <FiSave />
            <span>{saving ? "Saving..." : "Save Changes"}</span>
          </button>
        </article>

        <article className="profile-panel__card">
          <div className="profile-panel__card-top">
            <strong>Subscription overview</strong>
            <span className={`progress-pill progress-pill--${planSummary?.isTrial ? "medium" : "low"}`}>
              {planSummary?.planCode || "FREE"}
              {planSummary?.isTrial ? " Trial" : ""}
            </span>
          </div>

          <div className="profile-panel__summary-list">
            <div>
              <span>Ask usage</span>
              <strong>
                {planSummary?.usage?.ask_count || 0}/{planSummary?.limits?.ask_count || 0}
              </strong>
            </div>
            <div>
              <span>Lesson generation</span>
              <strong>
                {planSummary?.usage?.lesson_count || 0}/{planSummary?.limits?.lesson_count || 0}
              </strong>
            </div>
            <div>
              <span>Quiz generation</span>
              <strong>
                {planSummary?.usage?.quiz_count || 0}/{planSummary?.limits?.quiz_count || 0}
              </strong>
            </div>
          </div>

          <div className="profile-panel__subscription-block">
            <strong>Active class subscriptions</strong>
            {activeClasses.length === 0 ? (
              <p className="sidebar-note">No class-specific subscriptions are active yet on this account.</p>
            ) : (
              <div className="profile-panel__chip-list">
                {activeClasses.map((item) => (
                  <div key={`${item.class_name}-${item.expires_at || "active"}`} className="profile-panel__chip">
                    <span>{item.class_name}</span>
                    <small>
                      {item.expires_at ? `Expires ${formatDateLabel(item.expires_at)}` : "Active"}
                      {item.auto_renew ? " · auto-renew" : ""}
                    </small>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="profile-panel__subscription-block">
            <strong>Included features</strong>
            {(planSummary?.entitlements || []).length === 0 ? (
              <p className="sidebar-note">Your current plan details will appear here after plan data is loaded.</p>
            ) : (
              <div className="profile-panel__entitlement-list">
                {(planSummary?.entitlements || []).map((item) => (
                  <div key={item.feature_key} className={`profile-panel__entitlement${item.enabled ? " is-enabled" : ""}`}>
                    <FiCheckCircle />
                    <span>{formatEntitlementLabel(item.feature_key)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </article>
      </div>
    </section>
  );
}
