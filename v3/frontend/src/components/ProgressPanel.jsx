import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  FiActivity,
  FiAward,
  FiBarChart2,
  FiBookOpen,
  FiClock,
  FiEdit,
  FiMoreVertical,
  FiRefreshCw,
  FiZap,
} from "react-icons/fi";
import { apiFetch, parseApiError } from "../services/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtTime(seconds) {
  if (!seconds || seconds < 60) return `${seconds || 0}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function MasteryBar({ pct }) {
  const color =
    pct >= 75 ? "#50c878" : pct >= 50 ? "#f5a623" : "#f1607b";
  return (
    <div className="mastery-bar-track">
      <div
        className="mastery-bar-fill"
        style={{ width: `${Math.min(pct, 100)}%`, background: color }}
      />
    </div>
  );
}

function MiniTrendChart({ scores = [], label = "Assessment trend" }) {
  if (!Array.isArray(scores) || scores.length < 2) return null;
  const safeScores = scores.map((value) => Math.max(0, Math.min(100, Number(value) || 0)));
  const width = 120;
  const height = 32;
  const stepX = safeScores.length > 1 ? width / (safeScores.length - 1) : width;
  const points = safeScores
    .map((score, index) => {
      const x = Math.round(index * stepX);
      const y = Math.round(height - (score / 100) * (height - 4) - 2);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg
      role="img"
      aria-label={label}
      width="120"
      height="32"
      viewBox={`0 0 ${width} ${height}`}
      className="progress-mini-trend"
    >
      <polyline
        fill="none"
        stroke="#6c63ff"
        strokeWidth="2"
        points={points}
      />
    </svg>
  );
}

function downloadTextFile(fileName, content, mimeType = "text/plain;charset=utf-8") {
  if (typeof window === "undefined" || !window.URL?.createObjectURL) {
    throw new Error("Export is not available in this browser.");
  }
  const blob = new Blob([content], { type: mimeType });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  window.URL.revokeObjectURL(url);
}

function StatCard({ icon, label, value, sub }) {
  return (
    <div className="progress-stat-card">
      <div className="progress-stat-card__icon">{icon}</div>
      <div className="progress-stat-card__body">
        <div className="progress-stat-card__value">{value}</div>
        <div className="progress-stat-card__label">{label}</div>
        {sub && <div className="progress-stat-card__sub">{sub}</div>}
      </div>
    </div>
  );
}

const ACTIVITY_ICON = {
  lesson:     <FiBookOpen />,
  quiz:       <FiEdit />,
  flashcard:  <FiZap />,
  chat:       <FiActivity />,
  assessment: <FiBarChart2 />,
};

function buildRecentActivityAction(item) {
  if (!item?.activity_type) return null;

  const actionTab = item.activity_type === "flashcard" ? "flashcards" : item.activity_type;
  const chapterHint = item.subject || item.chapter || "";
  const contextHint = item.subject && item.chapter && item.subject !== item.chapter
    ? `${item.subject} — ${item.chapter}`
    : item.subject || item.chapter || item.activity_type;
  const ctaLabel = {
    lesson: "Open Lesson",
    quiz: "Retry Quiz",
    assessment: "Review Assessment",
    flashcard: "Open Flashcards",
    chat: "Open Chat",
  }[item.activity_type] || "Open Activity";

  return {
    ...item,
    id: `recent-${String(item.activity_type || "item")}-${String(chapterHint || "general")}`
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-"),
    action_tab: actionTab,
    chapter_hint: chapterHint,
    context_hint: contextHint,
    cta_label: ctaLabel,
  };
}

function buildTopSubjectAction(item) {
  const subjectLabel = item?.subject || item?.chapter || "";
  if (!subjectLabel) return null;

  return {
    ...item,
    id: `time-subject-${String(subjectLabel).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
    action_tab: "lesson",
    chapter_hint: subjectLabel,
    context_hint: `Continue learning in ${subjectLabel} based on your recent study time.`,
    cta_label: `Open ${subjectLabel} Lesson`,
  };
}

function ActivityRow({ item, onAction = null }) {
  const icon = ACTIVITY_ICON[item.activity_type] || <FiActivity />;
  const label =
    item.subject && item.chapter && item.subject !== item.chapter
      ? `${item.subject} — ${item.chapter}`
      : item.subject || item.chapter || item.activity_type;
  const time = item.logged_at ? new Date(item.logged_at).toLocaleDateString() : "";
  const action = buildRecentActivityAction(item);
  return (
    <div className="progress-activity-row">
      <span className="progress-activity-row__icon">{icon}</span>
      <span className="progress-activity-row__label">{label}</span>
      {item.duration_seconds > 0 && (
        <span className="progress-activity-row__duration">{fmtTime(item.duration_seconds)}</span>
      )}
      <span className="progress-activity-row__date">{time}</span>
      {action?.cta_label ? (
        <button
          type="button"
          className="secondary-button progress-plan-item__action"
          onClick={() => onAction?.(action)}
          disabled={!onAction}
        >
          {action.cta_label}
        </button>
      ) : null}
    </div>
  );
}

function getPlanStatusLabel(step) {
  if (step?.status_label) return step.status_label;
  if (step?.completed || step?.status === "done") return "Done";
  if (step?.status === "next") return "Next up";
  return "Coming up";
}

function getPlanStatusTone(step) {
  if (step?.completed || step?.status === "done") return "low";
  if (step?.status === "next") return "medium";
  return "neutral";
}

function normalizeReminderSettings(settings) {
  const mutedIds = Array.isArray(settings?.muted_ids) ? settings.muted_ids.filter(Boolean) : [];
  return {
    enabled: settings?.enabled !== false,
    frequency: settings?.frequency || "daily",
    muted_ids: mutedIds,
    delivery_scope: settings?.delivery_scope || "local-only",
  };
}

function buildHistoryDeltaSummary(currentWeek, previousWeek) {
  if (!currentWeek || !previousWeek) return [];
  const goalDelta = Number(currentWeek.goal_completed || 0) - Number(previousWeek.goal_completed || 0);
  const stepDelta = Number(currentWeek.completed_steps || 0) - Number(previousWeek.completed_steps || 0);
  const items = [];

  if (goalDelta !== 0) {
    items.push(`${goalDelta > 0 ? "+" : ""}${goalDelta} goals`);
  }
  if (stepDelta !== 0) {
    items.push(`${stepDelta > 0 ? "+" : ""}${stepDelta} steps`);
  }

  return items;
}

function parseDueDateValue(value) {
  const rawValue = String(value || "").trim();
  if (!rawValue) return null;
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(rawValue) ? `${rawValue}T00:00:00` : rawValue;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function getAssignmentDueMeta(dueLabel) {
  if (!dueLabel) {
    return { label: "", tone: "neutral", bucket: "none", sortTime: Number.MAX_SAFE_INTEGER };
  }

  const parsed = parseDueDateValue(dueLabel);
  if (!parsed) {
    return { label: "Scheduled", tone: "neutral", bucket: "scheduled", sortTime: Number.MAX_SAFE_INTEGER - 1 };
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dueDate = new Date(parsed);
  dueDate.setHours(0, 0, 0, 0);
  const diffDays = Math.round((dueDate.getTime() - today.getTime()) / 86400000);

  if (diffDays < 0) {
    return { label: "Overdue", tone: "high", bucket: "overdue", sortTime: dueDate.getTime() };
  }
  if (diffDays <= 3) {
    return { label: "Due soon", tone: "medium", bucket: "due-soon", sortTime: dueDate.getTime() };
  }
  return { label: "Scheduled", tone: "low", bucket: "scheduled", sortTime: dueDate.getTime() };
}

function matchesAssignmentFilter(item, filterValue = "all") {
  const status = String(item?.status || "assigned").toLowerCase();
  const dueMeta = getAssignmentDueMeta(item?.due_label);

  switch (filterValue) {
    case "open":
      return status === "assigned";
    case "completed":
      return status === "completed";
    case "dismissed":
      return status === "dismissed";
    case "overdue":
      return status === "assigned" && dueMeta.bucket === "overdue";
    case "due-soon":
      return status === "assigned" && dueMeta.bucket === "due-soon";
    default:
      return true;
  }
}

function matchesAssignmentSearch(item, query = "") {
  const searchValue = String(query || "").trim().toLowerCase();
  if (!searchValue) return true;
  const haystack = [item?.title, item?.description, item?.chapter_hint, item?.due_label]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(searchValue);
}

function compareAssignmentsByPriority(left, right) {
  const leftDueMeta = getAssignmentDueMeta(left?.due_label);
  const rightDueMeta = getAssignmentDueMeta(right?.due_label);
  const leftRank = leftDueMeta.bucket === "overdue" ? 0 : leftDueMeta.bucket === "due-soon" ? 1 : 2;
  const rightRank = rightDueMeta.bucket === "overdue" ? 0 : rightDueMeta.bucket === "due-soon" ? 1 : 2;

  if (leftRank !== rightRank) return leftRank - rightRank;
  if (leftDueMeta.sortTime !== rightDueMeta.sortTime) return leftDueMeta.sortTime - rightDueMeta.sortTime;
  return String(left?.title || "").localeCompare(String(right?.title || ""));
}

function matchesSubjectFilter(values, subjectFilter = "") {
  const filterValue = String(subjectFilter || "").trim().toLowerCase();
  if (!filterValue) return true;
  const haystack = (Array.isArray(values) ? values : [values]).filter(Boolean).join(" ").toLowerCase();
  return haystack.includes(filterValue);
}

function isWithinRange(dateValue, range = "all") {
  if (!dateValue || !range || range === "all") return true;
  const parsed = parseDueDateValue(dateValue) || new Date(dateValue);
  if (!parsed || Number.isNaN(parsed.getTime())) return false;

  const now = new Date();
  const start = new Date(now);
  if (range === "7d") {
    start.setDate(now.getDate() - 7);
  } else if (range === "30d") {
    start.setDate(now.getDate() - 30);
  } else if (range === "90d") {
    start.setDate(now.getDate() - 90);
  } else {
    return true;
  }
  return parsed >= start && parsed <= now;
}

function sortAssignmentsForMode(items, sortMode = "priority") {
  const list = [...(items || [])];
  if (sortMode === "title") {
    return list.sort((left, right) => String(left?.title || "").localeCompare(String(right?.title || "")));
  }
  if (sortMode === "due-date") {
    return list.sort((left, right) => getAssignmentDueMeta(left?.due_label).sortTime - getAssignmentDueMeta(right?.due_label).sortTime);
  }
  return list.sort(compareAssignmentsByPriority);
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ProgressPanel({ planSummary = null, onPlanAction = null, isActive = true }) {
  const [dashboard, setDashboard] = useState(null);
  const [insights, setInsights] = useState({
    headline: "",
    recommendations: [],
    badges: [],
  });
  const [studyPlan, setStudyPlan] = useState({
    headline: "",
    focus_subject: "",
    schedule: [],
  });
  const [preferences, setPreferences] = useState({
    preferred_language: typeof window !== "undefined" ? localStorage.getItem("preferred_language") || "en" : "en",
    reminder_settings: normalizeReminderSettings(),
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedSubject, setExpandedSubject] = useState(null);
  const [savingItemKey, setSavingItemKey] = useState("");
  const [savingReminderPrefs, setSavingReminderPrefs] = useState(false);
  const [assignmentSearch, setAssignmentSearch] = useState("");
  const [assignmentFilter, setAssignmentFilter] = useState("all");
  const [assignmentSort, setAssignmentSort] = useState("priority");
  const [reportSubject, setReportSubject] = useState("");
  const [reportRange, setReportRange] = useState("all");
  const [reminderSeverity, setReminderSeverity] = useState("all");
  const [activeTab, setActiveTab] = useState("overview");
  const [reportMenuOpen, setReportMenuOpen] = useState(false);
  const wasActiveRef = useRef(isActive);
  const reportMenuRef = useRef(null);
  const currentUsername = typeof window !== "undefined" ? localStorage.getItem("username") || "" : "";

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [dashboardResult, insightsResult, studyPlanResult, preferencesResult] = await Promise.allSettled([
        apiFetch("/progress/dashboard"),
        apiFetch("/progress/insights"),
        apiFetch("/progress/study-plan"),
        apiFetch("/preferences"),
      ]);

      if (dashboardResult.status !== "fulfilled" || !dashboardResult.value.ok) {
        throw new Error("Failed to load progress data.");
      }

      const dashboardJson = await dashboardResult.value.json();
      setDashboard(dashboardJson?.data || dashboardJson);

      if (insightsResult.status === "fulfilled" && insightsResult.value.ok) {
        const insightsJson = await insightsResult.value.json();
        setInsights(insightsJson?.data || insightsJson);
      } else {
        setInsights({ headline: "", recommendations: [], badges: [] });
      }

      if (studyPlanResult.status === "fulfilled" && studyPlanResult.value.ok) {
        const studyPlanJson = await studyPlanResult.value.json();
        setStudyPlan(studyPlanJson?.data || studyPlanJson);
      } else {
        setStudyPlan({
          headline: "",
          focus_subject: "",
          schedule: [],
          goal_summary: { completed: 0, total: 0 },
          targets: [],
          history: {},
        });
      }

      if (preferencesResult.status === "fulfilled" && preferencesResult.value.ok) {
        const prefJson = await preferencesResult.value.json();
        const prefData = prefJson?.data || prefJson;
        setPreferences({
          preferred_language: prefData?.preferred_language || "en",
          reminder_settings: normalizeReminderSettings(prefData?.reminder_settings),
        });
      } else {
        setPreferences((current) => ({
          preferred_language: current?.preferred_language || "en",
          reminder_settings: normalizeReminderSettings(current?.reminder_settings),
        }));
      }
    } catch (err) {
      setError(err?.message || "Failed to load progress data.");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleTogglePlanItem = useCallback(async (item, itemType) => {
    if (!item?.id) return;
    const savingKey = `${itemType}:${item.id}`;
    setSavingItemKey(savingKey);
    try {
      const res = await apiFetch(`/progress/study-plan/items/${encodeURIComponent(item.id)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_type: itemType, completed: !item.completed }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not update this study plan item."));
      }
      await loadDashboard();
    } catch (err) {
      setError(err?.message || "Could not update this study plan item.");
    } finally {
      setSavingItemKey("");
    }
  }, [loadDashboard]);

  const handleExportReport = useCallback((format = "json") => {
    const currentWeek = studyPlan?.history?.current_week || null;
    const previousWeek = studyPlan?.history?.previous_week || null;
    const historyDeltas = buildHistoryDeltaSummary(currentWeek, previousWeek);
    const filteredDashboard = {
      ...(dashboard || {}),
      top_subjects: (dashboard?.top_subjects || []).filter((item) => matchesSubjectFilter(item?.subject, reportSubject)),
      recent_activity: (dashboard?.recent_activity || []).filter((item) => matchesSubjectFilter([item?.subject, item?.chapter], reportSubject) && isWithinRange(item?.logged_at, reportRange)),
      mastery_summary: (dashboard?.mastery_summary || []).filter((item) => matchesSubjectFilter([item?.subject, ...(item?.chapters || []).map((chapter) => chapter?.chapter)], reportSubject)),
      assignments: (dashboard?.assignments || []).filter((item) => matchesSubjectFilter([item?.title, item?.description, item?.chapter_hint], reportSubject) && isWithinRange(item?.due_label || item?.created_at || item?.completed_at, reportRange)),
    };
    const filteredStudyPlan = {
      ...(studyPlan || {}),
      targets: (studyPlan?.targets || []).filter((item) => matchesSubjectFilter([item?.label, item?.chapter_hint], reportSubject)),
      schedule: (studyPlan?.schedule || []).filter((item) => matchesSubjectFilter([item?.title, item?.description, item?.chapter_hint], reportSubject)),
    };
    const payload = {
      generated_at: new Date().toISOString(),
      filters: {
        subject: reportSubject || null,
        range: reportRange,
      },
      dashboard: filteredDashboard,
      insights,
      study_plan: filteredStudyPlan,
      plan_summary: planSummary,
      preferences,
      report_summary: {
        streak_days: dashboard?.streak_days || 0,
        study_time_seconds: dashboard?.total_study_seconds || 0,
        assignment_open_count: (filteredDashboard.assignments || []).filter((item) => item?.status !== "completed").length,
        history_deltas: historyDeltas,
        filtered_subject: reportSubject || "All subjects",
        report_range: reportRange,
      },
    };

    if (format === "csv") {
      const reportAssessment = dashboard?.assessment_summary || {};
      const rows = [
        ["section", "label", "value"],
        ["filter", "subject", reportSubject || "All subjects"],
        ["filter", "range", reportRange],
        ["summary", "study_time_seconds", dashboard?.total_study_seconds || 0],
        ["summary", "streak_days", dashboard?.streak_days || 0],
        ["summary", "reminder_frequency", preferences?.reminder_settings?.frequency || "daily"],
        ["assessment", "average_score_pct", reportAssessment?.average_score_pct || 0],
        ["assessment", "best_score_pct", reportAssessment?.best_score_pct || 0],
        ["assessment", "latest_score_pct", reportAssessment?.latest_score_pct || 0],
        ["history", "week_over_week", historyDeltas.join(" · ") || studyPlan?.history?.comparison?.summary || ""],
        ...((filteredStudyPlan.targets || []).map((target) => ["goal", target.label || target.id, `${target.current || 0}/${target.target || 0} ${target.unit || ""}`])),
        ...((filteredDashboard.assignments || []).map((item) => ["assignment", item.title || item.id, item.status || "assigned"])),
      ];
      const csv = rows.map((row) => row.map((value) => `"${String(value ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
      downloadTextFile("progress-report.csv", csv, "text/csv;charset=utf-8");
      return;
    }

    downloadTextFile("progress-report.json", JSON.stringify(payload, null, 2), "application/json;charset=utf-8");
  }, [dashboard, insights, planSummary, preferences, reportRange, reportSubject, studyPlan]);

  const handlePrintReport = useCallback(() => {
    if (typeof window !== "undefined" && typeof window.print === "function") {
      window.print();
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    if (isActive && !wasActiveRef.current) {
      loadDashboard();
    }
    wasActiveRef.current = isActive;
  }, [isActive, loadDashboard]);

  useEffect(() => {
    if (!reportMenuOpen) return undefined;

    const handlePointerDown = (event) => {
      if (reportMenuRef.current && !reportMenuRef.current.contains(event.target)) {
        setReportMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [reportMenuOpen]);

  const handleReminderSettingsUpdate = useCallback(async (nextReminderSettings) => {
    setSavingReminderPrefs(true);
    setError("");
    try {
      const res = await apiFetch("/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          preferred_language: preferences?.preferred_language || "en",
          reminder_settings: nextReminderSettings,
        }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not update reminder settings."));
      }
      const json = await res.json();
      const payload = json?.data || json;
      setPreferences({
        preferred_language: payload?.preferred_language || preferences?.preferred_language || "en",
        reminder_settings: normalizeReminderSettings(payload?.reminder_settings || nextReminderSettings),
      });
    } catch (err) {
      setError(err?.message || "Could not update reminder settings.");
    } finally {
      setSavingReminderPrefs(false);
    }
  }, [preferences]);

  const handleAssignmentStatusUpdate = useCallback(async (item, nextStatus) => {
    if (!item?.id || !currentUsername) return;
    setSavingItemKey(`assignment:${item.id}`);
    setError("");
    try {
      const res = await apiFetch(`/students/${encodeURIComponent(currentUsername)}/assignments/${encodeURIComponent(item.id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not update this assignment."));
      }
      await loadDashboard();
    } catch (err) {
      setError(err?.message || "Could not update this assignment.");
    } finally {
      setSavingItemKey("");
    }
  }, [currentUsername, loadDashboard]);

  if (loading) {
    return (
      <div className="progress-panel workspace-panel">
        <div className="progress-panel__loading">
          <FiRefreshCw className="spin" />
          <span>Loading your progress…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="progress-panel workspace-panel">
        <div className="progress-panel__error">
          <p>{error}</p>
          <button className="btn-secondary" onClick={loadDashboard}>Retry</button>
        </div>
      </div>
    );
  }

  const totalSeconds = dashboard?.total_study_seconds || 0;
  const streak = dashboard?.streak_days || 0;
  const totals = dashboard?.totals || {};
  const topSubjects = dashboard?.top_subjects || [];
  const recentActivity = dashboard?.recent_activity || [];
  const masterySummary = dashboard?.mastery_summary || [];
  const assessmentSummary = dashboard?.assessment_summary || {};
  const insightHeadline = insights?.headline || "";
  const recommendations = insights?.recommendations || [];
  const badges = insights?.badges || [];
  const notifications = insights?.notifications || [];
  const assignments = dashboard?.assignments || [];
  const studyPlanHeadline = studyPlan?.headline || "";
  const studyPlanSchedule = studyPlan?.schedule || [];
  const goalSummary = studyPlan?.goal_summary || { completed: 0, total: 0 };
  const goalTargets = studyPlan?.targets || [];
  const studyPlanHistory = studyPlan?.history || {};
  const currentWeek = studyPlanHistory?.current_week || null;
  const previousWeek = studyPlanHistory?.previous_week || null;
  const historyComparison = studyPlanHistory?.comparison || {};
  const historyDeltaItems = buildHistoryDeltaSummary(currentWeek, previousWeek);
  const reminderSettings = normalizeReminderSettings(preferences?.reminder_settings);
  const visibleNotifications = notifications.filter((item) => {
    if (!reminderSettings.enabled || reminderSettings.frequency === "off") return false;
    if (reminderSettings.muted_ids.includes(item?.id)) return false;
    if (reminderSettings.frequency === "important-only") {
      return ["high", "critical"].includes(String(item?.severity || "").toLowerCase());
    }
    return true;
  }).filter((item) => reminderSeverity === "all" || String(item?.severity || "").toLowerCase() === reminderSeverity);
  const completedPlanSteps = studyPlanSchedule.filter((step) => step?.completed).length;
  const visibleAssignments = sortAssignmentsForMode(
    [...assignments]
      .filter((item) => matchesAssignmentFilter(item, assignmentFilter))
      .filter((item) => matchesAssignmentSearch(item, assignmentSearch)),
    assignmentSort,
  );
  const hasOverviewContent = goalTargets.length > 0
    || Boolean(studyPlanHeadline)
    || studyPlanSchedule.length > 0
    || Boolean(currentWeek || previousWeek);
  const hasActivityContent = masterySummary.length > 0 || topSubjects.length > 0 || recentActivity.length > 0;
  const hasInsightsContent = Boolean(insightHeadline) || recommendations.length > 0 || badges.length > 0;
  const hasRemindersContent = Boolean(reminderSettings) || visibleNotifications.length > 0 || assignments.length > 0;
  const progressTabs = [
    {
      id: "overview",
      label: "Overview",
      hint: "Goals, weekly plan, and summary",
      count: [goalTargets.length > 0, Boolean(studyPlanHeadline || studyPlanSchedule.length > 0), Boolean(currentWeek || previousWeek)].filter(Boolean).length,
    },
    {
      id: "activity",
      label: "Activity",
      hint: "Mastery, study time, and recent work",
      count: [masterySummary.length > 0, topSubjects.length > 0, recentActivity.length > 0].filter(Boolean).length,
    },
    {
      id: "insights",
      label: "Insights",
      hint: "AI guidance and coaching signals",
      count: [Boolean(insightHeadline), recommendations.length > 0, badges.length > 0].filter(Boolean).length,
    },
    {
      id: "reminders",
      label: "Reminders",
      hint: "Alerts and mentor tasks",
      count: [visibleNotifications.length > 0, assignments.length > 0].filter(Boolean).length,
    },
  ];

  return (
    <div className="progress-panel workspace-panel">
      <div className="progress-panel__body">
        <section className="progress-section">
          <div className="progress-toolbar-card">
            <div className="progress-toolbar-card__header">
              <div>
                <div className="progress-plan-item__title">Progress workspace</div>
                <p className="progress-toolbar-card__copy">
                  {studyPlan?.focus_subject
                    ? `Focus this week: ${studyPlan.focus_subject}. Switch tabs to review goals, activity, insights, and reminders without the clutter.`
                    : "Switch tabs to review goals, activity, insights, and reminders without the clutter."}
                </p>
              </div>
              <span className="progress-pill progress-pill--neutral">{reportSubject ? `Filtered: ${reportSubject}` : "All subjects"}</span>
            </div>
            <div className="progress-toolbar__controls">
              <label className="progress-toolbar__field progress-toolbar__field--wide">
                <span>Report subject</span>
                <input
                  className="progress-toolbar__input"
                  aria-label="Report subject"
                  type="text"
                  value={reportSubject}
                  onChange={(event) => setReportSubject(event.target.value)}
                  placeholder="All subjects"
                />
              </label>
              <label className="progress-toolbar__field">
                <span>Report range</span>
                <div className="workspace-select-wrap workspace-select-wrap--compact">
                  <select
                    aria-label="Report range"
                    value={reportRange}
                    onChange={(event) => setReportRange(event.target.value)}
                  >
                    <option value="all">All time</option>
                    <option value="7d">Last 7 days</option>
                    <option value="30d">Last 30 days</option>
                    <option value="90d">Last 90 days</option>
                  </select>
                </div>
              </label>
              <label className="progress-toolbar__field">
                <span>Reminder severity</span>
                <div className="workspace-select-wrap workspace-select-wrap--compact">
                  <select
                    aria-label="Reminder severity"
                    value={reminderSeverity}
                    onChange={(event) => setReminderSeverity(event.target.value)}
                  >
                    <option value="all">All</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </label>
              <div className="progress-toolbar__actions">
                <button
                  type="button"
                  className="icon-button icon-button--ghost"
                  onClick={loadDashboard}
                  title="Refresh progress"
                  aria-label="Refresh progress"
                >
                  <FiRefreshCw />
                </button>
                <div className={`progress-action-menu${reportMenuOpen ? " is-open" : ""}`} ref={reportMenuRef}>
                  <button
                    type="button"
                    className="secondary-button progress-action-menu__trigger"
                    onClick={() => setReportMenuOpen((open) => !open)}
                    aria-label="Open report actions"
                    aria-haspopup="menu"
                    aria-expanded={reportMenuOpen}
                    title="Open report actions"
                  >
                    <span>Report actions</span>
                    <FiMoreVertical />
                  </button>
                  {reportMenuOpen ? (
                    <div className="progress-action-menu__panel" role="menu" aria-label="Report actions menu">
                      <button
                        type="button"
                        role="menuitem"
                        className="progress-action-menu__item"
                        onClick={() => {
                          setReportMenuOpen(false);
                          handleExportReport("json");
                        }}
                      >
                        Export Report JSON
                      </button>
                      <button
                        type="button"
                        role="menuitem"
                        className="progress-action-menu__item"
                        onClick={() => {
                          setReportMenuOpen(false);
                          handleExportReport("csv");
                        }}
                      >
                        Export Report CSV
                      </button>
                      <button
                        type="button"
                        role="menuitem"
                        className="progress-action-menu__item"
                        onClick={() => {
                          setReportMenuOpen(false);
                          handlePrintReport();
                        }}
                      >
                        Print / Save PDF
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
            <div className="progress-tab-list" role="tablist" aria-label="Progress sections">
              {progressTabs.map((tab) => (
                <button
                  key={tab.id}
                  id={`progress-tab-${tab.id}`}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  aria-controls={`progress-panel-${tab.id}`}
                  className={`progress-tab${activeTab === tab.id ? " is-active" : ""}`}
                  onClick={() => {
                    setActiveTab(tab.id);
                    setReportMenuOpen(false);
                  }}
                >
                  <span className="progress-tab__top">
                    <span className="progress-tab__label">{tab.label}</span>
                    {tab.count > 0 ? <span className="progress-tab__count">{tab.count}</span> : null}
                  </span>
                  <span className="progress-tab__meta">{tab.hint}</span>
                </button>
              ))}
            </div>
          </div>
        </section>
        {/* Stats row */}
        <section className="progress-stats-grid">
          <StatCard
            icon={<FiClock />}
            label="Study Time"
            value={fmtTime(totalSeconds)}
            sub="Total logged"
          />
          <StatCard
            icon={<FiZap />}
            label="Day Streak"
            value={`${streak}🔥`}
            sub={streak === 0 ? "Start today!" : "Keep it up!"}
          />
          <StatCard
            icon={<FiEdit />}
            label="Quizzes"
            value={totals.quizzes || 0}
          />
          <StatCard
            icon={<FiBookOpen />}
            label="Lessons"
            value={totals.lessons || 0}
          />
          {Number(assessmentSummary?.attempt_count || 0) > 0 && (
            <StatCard
              icon={<FiAward />}
              label="Assessment Avg"
              value={`${assessmentSummary.average_score_pct || 0}%`}
              sub={
                <>
                  <span>
                    {`Best ${assessmentSummary.best_score_pct || 0}% · Latest ${assessmentSummary.latest_score_pct || 0}%${assessmentSummary.latest_subject ? ` in ${assessmentSummary.latest_subject}` : ""}`}
                  </span>
                  {(Array.isArray(assessmentSummary.recent_scores) && assessmentSummary.recent_scores.length > 0) && (
                    <>
                      <br />
                      <span>
                        {`Recent ${assessmentSummary.recent_scores.map((score) => `${score}%`).join(", ")}`}
                      </span>
                    </>
                  )}
                  {(Array.isArray(assessmentSummary.recent_scores) && assessmentSummary.recent_scores.length > 1) && (
                    <>
                      <br />
                      <MiniTrendChart scores={assessmentSummary.recent_scores} label="Assessment trend" />
                    </>
                  )}
                  {(Number(assessmentSummary.attempt_count || 0) > 0 || assessmentSummary.last_attempted_at) && (
                    <>
                      <br />
                      <span>
                        {Number(assessmentSummary.attempt_count || 0) > 0 ? `${assessmentSummary.attempt_count} attempts` : ""}
                        {Number(assessmentSummary.attempted_assessments || 0) > 0
                          ? `${Number(assessmentSummary.attempt_count || 0) > 0 ? " · " : ""}${assessmentSummary.attempted_assessments} papers`
                          : ""}
                        {assessmentSummary.last_attempted_at
                          ? `${Number(assessmentSummary.attempt_count || 0) > 0 || Number(assessmentSummary.attempted_assessments || 0) > 0 ? " · " : ""}Last ${String(assessmentSummary.last_attempted_at).split("T")[0]}`
                          : ""}
                      </span>
                    </>
                  )}
                </>
              }
            />
          )}
        </section>

        {activeTab === "insights" && (
          <div
            className="progress-tab-panel"
            role="tabpanel"
            id="progress-panel-insights"
            aria-labelledby="progress-tab-insights"
          >
            <p className="progress-tab-panel__intro">Use this tab for the AI-generated summary, recommendations, and earned-badge progress.</p>

            {(insightHeadline || recommendations.length > 0 || badges.length > 0) ? (
              <section className="progress-section">
                <h4 className="progress-section__title">
                  <FiAward /> Smart Insights
                </h4>
                <div className="progress-insights-card">
                  {insightHeadline && (
                    <p className="progress-insights-card__headline">{insightHeadline}</p>
                  )}

                  {recommendations.length > 0 && (
                    <div className="progress-recommendation-list">
                      {recommendations.map((rec) => (
                        <div key={rec.id || rec.title} className="progress-recommendation-item">
                          <div className="progress-recommendation-item__body">
                            <div className="progress-recommendation-item__title">{rec.title}</div>
                            <div className="progress-recommendation-item__description">
                              {rec.description}
                            </div>
                            {rec.cta_label ? (
                              <button
                                type="button"
                                className="secondary-button progress-plan-item__action"
                                onClick={() => onPlanAction?.(rec)}
                                disabled={!onPlanAction}
                              >
                                {rec.cta_label}
                              </button>
                            ) : null}
                          </div>
                          {rec.priority && (
                            <span className={`progress-pill progress-pill--${rec.priority}`}>
                              {rec.priority}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {badges.length > 0 && (
                    <div className="progress-badge-list">
                      {badges.map((badge) => (
                        <div
                          key={badge.id || badge.label}
                          className={`progress-badge-item${badge.earned ? " is-earned" : ""}`}
                        >
                          <div className="progress-badge-item__top">
                            <span className="progress-badge-item__label">{badge.label}</span>
                            <span className="progress-badge-item__pct">{badge.progress_pct || 0}%</span>
                          </div>
                          <div className="progress-badge-item__description">{badge.description}</div>
                          <MasteryBar pct={badge.progress_pct || 0} />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            ) : (
              <div className="progress-plan-card">
                <p className="progress-plan-card__headline">No insight recommendations are available yet. Come back after a few more study sessions.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === "reminders" && (
          <div
            className="progress-tab-panel"
            role="tabpanel"
            id="progress-panel-reminders"
            aria-labelledby="progress-tab-reminders"
          >
            <p className="progress-tab-panel__intro">Keep up with reminders and mentor tasks in one focused view.</p>

            {(notifications.length > 0 || reminderSettings) && (
              <section className="progress-section">
                <h4 className="progress-section__title">
                  <FiActivity /> Reminders
                </h4>
                <div className="progress-plan-card" style={{ marginBottom: 12 }}>
                  <div className="progress-plan-item__top">
                    <div className="progress-plan-item__title">Reminder settings</div>
                    <span className={`progress-pill progress-pill--${reminderSettings.enabled ? "low" : "neutral"}`}>
                      {reminderSettings.enabled ? "Enabled" : "Muted"}
                    </span>
                  </div>
                  <p className="sidebar-note">
                    Reminder delivery is local-only and controlled by your stored preferences.
                  </p>
                  <div className="progress-toolbar__controls progress-toolbar__controls--dense">
                    <label className="progress-toolbar__field">
                      <span>Reminder frequency</span>
                      <div className="workspace-select-wrap workspace-select-wrap--compact">
                        <select
                          aria-label="Reminder frequency"
                          value={reminderSettings.frequency}
                          onChange={(e) =>
                            handleReminderSettingsUpdate({
                              ...reminderSettings,
                              enabled: true,
                              frequency: e.target.value,
                            })
                          }
                          disabled={savingReminderPrefs}
                        >
                          <option value="daily">Daily</option>
                          <option value="important-only">Important only</option>
                          <option value="weekly">Weekly</option>
                          <option value="off">Off</option>
                        </select>
                      </div>
                    </label>
                    <button
                      type="button"
                      className="secondary-button progress-plan-item__action"
                      onClick={() => handleReminderSettingsUpdate({ ...reminderSettings, enabled: !reminderSettings.enabled })}
                      disabled={savingReminderPrefs}
                    >
                      {reminderSettings.enabled ? "Pause reminders" : "Resume reminders"}
                    </button>
                  </div>
                </div>
                {visibleNotifications.length > 0 ? (
                  <div className="progress-recommendation-list">
                    {visibleNotifications.map((item) => (
                      <div key={item.id || item.title} className="progress-recommendation-item">
                        <div className="progress-recommendation-item__body">
                          <div className="progress-recommendation-item__title">{item.title}</div>
                          <div className="progress-recommendation-item__description">{item.message}</div>
                          {item.cta_label ? (
                            <button
                              type="button"
                              className="secondary-button progress-plan-item__action"
                              onClick={() => onPlanAction?.(item)}
                              disabled={!onPlanAction}
                            >
                              {item.cta_label}
                            </button>
                          ) : null}
                          {item?.id ? (
                            <button
                              type="button"
                              className="secondary-button progress-plan-item__action"
                              onClick={() =>
                                handleReminderSettingsUpdate({
                                  ...reminderSettings,
                                  muted_ids: Array.from(new Set([...(reminderSettings.muted_ids || []), item.id])),
                                })
                              }
                              disabled={savingReminderPrefs}
                            >
                              Mute this reminder
                            </button>
                          ) : null}
                        </div>
                        {item.severity ? (
                          <span className={`progress-pill progress-pill--${item.severity}`}>
                            {item.severity}
                          </span>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="progress-plan-card">
                    <p className="progress-plan-card__headline">No active reminders are being shown with your current preference settings.</p>
                  </div>
                )}
              </section>
            )}

            {assignments.length > 0 && (
              <section className="progress-section">
                <h4 className="progress-section__title">
                  <FiBookOpen /> Mentor Assignments
                </h4>
                <div className="progress-plan-card" style={{ marginBottom: 12 }}>
                  <div className="progress-toolbar__controls progress-toolbar__controls--dense">
                    <label className="progress-toolbar__field progress-toolbar__field--wide">
                      <span>Search assignments</span>
                      <input
                        className="progress-toolbar__input"
                        type="text"
                        aria-label="Search assignments"
                        placeholder="Search assignments"
                        value={assignmentSearch}
                        onChange={(event) => setAssignmentSearch(event.target.value)}
                      />
                    </label>
                    <label className="progress-toolbar__field">
                      <span>Assignment filter</span>
                      <div className="workspace-select-wrap workspace-select-wrap--compact">
                        <select
                          aria-label="Assignment filter"
                          value={assignmentFilter}
                          onChange={(event) => setAssignmentFilter(event.target.value)}
                        >
                          <option value="all">All</option>
                          <option value="open">Open</option>
                          <option value="overdue">Overdue</option>
                          <option value="due-soon">Due soon</option>
                          <option value="completed">Completed</option>
                          <option value="dismissed">Dismissed</option>
                        </select>
                      </div>
                    </label>
                    <label className="progress-toolbar__field">
                      <span>Assignment sort</span>
                      <div className="workspace-select-wrap workspace-select-wrap--compact">
                        <select
                          aria-label="Assignment sort"
                          value={assignmentSort}
                          onChange={(event) => setAssignmentSort(event.target.value)}
                        >
                          <option value="priority">Priority</option>
                          <option value="due-date">Due date</option>
                          <option value="title">Title</option>
                        </select>
                      </div>
                    </label>
                  </div>
                </div>
                <div className="progress-plan-list">
                  {visibleAssignments.length === 0 ? (
                    <div className="progress-plan-card">
                      <p className="progress-plan-card__headline">No mentor assignments match the current filters.</p>
                    </div>
                  ) : visibleAssignments.map((item) => {
                    const dueMeta = getAssignmentDueMeta(item.due_label);
                    const assignmentTone = item.status === "completed"
                      ? "low"
                      : item.status === "dismissed"
                        ? "neutral"
                        : dueMeta.bucket === "overdue"
                          ? "high"
                          : "medium";
                    const assignmentLabel = item.status === "completed" ? "Done" : item.status === "dismissed" ? "Dismissed" : "Assigned";
                    return (
                      <div key={item.id || item.title} className="progress-plan-item">
                        <div className="progress-plan-item__top">
                          <div className="progress-plan-item__title">{item.title}</div>
                          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                            <span className={`progress-pill progress-pill--${assignmentTone}`}>
                              {assignmentLabel}
                            </span>
                            {dueMeta.label ? (
                              <span className={`progress-pill progress-pill--${dueMeta.tone}`}>
                                {dueMeta.label}
                              </span>
                            ) : null}
                          </div>
                        </div>
                        <div className="progress-plan-item__description">{item.description}</div>
                        <div className="progress-plan-item__meta">
                          {`Assigned by ${item.author_role || "mentor"}${item.due_label ? ` · Due ${item.due_label}` : ""}`}
                        </div>
                        {item.cta_label ? (
                          <button
                            type="button"
                            className="secondary-button progress-plan-item__action"
                            onClick={() => onPlanAction?.(item)}
                            disabled={!onPlanAction}
                          >
                            {item.cta_label}
                          </button>
                        ) : null}
                        {currentUsername ? (
                          <button
                            type="button"
                            className="secondary-button progress-plan-item__action"
                            onClick={() => handleAssignmentStatusUpdate(item, item.status === "completed" ? "assigned" : "completed")}
                            disabled={savingItemKey === `assignment:${item.id}`}
                          >
                            {item.status === "completed" ? "Undo" : "Mark Done"}
                          </button>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {!hasRemindersContent && (
              <div className="progress-plan-card">
                <p className="progress-plan-card__headline">No reminders or mentor tasks need attention right now.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === "overview" && (
          <div
            className="progress-tab-panel"
            role="tabpanel"
            id="progress-panel-overview"
            aria-labelledby="progress-tab-overview"
          >
            <p className="progress-tab-panel__intro">Use this tab for the weekly plan, goal tracking, and a quick snapshot of momentum.</p>

            {goalTargets.length > 0 && (
              <section className="progress-section">
                <h4 className="progress-section__title">
                  <FiZap /> Weekly Goals
                </h4>
                <div className="progress-goals-card">
                  <div className="progress-plan-card__summary">
                    <span className="progress-plan-card__summary-text">
                      {goalSummary.completed} of {goalSummary.total} goals on track
                    </span>
                    <span className={`progress-pill progress-pill--${goalSummary.completed === goalSummary.total ? "low" : "medium"}`}>
                      {goalSummary.completed === goalSummary.total ? "On track" : "Keep going"}
                    </span>
                  </div>
                  <div className="progress-goals-list">
                    {goalTargets.map((target) => {
                      const fallbackPct = target?.target
                        ? Math.min(100, Math.round(((Number(target.current) || 0) / Number(target.target)) * 100))
                        : 0;
                      const pct = typeof target?.progress_pct === "number" ? target.progress_pct : fallbackPct;

                      return (
                        <div key={target.id || target.label} className={`progress-goal-item${target.completed ? " is-complete" : ""}`}>
                          <div className="progress-goal-item__top">
                            <span className="progress-goal-item__label">{target.label}</span>
                            <span className="progress-goal-item__value">
                              {target.current} / {target.target} {target.unit}
                            </span>
                          </div>
                          <MasteryBar pct={pct} />
                          {target.cta_label ? (
                            <button
                              type="button"
                              className="secondary-button progress-plan-item__action"
                              onClick={() => onPlanAction?.(target)}
                              disabled={!onPlanAction}
                            >
                              {target.cta_label}
                            </button>
                          ) : null}
                          <button
                            type="button"
                            className="secondary-button progress-plan-item__action"
                            onClick={() => handleTogglePlanItem(target, "goal")}
                            disabled={savingItemKey === `goal:${target.id}`}
                          >
                            {target.completed ? "Undo" : "Mark Done"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </section>
            )}

            {(studyPlanHeadline || studyPlanSchedule.length > 0) && (
              <section className="progress-section">
                <h4 className="progress-section__title">
                  <FiBookOpen /> This Week's Plan
                </h4>
                <div className="progress-plan-card">
                  {studyPlanHeadline && (
                    <p className="progress-plan-card__headline">{studyPlanHeadline}</p>
                  )}
                  {studyPlanSchedule.length > 0 && (
                    <div className="progress-plan-card__summary">
                      <span className="progress-plan-card__summary-text">
                        {completedPlanSteps} of {studyPlanSchedule.length} complete
                      </span>
                      <span className={`progress-pill progress-pill--${completedPlanSteps === studyPlanSchedule.length ? "low" : "medium"}`}>
                        {completedPlanSteps === studyPlanSchedule.length ? "All set" : "In progress"}
                      </span>
                    </div>
                  )}
                  <div className="progress-plan-list">
                    {studyPlanSchedule.map((step) => (
                      <div key={step.id || step.title} className="progress-plan-item">
                        <div className="progress-plan-item__top">
                          <div className="progress-plan-item__title">{step.title}</div>
                          <span className={`progress-pill progress-pill--${getPlanStatusTone(step)}`}>
                            {getPlanStatusLabel(step)}
                          </span>
                        </div>
                        <div className="progress-plan-item__description">{step.description}</div>
                        {step.duration_minutes ? (
                          <div className="progress-plan-item__meta">{step.duration_minutes} min</div>
                        ) : null}
                        {step.cta_label ? (
                          <button
                            type="button"
                            className="secondary-button progress-plan-item__action"
                            onClick={() => onPlanAction?.(step)}
                            disabled={!onPlanAction}
                          >
                            {step.cta_label}
                          </button>
                        ) : null}
                        <button
                          type="button"
                          className="secondary-button progress-plan-item__action"
                          onClick={() => handleTogglePlanItem(step, "schedule")}
                          disabled={savingItemKey === `schedule:${step.id}`}
                        >
                          {step.completed ? "Undo" : "Mark Done"}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </section>
            )}

            {(studyPlanHistory?.current_week || previousWeek) && (
              <section className="progress-section">
                <h4 className="progress-section__title">
                  <FiClock /> Last Week Snapshot
                </h4>
                <div className="progress-plan-card">
                  {previousWeek ? (
                    <>
                      <p className="progress-plan-card__headline">{historyComparison.summary || "Progress is trending week over week."}</p>
                      <div className="progress-plan-card__summary">
                        <span className="progress-plan-card__summary-text">
                          {`Last week: ${previousWeek.goal_completed || 0}/${previousWeek.goal_total || 0} goals · ${previousWeek.completed_steps || 0}/${previousWeek.total_steps || 0} steps`}
                        </span>
                      </div>
                      {historyDeltaItems.length > 0 ? (
                        <div className="progress-plan-item__meta">
                          {`Week over week: ${historyDeltaItems.join(" · ")}`}
                        </div>
                      ) : null}
                      {currentWeek ? (
                        <div className="progress-plan-item__meta">
                          {`This week: ${currentWeek.goal_completed || 0}/${currentWeek.goal_total || 0} goals · ${currentWeek.completed_steps || 0}/${currentWeek.total_steps || 0} steps`}
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <p className="progress-plan-card__headline">{historyComparison.summary || "This week’s plan is now being tracked for future comparisons."}</p>
                  )}
                </div>
              </section>
            )}

            {!hasOverviewContent && (
              <div className="progress-plan-card">
                <p className="progress-plan-card__headline">Your weekly overview will appear here once the system has enough progress data.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === "activity" && (
          <div
            className="progress-tab-panel"
            role="tabpanel"
            id="progress-panel-activity"
            aria-labelledby="progress-tab-activity"
          >
            <p className="progress-tab-panel__intro">Review subject mastery, time spent, and recent learning activity in one timeline.</p>

            {masterySummary.length > 0 && (
              <section className="progress-section">
                <h4 className="progress-section__title">
                  <FiAward /> Subject Mastery
                </h4>
                <div className="progress-mastery-list">
                  {masterySummary.map((subj) => (
                    <div key={subj.subject} className="progress-mastery-item">
                      <div
                        className="progress-mastery-item__header"
                        onClick={() =>
                          setExpandedSubject(
                            expandedSubject === subj.subject ? null : subj.subject
                          )
                        }
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) =>
                          e.key === "Enter" &&
                          setExpandedSubject(
                            expandedSubject === subj.subject ? null : subj.subject
                          )
                        }
                      >
                        <span className="progress-mastery-item__name">{subj.subject}</span>
                        <span className="progress-mastery-item__pct">
                          {subj.avg_mastery_pct}%
                        </span>
                      </div>
                      <MasteryBar pct={subj.avg_mastery_pct} />
                      {onPlanAction ? (
                        <button
                          type="button"
                          className="secondary-button progress-plan-item__action"
                          onClick={() =>
                            onPlanAction({
                              id: `mastery-${String(subj.subject || "general").toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
                              action_tab: "quiz",
                              cta_label: `Practice ${subj.subject || "Topic"} Quiz`,
                              chapter_hint: subj.subject || "",
                              context_hint: `Practice ${subj.subject || "this subject"} with a short quiz to strengthen mastery.`,
                            })
                          }
                        >
                          {`Practice ${subj.subject || "Topic"} Quiz`}
                        </button>
                      ) : null}
                      {expandedSubject === subj.subject &&
                        subj.chapters.length > 0 && (
                          <div className="progress-chapters">
                            {subj.chapters.map((ch) => (
                              <div key={ch.chapter} className="progress-chapter-row">
                                <span className="progress-chapter-row__name">
                                  {ch.chapter || "General"}
                                </span>
                                <MasteryBar pct={ch.mastery_pct} />
                                <span className="progress-chapter-row__pct">
                                  {ch.mastery_pct}%
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {topSubjects.length > 0 && (
              <section className="progress-section">
                <h4 className="progress-section__title">
                  <FiClock /> Time by Subject
                </h4>
                <div className="progress-time-subjects">
                  {topSubjects.map((s) => {
                    const action = buildTopSubjectAction(s);
                    return (
                      <div key={s.subject} className="progress-time-subject-row">
                        <span className="progress-time-subject-row__name">{s.subject}</span>
                        <span className="progress-time-subject-row__time">
                          {fmtTime(s.study_seconds)}
                        </span>
                        {action?.cta_label ? (
                          <button
                            type="button"
                            className="secondary-button progress-plan-item__action"
                            onClick={() => onPlanAction?.(action)}
                            disabled={!onPlanAction}
                          >
                            {action.cta_label}
                          </button>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {recentActivity.length > 0 && (
              <section className="progress-section">
                <h4 className="progress-section__title">
                  <FiActivity /> Recent Activity
                </h4>
                <div className="progress-activity-list">
                  {recentActivity.map((item, idx) => (
                    <ActivityRow key={idx} item={item} onAction={onPlanAction} />
                  ))}
                </div>
              </section>
            )}

            {!hasActivityContent && (
              <div className="progress-empty">
                <FiBarChart2 />
                <p>No activity logged yet. Start learning to track your progress!</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
