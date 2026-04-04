import React, { useMemo } from "react";
import {
  FiCheckCircle,
  FiCreditCard,
  FiRefreshCw,
  FiZap,
} from "react-icons/fi";

function formatDateLabel(value, fallback = "Not scheduled") {
  if (!value) return fallback;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString([], { dateStyle: "medium" });
}

function formatMoney(cents, currency = "INR") {
  const amount = Number(cents || 0) / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatEntitlementLabel(value) {
  return String(value || "feature")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function BillingPanel({
  planSummary = null,
  onOpenSubscription = null,
  onRefresh = null,
  isLoading = false,
}) {
  const activeClasses = useMemo(
    () => (Array.isArray(planSummary?.classes) ? planSummary.classes : []),
    [planSummary?.classes],
  );

  const usageRows = useMemo(() => {
    const rows = [
      { key: "ask_count", label: "Questions", used: Number(planSummary?.usage?.ask_count || 0), limit: Number(planSummary?.limits?.ask_count || 0) },
      { key: "lesson_count", label: "Lessons", used: Number(planSummary?.usage?.lesson_count || 0), limit: Number(planSummary?.limits?.lesson_count || 0) },
      { key: "quiz_count", label: "Quizzes", used: Number(planSummary?.usage?.quiz_count || 0), limit: Number(planSummary?.limits?.quiz_count || 0) },
      { key: "uploads_count", label: "Uploads", used: Number(planSummary?.usage?.uploads_count || 0), limit: Number(planSummary?.limits?.uploads_count || 0) },
    ];

    return rows
      .filter((item) => item.limit > 0 || item.used > 0)
      .map((item) => ({
        ...item,
        remaining: item.limit > 0 ? Math.max(item.limit - item.used, 0) : 0,
        pct: item.limit > 0 ? Math.min((item.used / item.limit) * 100, 100) : 0,
      }));
  }, [planSummary]);

  const renewalDate = planSummary?.isTrial
    ? planSummary?.trialEndsAt
    : planSummary?.planExpiresAt || activeClasses[0]?.expires_at || null;

  const annualRenewalTotal = useMemo(
    () => activeClasses.reduce((sum, item) => sum + Number(item?.annual_price_cents || 0), 0),
    [activeClasses],
  );

  const billingCurrency = activeClasses[0]?.currency || "INR";
  const latestStartedAt = activeClasses[0]?.started_at || planSummary?.planStartedAt || null;
  const latestPromo = activeClasses.find((item) => item?.promo_code)?.promo_code || null;

  return (
    <section className="workspace-panel profile-panel billing-panel">
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end", marginBottom: 12 }}>
        <button type="button" className="secondary-button" onClick={onRefresh} disabled={!onRefresh || isLoading}>
          <FiRefreshCw />
          <span>{isLoading ? "Refreshing..." : "Refresh Plan"}</span>
        </button>
        <button type="button" className="secondary-button" onClick={onOpenSubscription} disabled={!onOpenSubscription}>
          <FiCreditCard />
          <span>Manage Subscription</span>
        </button>
      </div>

      <div className="profile-panel__grid">
        <article className="profile-panel__card">
          <div className="profile-panel__card-top">
            <strong>Current plan</strong>
            <span className={`progress-pill progress-pill--${planSummary?.isTrial ? "medium" : "low"}`}>
              {planSummary?.planCode || "FREE"}
              {planSummary?.isTrial ? " Trial" : " Paid"}
            </span>
          </div>

          <div className="profile-panel__summary-list">
            <div>
              <span>Billing period</span>
              <strong>{planSummary?.billingPeriod || "Annual"}</strong>
            </div>
            <div>
              <span>{planSummary?.isTrial ? "Trial ends" : "Renews on"}</span>
              <strong>{formatDateLabel(renewalDate)}</strong>
            </div>
            <div>
              <span>Auto-renew</span>
              <strong>{planSummary?.autoRenew ? "On" : "Off"}</strong>
            </div>
            <div>
              <span>Latest billing activity</span>
              <strong>{formatDateLabel(latestStartedAt, "Not available")}</strong>
            </div>
          </div>

          {latestPromo ? (
            <div className="profile-panel__success" role="status">
              <FiCheckCircle />
              <span>Promo applied: {latestPromo}</span>
            </div>
          ) : null}
        </article>

        <article className="profile-panel__card">
          <div className="profile-panel__card-top">
            <strong>Usage this cycle</strong>
            <span className="progress-pill progress-pill--neutral">{usageRows.length} tracked</span>
          </div>

          {usageRows.length === 0 ? (
            <p className="sidebar-note">Plan usage will appear here once you start using lessons, quizzes, uploads, or chat asks.</p>
          ) : (
            <div className="billing-panel__usage-list">
              {usageRows.map((item) => (
                <div key={item.key} className="billing-panel__usage-item">
                  <div className="billing-panel__usage-top">
                    <span>{item.label}</span>
                    <strong>
                      {item.used}/{item.limit || "∞"}
                    </strong>
                  </div>
                  <div className="billing-panel__meter" aria-hidden="true">
                    <span style={{ width: `${item.pct}%` }} />
                  </div>
                  <small>{item.limit > 0 ? `${item.remaining} remaining this cycle` : "Unlimited on current plan"}</small>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="profile-panel__card">
          <div className="profile-panel__card-top">
            <strong>Class subscriptions</strong>
            <span className="progress-pill progress-pill--neutral">{activeClasses.length} active</span>
          </div>

          <div className="profile-panel__summary-list">
            <div>
              <span>Estimated annual renewal</span>
              <strong>{formatMoney(annualRenewalTotal, billingCurrency)}</strong>
            </div>
            <div>
              <span>Access scope</span>
              <strong>{activeClasses.length > 0 ? `${activeClasses.length} class plan${activeClasses.length === 1 ? "" : "s"}` : "No paid classes yet"}</strong>
            </div>
          </div>

          {activeClasses.length === 0 ? (
            <p className="sidebar-note">Add class access to unlock paid learning spaces and mentor workflows.</p>
          ) : (
            <div className="profile-panel__chip-list">
              {activeClasses.map((item) => (
                <div key={`${item.class_name}-${item.expires_at || "active"}`} className="profile-panel__chip">
                  <span>{item.class_name}</span>
                  <small>
                    {formatMoney(item.annual_price_cents, item.currency)}
                    {item.expires_at ? ` · Expires ${formatDateLabel(item.expires_at)}` : ""}
                    {item.auto_renew ? " · auto-renew" : ""}
                  </small>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="profile-panel__card">
          <div className="profile-panel__card-top">
            <strong>Included access</strong>
            <span className="progress-pill progress-pill--neutral">{(planSummary?.entitlements || []).length} features</span>
          </div>

          {(planSummary?.entitlements || []).length === 0 ? (
            <p className="sidebar-note">Feature access details will appear here once the current plan is loaded.</p>
          ) : (
            <div className="profile-panel__entitlement-list">
              {(planSummary?.entitlements || []).map((item) => (
                <div key={item.feature_key} className={`profile-panel__entitlement${item.enabled ? " is-enabled" : ""}`}>
                  <div>
                    <strong>{formatEntitlementLabel(item.feature_key)}</strong>
                    {item.hint ? <small className="billing-panel__hint">{item.hint}</small> : null}
                  </div>
                  <FiCheckCircle />
                </div>
              ))}
            </div>
          )}

          <div className="billing-panel__cta-row">
            <button type="button" className="primary-button" onClick={onOpenSubscription} disabled={!onOpenSubscription}>
              <FiZap />
              <span>Upgrade Classes</span>
            </button>
            <span className="sidebar-note">Use Manage Subscription to add or change class access at any time.</span>
          </div>
        </article>
      </div>
    </section>
  );
}
