/**
 * RoleHub utility functions and constants
 * Shared across RoleHubPanel and its subcomponents
 */

export const DEFAULT_ASSIGNMENT_TEMPLATES = [
  {
    id: "weekly-science-review",
    label: "Weekly Science Review",
    assignmentType: "lesson",
    subject: "Science",
    note: "Complete a short Science lesson recap together.",
  },
  {
    id: "math-quiz-checkpoint",
    label: "Math Quiz Checkpoint",
    assignmentType: "quiz",
    subject: "Math",
    note: "Practice one short Math quiz checkpoint this week.",
  },
  {
    id: "reading-reflection-checkin",
    label: "Reading Reflection Check-in",
    assignmentType: "chat",
    subject: "English",
    note: "Share a quick reading reflection in chat before the next class.",
  },
];

export const SAVED_ASSIGNMENT_TEMPLATES_KEY = "role-hub.saved-assignment-templates";

// ============================================================================
// Date & Duration Utilities
// ============================================================================

export function parseDueDateValue(value) {
  const rawValue = String(value || "").trim();
  if (!rawValue) return null;
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(rawValue) ? `${rawValue}T00:00:00` : rawValue;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatNoteDate(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString([], { dateStyle: "medium" });
}

export function getAssignmentDueMeta(dueLabel) {
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

export function isWithinRange(dateValue, range = "all") {
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

// ============================================================================
// Assignment Filtering & Sorting
// ============================================================================

export function matchesAssignmentFilter(item, filterValue = "all") {
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

export function compareAssignmentsByPriority(left, right) {
  const leftDueMeta = getAssignmentDueMeta(left?.due_label);
  const rightDueMeta = getAssignmentDueMeta(right?.due_label);
  const leftRank = leftDueMeta.bucket === "overdue" ? 0 : leftDueMeta.bucket === "due-soon" ? 1 : 2;
  const rightRank = rightDueMeta.bucket === "overdue" ? 0 : rightDueMeta.bucket === "due-soon" ? 1 : 2;

  if (leftRank !== rightRank) return leftRank - rightRank;
  if (leftDueMeta.sortTime !== rightDueMeta.sortTime) return leftDueMeta.sortTime - rightDueMeta.sortTime;
  return String(left?.title || "").localeCompare(String(right?.title || ""));
}

export function sortAssignmentsForMode(items, sortMode = "priority") {
  const list = [...(items || [])];
  if (sortMode === "title") {
    return list.sort((left, right) => String(left?.title || "").localeCompare(String(right?.title || "")));
  }
  if (sortMode === "due-date") {
    return list.sort((left, right) => getAssignmentDueMeta(left?.due_label).sortTime - getAssignmentDueMeta(right?.due_label).sortTime);
  }
  return list.sort(compareAssignmentsByPriority);
}

export function getNextOpenAssignment(assignments = []) {
  return [...(assignments || [])]
    .filter((item) => !["completed", "dismissed"].includes(String(item?.status || "assigned").toLowerCase()))
    .sort((left, right) => getAssignmentDueMeta(left?.due_label).sortTime - getAssignmentDueMeta(right?.due_label).sortTime)[0] || null;
}

// ============================================================================
// Subject & Search Filtering
// ============================================================================

export function matchesSubjectFilter(values, subjectFilter = "") {
  const filterValue = String(subjectFilter || "").trim().toLowerCase();
  if (!filterValue) return true;
  const haystack = (Array.isArray(values) ? values : [values]).filter(Boolean).join(" ").toLowerCase();
  return haystack.includes(filterValue);
}

// ============================================================================
// Template Formatting & Management
// ============================================================================

export function formatTemplateTypeLabel(value = "lesson") {
  const normalized = String(value || "lesson").trim().toLowerCase();
  return normalized ? `${normalized.charAt(0).toUpperCase()}${normalized.slice(1)}` : "Lesson";
}

export function formatTemplateCategoryLabel(value = "general") {
  const normalized = String(value || "general").trim().toLowerCase();
  const labels = {
    general: "General",
    stem: "STEM",
    humanities: "Humanities",
    languages: "Languages",
    exam: "Exam Prep",
  };
  return labels[normalized] || formatTemplateTypeLabel(normalized);
}

export function normalizeSavedAssignmentTemplates(value) {
  const sourceItems = Array.isArray(value)
    ? value
    : Array.isArray(value?.templates)
      ? value.templates
      : [];

  return sourceItems
    .map((item) => {
      const assignmentType = String(item?.assignmentType || "lesson").trim().toLowerCase() || "lesson";
      const subject = String(item?.subject || "").trim() || "General";
      const note = String(item?.note || "").trim() || `Focus on ${subject} with one short ${assignmentType} task this week.`;
      const label = String(item?.label || "").trim() || `${subject} ${formatTemplateTypeLabel(assignmentType)} Template`;
      const id = String(item?.id || `saved-template-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`).trim();
      return {
        id,
        label,
        assignmentType,
        subject,
        note,
        category: String(item?.category || "general").trim().toLowerCase() || "general",
        isFavorite: Boolean(item?.isFavorite),
      };
    })
    .filter((item) => item.id && item.label);
}

export function readSavedAssignmentTemplates() {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(SAVED_ASSIGNMENT_TEMPLATES_KEY) || "[]");
    return normalizeSavedAssignmentTemplates(parsed);
  } catch {
    return [];
  }
}

// ============================================================================
// Assignment Action Metadata
// ============================================================================

export function getAssignmentActionMeta(assignmentType = "lesson", subjectLabel = "General") {
  const actionLabels = {
    lesson: { title: `Review ${subjectLabel} lesson`, cta: `Open ${subjectLabel} Lesson` },
    quiz: { title: `Practice ${subjectLabel} quiz`, cta: "Open Assigned Quiz" },
    assessment: { title: `Retry ${subjectLabel} assessment`, cta: "Open Assigned Assessment" },
    chat: { title: `Recap ${subjectLabel} in chat`, cta: "Open Assigned Chat" },
    flashcards: { title: `Review ${subjectLabel} flashcards`, cta: "Open Assigned Flashcards" },
  };

  return actionLabels[assignmentType] || actionLabels.lesson;
}

export function buildRecentActivityAction(item) {
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
    id: `mentor-recent-${String(item.activity_type || "item")}-${String(chapterHint || "general")}`
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-"),
    action_tab: actionTab,
    chapter_hint: chapterHint,
    context_hint: contextHint,
    cta_label: ctaLabel,
  };
}

export function buildTopSubjectAction(item) {
  const subjectLabel = item?.subject || item?.chapter || "";
  if (!subjectLabel) return null;

  return {
    ...item,
    id: `time-subject-${String(subjectLabel).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
    action_tab: "lesson",
    chapter_hint: subjectLabel,
    context_hint: `Continue learning in ${subjectLabel} based on recent study time.`,
    cta_label: `Open ${subjectLabel} Lesson`,
  };
}

// ============================================================================
// File Export Utilities
// ============================================================================

export function downloadTextFile(fileName, content, mimeType = "text/plain;charset=utf-8") {
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
