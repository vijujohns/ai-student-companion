import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { usePlanSummary } from "../../../frontend/src/hooks/usePlanSummary";

function makeApiFetch(plan, usage, { ok = true } = {}) {
  return vi.fn(async () => ({
    ok,
    json: async () => ({ plan, usage }),
  }));
}

describe("usePlanSummary", () => {
  it("initialises with null planSummary", () => {
    const { result } = renderHook(() => usePlanSummary());
    expect(result.current.planSummary).toBeNull();
    expect(typeof result.current.loadPlanSummary).toBe("function");
    expect(typeof result.current.getUsageLimitState).toBe("function");
  });

  it("loadPlanSummary populates planSummary from API response", async () => {
    const fakePlan = {
      plan_code: "pro",
      is_trial: false,
      limits: { ask_count: 100 },
      entitlements: [{ feature_key: "basic_lessons", enabled: true }],
      classes: [{ class_name: "Class 8", status: "ACTIVE" }],
    };
    const fakeUsage = { ask_count: 5 };
    const apiFetch = makeApiFetch(fakePlan, fakeUsage);
    const { result } = renderHook(() => usePlanSummary({ apiFetch }));

    await act(async () => {
      await result.current.loadPlanSummary();
    });

    expect(result.current.planSummary).toEqual({
      planCode: "PRO",
      isTrial: false,
      autoRenew: false,
      planStartedAt: null,
      planExpiresAt: null,
      trialEndsAt: null,
      billingPeriod: "Annual",
      usage: fakeUsage,
      limits: fakePlan.limits,
      entitlements: fakePlan.entitlements,
      classes: fakePlan.classes,
    });
  });

  it("getUsageLimitState returns blocked=false when no plan loaded", () => {
    const { result } = renderHook(() => usePlanSummary());
    const state = result.current.getUsageLimitState("ask");
    expect(state.blocked).toBe(false);
    expect(state.used).toBe(0);
  });

  it("getUsageLimitState returns blocked=true when usage meets limit", async () => {
    const fakePlan = { plan_code: "free", is_trial: true, limits: { ask_count: 10 } };
    const fakeUsage = { ask_count: 10 };
    const apiFetch = makeApiFetch(fakePlan, fakeUsage);
    const { result } = renderHook(() => usePlanSummary({ apiFetch }));

    await act(async () => {
      await result.current.loadPlanSummary();
    });

    const state = result.current.getUsageLimitState("ask");
    expect(state.blocked).toBe(true);
    expect(state.used).toBe(10);
    expect(state.limit).toBe(10);
    expect(state.remaining).toBe(0);
  });

  it("loadPlanSummary does nothing when response is not ok", async () => {
    const apiFetch = makeApiFetch(null, null, { ok: false });
    const { result } = renderHook(() => usePlanSummary({ apiFetch }));

    await act(async () => {
      await result.current.loadPlanSummary();
    });

    expect(result.current.planSummary).toBeNull();
  });
});
