import { useCallback, useState } from "react";
import { buildUsageLimitState } from "../utils/chatPanelSelectors";
import { apiFetch as defaultApiFetch } from "../services/api";

/**
 * Manages plan summary state and the usage-limit helper derived from it.
 *
 * @param {Object} opts
 * @param {Function} [opts.apiFetch] - injectable fetch helper (defaults to the real apiFetch)
 *
 * @returns {{
 *   planSummary: Object|null,
 *   loadPlanSummary: () => Promise<void>,
 *   getUsageLimitState: (action: string) => { blocked: boolean, used: number, limit: number, remaining: number },
 * }}
 */
export function usePlanSummary({ apiFetch = defaultApiFetch } = {}) {
  const [planSummary, setPlanSummary] = useState(null);

  const loadPlanSummary = useCallback(async () => {
    try {
      const res = await apiFetch("/plan/me");
      if (!res.ok) return;
      const data = await res.json();
      const plan = data?.plan;
      const usage = data?.usage;
      if (!plan || !usage) return;

      setPlanSummary({
        planCode: String(plan.plan_code || "free").toUpperCase(),
        isTrial: Boolean(plan.is_trial),
        autoRenew: Boolean(plan.auto_renew),
        planStartedAt: plan.plan_started_at || null,
        planExpiresAt: plan.plan_expires_at || null,
        trialEndsAt: plan.trial_ends_at || null,
        billingPeriod: String(plan.billing_period || "Annual"),
        usage,
        limits: plan.limits || {},
        entitlements: Array.isArray(plan.entitlements) ? plan.entitlements : [],
        classes: Array.isArray(plan.classes) ? plan.classes : [],
      });
    } catch (err) {
      console.error("Failed to load plan summary", err);
    }
  }, [apiFetch]);

  const getUsageLimitState = useCallback(
    (action) => buildUsageLimitState(planSummary, action),
    [planSummary]
  );

  return { planSummary, loadPlanSummary, getUsageLimitState };
}
