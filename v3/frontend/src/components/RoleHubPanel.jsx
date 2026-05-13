import React, { useCallback, useEffect, useMemo, useState } from "react";
import { FiLink, FiRefreshCw, FiUsers } from "react-icons/fi";
import { apiFetch, parseApiError } from "../services/api";

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
    id: `mentor-recent-${String(item.activity_type || "item")}-${String(chapterHint || "general")}`
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
    context_hint: `Continue learning in ${subjectLabel} based on recent study time.`,
    cta_label: `Open ${subjectLabel} Lesson`,
  };
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
    <svg role="img" aria-label={label} width="120" height="32" viewBox={`0 0 ${width} ${height}`}>
      <polyline fill="none" stroke="#6c63ff" strokeWidth="2" points={points} />
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

function formatNoteDate(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString([], { dateStyle: "medium" });
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

function getNextOpenAssignment(assignments = []) {
  return [...(assignments || [])]
    .filter((item) => !["completed", "dismissed"].includes(String(item?.status || "assigned").toLowerCase()))
    .sort((left, right) => getAssignmentDueMeta(left?.due_label).sortTime - getAssignmentDueMeta(right?.due_label).sortTime)[0] || null;
}

function getAssignmentActionMeta(assignmentType = "lesson", subjectLabel = "General") {
  const actionLabels = {
    lesson: { title: `Review ${subjectLabel} lesson`, cta: `Open ${subjectLabel} Lesson` },
    quiz: { title: `Practice ${subjectLabel} quiz`, cta: "Open Assigned Quiz" },
    assessment: { title: `Retry ${subjectLabel} assessment`, cta: "Open Assigned Assessment" },
    chat: { title: `Recap ${subjectLabel} in chat`, cta: "Open Assigned Chat" },
    flashcards: { title: `Review ${subjectLabel} flashcards`, cta: "Open Assigned Flashcards" },
  };

  return actionLabels[assignmentType] || actionLabels.lesson;
}

const DEFAULT_ASSIGNMENT_TEMPLATES = [
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

const SAVED_ASSIGNMENT_TEMPLATES_KEY = "role-hub.saved-assignment-templates";

function formatTemplateTypeLabel(value = "lesson") {
  const normalized = String(value || "lesson").trim().toLowerCase();
  return normalized ? `${normalized.charAt(0).toUpperCase()}${normalized.slice(1)}` : "Lesson";
}

function formatTemplateCategoryLabel(value = "general") {
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

function normalizeSavedAssignmentTemplates(value) {
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

function readSavedAssignmentTemplates() {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(SAVED_ASSIGNMENT_TEMPLATES_KEY) || "[]");
    return normalizeSavedAssignmentTemplates(parsed);
  } catch {
    return [];
  }
}

export default function RoleHubPanel({
  onPlanAction = null,
  actualRole = null,
  viewRole = null,
  onAdminViewRoleChange = null,
  onAdminReindex = null,
  onAdminIncrementalReindex = null,
  adminRunning = false,
  adminMessage = "",
}) {
  const role = String(actualRole || localStorage.getItem("role") || "student").toLowerCase();
  const username = localStorage.getItem("username") || "";
  const previewRole = role === "admin"
    ? String(viewRole || "admin").toLowerCase()
    : role;

  const isMentorRole = previewRole === "teacher" || previewRole === "parent";
  const isAdminRole = role === "admin";
  const isStudentRole = previewRole === "student";

  const [studentEmail, setStudentEmail] = useState("");
  const [relationLabel, setRelationLabel] = useState("");
  const [students, setStudents] = useState([]);
  const [mentors, setMentors] = useState([]);
  const [selectedStudent, setSelectedStudent] = useState("");
  const [assignmentTargets, setAssignmentTargets] = useState([]);
  const [savedAssignmentTemplates, setSavedAssignmentTemplates] = useState([]);
  const [templateImportText, setTemplateImportText] = useState("");
  const [templateImportStatus, setTemplateImportStatus] = useState("");
  const [editingTemplateId, setEditingTemplateId] = useState(null);
  const [editingTemplateLabel, setEditingTemplateLabel] = useState("");
  const [editingTemplateType, setEditingTemplateType] = useState("lesson");
  const [editingTemplateCategory, setEditingTemplateCategory] = useState("general");
  const [editingTemplateSubject, setEditingTemplateSubject] = useState("");
  const [editingTemplateNote, setEditingTemplateNote] = useState("");
  const [savedTemplateCategoryFilter, setSavedTemplateCategoryFilter] = useState("all");
  const [showFavoriteTemplatesOnly, setShowFavoriteTemplatesOnly] = useState(false);
  const [previewTemplateId, setPreviewTemplateId] = useState(null);
  const [studentProgress, setStudentProgress] = useState(null);
  const [studentMastery, setStudentMastery] = useState([]);
  const [studentInsights, setStudentInsights] = useState(null);
  const [studentStudyPlan, setStudentStudyPlan] = useState(null);
  const [notes, setNotes] = useState([]);
  const [noteText, setNoteText] = useState("");
  const [assignmentType, setAssignmentType] = useState("quiz");
  const [templateCategory, setTemplateCategory] = useState("general");
  const [assignmentSubject, setAssignmentSubject] = useState("");
  const [assignmentNote, setAssignmentNote] = useState("");
  const [assignmentDueLabel, setAssignmentDueLabel] = useState("");
  const [assignmentSubmitting, setAssignmentSubmitting] = useState(false);
  const [assignmentBusyKey, setAssignmentBusyKey] = useState("");
  const [editingAssignmentId, setEditingAssignmentId] = useState(null);
  const [editingAssignmentTitle, setEditingAssignmentTitle] = useState("");
  const [editingAssignmentDescription, setEditingAssignmentDescription] = useState("");
  const [editingAssignmentType, setEditingAssignmentType] = useState("lesson");
  const [editingAssignmentDueLabel, setEditingAssignmentDueLabel] = useState("");
  const [workspaceSearch, setWorkspaceSearch] = useState("");
  const [assignmentFilter, setAssignmentFilter] = useState("all");
  const [assignmentSort, setAssignmentSort] = useState("priority");
  const [noteVisibilityFilter, setNoteVisibilityFilter] = useState("all");
  const [reportSubject, setReportSubject] = useState("");
  const [reportRange, setReportRange] = useState("all");
  const [noteBusyKey, setNoteBusyKey] = useState("");
  const [editingNoteId, setEditingNoteId] = useState(null);
  const [editingNoteText, setEditingNoteText] = useState("");
  const [editingNoteVisibility, setEditingNoteVisibility] = useState("all");
  const [visibility, setVisibility] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [teacherRosterProgress, setTeacherRosterProgress] = useState({});
  const [availableModelProfiles, setAvailableModelProfiles] = useState([]);
  const [selectedModelProfile, setSelectedModelProfile] = useState("balanced");
  const [modelProfileLoading, setModelProfileLoading] = useState(false);
  const [modelProfileSaving, setModelProfileSaving] = useState(false);
  const [modelProfileStatus, setModelProfileStatus] = useState("");

  const activeStudent = useMemo(() => {
    if (isStudentRole) return username;
    return selectedStudent || "";
  }, [isStudentRole, selectedStudent, username]);

  const assignmentTargetUsers = useMemo(() => {
    if (!isMentorRole) return [];
    const availableTargets = (students || []).map((item) => item?.username).filter(Boolean);
    const selectedTargets = (assignmentTargets || []).filter((item) => availableTargets.includes(item));
    if (selectedTargets.length > 0) return selectedTargets;
    if (previewRole === "teacher" && availableTargets.length > 0) return availableTargets;
    return activeStudent ? [activeStudent] : availableTargets.slice(0, 1);
  }, [activeStudent, assignmentTargets, isMentorRole, previewRole, students]);

  const filteredAssignments = useMemo(() => {
    const searchValue = String(workspaceSearch || "").trim().toLowerCase();
    const nextAssignments = [...(studentProgress?.assignments || [])]
      .filter((item) => matchesAssignmentFilter(item, assignmentFilter))
      .filter((item) => {
        if (!searchValue) return true;
        const haystack = [item?.title, item?.description, item?.chapter_hint, item?.due_label]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(searchValue);
      });
    return sortAssignmentsForMode(nextAssignments, assignmentSort);
  }, [assignmentFilter, assignmentSort, studentProgress, workspaceSearch]);

  const filteredNotes = useMemo(() => {
    const searchValue = String(workspaceSearch || "").trim().toLowerCase();
    return (notes || []).filter((item) => {
      if (noteVisibilityFilter !== "all" && String(item?.visibility || "all") !== noteVisibilityFilter) {
        return false;
      }
      if (!searchValue) return true;
      const haystack = [item?.note_text, item?.author_role, item?.visibility]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(searchValue);
    });
  }, [noteVisibilityFilter, notes, workspaceSearch]);

  const bulkAssignmentSummary = useMemo(() => {
    const visibleAssignments = Array.isArray(filteredAssignments) ? filteredAssignments : [];
    const openVisible = visibleAssignments.filter(
      (item) => !["completed", "dismissed"].includes(String(item?.status || "assigned").toLowerCase()),
    );
    const overdueVisible = openVisible.filter((item) => getAssignmentDueMeta(item?.due_label).bucket === "overdue");
    const dismissedVisible = visibleAssignments.filter(
      (item) => String(item?.status || "assigned").toLowerCase() === "dismissed",
    );

    return {
      visibleCount: visibleAssignments.length,
      openVisibleCount: openVisible.length,
      overdueVisibleCount: overdueVisible.length,
      dismissedVisibleCount: dismissedVisible.length,
    };
  }, [filteredAssignments]);

  const filteredSavedTemplates = useMemo(() => {
    return (savedAssignmentTemplates || []).filter((item) => {
      if (savedTemplateCategoryFilter !== "all" && String(item?.category || "general") !== savedTemplateCategoryFilter) {
        return false;
      }
      if (showFavoriteTemplatesOnly && !item?.isFavorite) {
        return false;
      }
      return true;
    });
  }, [savedAssignmentTemplates, savedTemplateCategoryFilter, showFavoriteTemplatesOnly]);

  const savedTemplateSummary = useMemo(() => ({
    totalCount: (savedAssignmentTemplates || []).length,
    favoriteCount: (savedAssignmentTemplates || []).filter((item) => item?.isFavorite).length,
  }), [savedAssignmentTemplates]);

  const selectedModelProfileDetails = useMemo(
    () => (availableModelProfiles || []).find((item) => item?.key === selectedModelProfile) || null,
    [availableModelProfiles, selectedModelProfile],
  );

  const assignmentButtonLabel = assignmentSubmitting
    ? "Assigning..."
    : assignmentTargetUsers.length > 1
      ? `Assign to ${assignmentTargetUsers.length} Learners`
      : "Assign Task";

  const workspaceTitle = previewRole === "teacher"
    ? "Teacher Workspace"
    : previewRole === "parent"
      ? "Parent Workspace"
      : previewRole === "admin"
        ? "Admin Workspace"
        : "Student Support Network";
  const workspaceDescription = previewRole === "teacher"
    ? "Link learners, assign work, and review study progress from one place."
    : previewRole === "parent"
      ? "Track your learner's assignments, notes, and progress alongside teacher updates."
      : previewRole === "admin"
        ? "Use this hub to preview role-based experiences. Open Admin Center for app-wide settings and maintenance actions."
        : "See your mentors, shared notes, and assigned work in one support workspace.";
  const activeStudentRecord = useMemo(
    () => (students || []).find((item) => item?.username === activeStudent) || null,
    [activeStudent, students],
  );
  const teacherRosterSummary = useMemo(() => {
    if (previewRole !== "teacher") return null;
    const learnerCount = Array.isArray(students) ? students.length : 0;
    const rosterLabels = Array.from(
      new Set(
        (students || [])
          .map((item) => String(item?.relation_label || "").trim())
          .filter(Boolean),
      ),
    );
    const assignments = Array.isArray(studentProgress?.assignments) ? studentProgress.assignments : [];
    const openAssignments = assignments.filter((item) => !["completed", "dismissed"].includes(String(item?.status || "assigned").toLowerCase()));
    return {
      learnerCount,
      selectedLearner: activeStudentRecord?.first_name || activeStudentRecord?.email || activeStudent || "No learner selected",
      rosterLabelSummary: rosterLabels.join(", ") || "No class labels added yet",
      openAssignmentsCount: openAssignments.length,
    };
  }, [activeStudent, activeStudentRecord, previewRole, studentProgress, students]);
  const teacherClassSummary = useMemo(() => {
    if (previewRole !== "teacher") return null;

    const rosterRecords = (students || [])
      .map((item) => {
        const learnerKey = item?.username;
        if (!learnerKey) return null;

        const dashboard = teacherRosterProgress[learnerKey]
          || (learnerKey === activeStudent ? studentProgress : null)
          || null;
        const assignments = Array.isArray(dashboard?.assignments) ? dashboard.assignments : [];
        const openAssignments = assignments.filter(
          (assignment) => !["completed", "dismissed"].includes(String(assignment?.status || "assigned").toLowerCase()),
        );
        const overdueAssignments = openAssignments.filter(
          (assignment) => getAssignmentDueMeta(assignment?.due_label).bucket === "overdue",
        );
        const urgentAssignments = openAssignments.filter((assignment) => {
          const bucket = getAssignmentDueMeta(assignment?.due_label).bucket;
          return bucket === "overdue" || bucket === "due-soon";
        });
        const assessmentAverage = Number(dashboard?.assessment_summary?.average_score_pct || 0);
        const streakDays = Number(dashboard?.streak_days || 0);
        const needsAttention = overdueAssignments.length > 0 || (assessmentAverage > 0 && assessmentAverage < 70) || streakDays < 2;

        return {
          learnerName: item?.first_name || item?.email || learnerKey,
          openAssignmentsCount: openAssignments.length,
          urgentAssignmentsCount: urgentAssignments.length,
          assessmentAverage,
          streakDays,
          needsAttention,
        };
      })
      .filter(Boolean);

    if (rosterRecords.length === 0) return null;

    const onTrackCount = rosterRecords.filter((item) => !item.needsAttention).length;
    const needsAttentionCount = rosterRecords.length - onTrackCount;
    const averageStreak = Math.round(
      rosterRecords.reduce((total, item) => total + Number(item?.streakDays || 0), 0) / rosterRecords.length,
    );
    const scoreValues = rosterRecords
      .map((item) => Number(item?.assessmentAverage || 0))
      .filter((value) => value > 0);
    const classAverageScore = scoreValues.length > 0
      ? Math.round(scoreValues.reduce((total, value) => total + value, 0) / scoreValues.length)
      : 0;
    const urgentLearnerCount = rosterRecords.filter((item) => item.urgentAssignmentsCount > 0).length;
    const focusLearner = [...rosterRecords].sort((left, right) => {
      if (left.needsAttention !== right.needsAttention) return left.needsAttention ? -1 : 1;
      if (left.urgentAssignmentsCount !== right.urgentAssignmentsCount) return right.urgentAssignmentsCount - left.urgentAssignmentsCount;
      if (left.assessmentAverage !== right.assessmentAverage) return left.assessmentAverage - right.assessmentAverage;
      return left.learnerName.localeCompare(right.learnerName);
    })[0] || null;

    return {
      learnerCount: rosterRecords.length,
      onTrackCount,
      needsAttentionCount,
      averageStreak,
      classAverageScore,
      urgentLearnerCount,
      focusLearnerName: focusLearner?.learnerName || "No learner selected",
    };
  }, [activeStudent, previewRole, studentProgress, students, teacherRosterProgress]);
  const parentSummary = useMemo(() => {
    if (previewRole !== "parent" || !studentProgress) return null;
    const assignments = Array.isArray(studentProgress?.assignments) ? studentProgress.assignments : [];
    const openAssignments = assignments.filter((item) => !["completed", "dismissed"].includes(String(item?.status || "assigned").toLowerCase()));
    const nextDueAssignment = getNextOpenAssignment(assignments);
    const assessmentSummary = studentProgress?.assessment_summary || {};
    return {
      learnerName: activeStudentRecord?.first_name || activeStudentRecord?.email || activeStudent || "your learner",
      openAssignmentsCount: openAssignments.length,
      nextDueLabel: nextDueAssignment?.due_label || "No due date set",
      nextDueTitle: nextDueAssignment?.title || "No active assignments",
      streakDays: Number(studentProgress?.streak_days || 0),
      averageScore: Number(assessmentSummary?.average_score_pct || 0),
      latestScore: Number(assessmentSummary?.latest_score_pct || 0),
      latestSubject: assessmentSummary?.latest_subject || "",
    };
  }, [activeStudent, activeStudentRecord, previewRole, studentProgress]);

  const loadRoleData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      if (isMentorRole) {
        const rosterRes = await apiFetch("/relationships/my-students", { method: "GET" });
        if (!rosterRes.ok) {
          if (isAdminRole) {
            setStudents([]);
            setMentors([]);
            return;
          }
          throw new Error(await parseApiError(rosterRes, "Unable to load linked students."));
        }
        const rosterData = await rosterRes.json();
        const nextStudents = rosterData.students || [];
        setStudents(nextStudents);
        if (nextStudents.length > 0 && !selectedStudent) {
          setSelectedStudent(nextStudents[0].username);
        }
        setMentors([]);
      } else if (isAdminRole) {
        setStudents([]);
        setMentors([]);
      } else {
        const mentorRes = await apiFetch("/relationships/my-mentors", { method: "GET" });
        if (mentorRes.ok) {
          const mentorData = await mentorRes.json();
          setMentors(mentorData.mentors || []);
        }
      }
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  }, [isAdminRole, isMentorRole, selectedStudent]);

  const loadAdminModelProfiles = useCallback(async () => {
    if (!isAdminRole) return;

    setModelProfileLoading(true);
    try {
      const res = await apiFetch("/admin/model-profiles", { method: "GET" });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to load global model profile settings."));
      }
      const payload = await res.json();
      const profiles = Array.isArray(payload?.profiles) ? payload.profiles : [];
      const activeProfile = payload?.active_profile || profiles[0]?.key || "balanced";
      setAvailableModelProfiles(profiles);
      setSelectedModelProfile(activeProfile);
      setModelProfileStatus("");
    } catch (_err) {
      // The dedicated Admin Center owns this state now; keep role previews usable even if the admin-state endpoint is unavailable.
    } finally {
      setModelProfileLoading(false);
    }
  }, [isAdminRole]);

  const loadTeacherRosterSnapshots = useCallback(async () => {
    if (previewRole !== "teacher") {
      setTeacherRosterProgress({});
      return;
    }

    const roster = Array.isArray(students) ? students.filter((item) => item?.username) : [];
    if (roster.length === 0) {
      setTeacherRosterProgress({});
      return;
    }

    try {
      const snapshotEntries = await Promise.all(
        roster.map(async (item) => {
          const learnerKey = item.username;
          const response = await apiFetch(`/students/${encodeURIComponent(learnerKey)}/progress`, { method: "GET" });
          if (!response.ok) {
            return [learnerKey, null];
          }
          const payload = await response.json();
          return [learnerKey, payload?.dashboard || null];
        }),
      );
      setTeacherRosterProgress(Object.fromEntries(snapshotEntries.filter(Boolean)));
    } catch (_err) {
      setTeacherRosterProgress({});
    }
  }, [previewRole, students]);

  const loadStudentViews = useCallback(async () => {
    if (!activeStudent) return;
    setError("");

    try {
      if (isMentorRole) {
        const progressRes = await apiFetch(`/students/${encodeURIComponent(activeStudent)}/progress`, { method: "GET" });
        if (progressRes.ok) {
          const data = await progressRes.json();
          setStudentProgress(data.dashboard || null);
          setStudentMastery(Array.isArray(data.mastery) ? data.mastery : []);
          setStudentInsights(data.insights || null);
          setStudentStudyPlan(data.study_plan || null);
        } else {
          setStudentProgress(null);
          setStudentMastery([]);
          setStudentInsights(null);
          setStudentStudyPlan(null);
        }
      }

      const notesRes = await apiFetch(`/students/${encodeURIComponent(activeStudent)}/notes`, { method: "GET" });
      if (notesRes.ok) {
        const data = await notesRes.json();
        setNotes(data.notes || []);
      } else {
        setNotes([]);
      }
    } catch (err) {
      setError(String(err.message || err));
    }
  }, [activeStudent, isMentorRole]);

  useEffect(() => {
    if (previewRole !== "teacher") {
      setSavedAssignmentTemplates([]);
      return;
    }
    setSavedAssignmentTemplates(readSavedAssignmentTemplates());
  }, [previewRole]);

  useEffect(() => {
    if (previewRole !== "teacher" || typeof window === "undefined") return;
    try {
      window.localStorage.setItem(SAVED_ASSIGNMENT_TEMPLATES_KEY, JSON.stringify(savedAssignmentTemplates));
    } catch (_err) {
      // Ignore localStorage write issues.
    }
  }, [previewRole, savedAssignmentTemplates]);

  useEffect(() => {
    loadRoleData();
  }, [loadRoleData]);

  useEffect(() => {
    loadAdminModelProfiles();
  }, [loadAdminModelProfiles]);

  useEffect(() => {
    loadTeacherRosterSnapshots();
  }, [loadTeacherRosterSnapshots]);

  useEffect(() => {
    loadStudentViews();
  }, [loadStudentViews]);

  const handleLinkStudent = async () => {
    if (!studentEmail.trim()) return;
    setError("");
    try {
      const res = await apiFetch("/relationships/link-student", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student_email: studentEmail.trim(),
          relation_label: relationLabel.trim() || null,
        }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to link student."));
      }
      setStudentEmail("");
      setRelationLabel("");
      await loadRoleData();
    } catch (err) {
      setError(String(err.message || err));
    }
  };

  const handleUnlinkSelectedStudent = async () => {
    if (!isMentorRole || !activeStudent) return;
    const studentLabel = activeStudentRecord?.first_name || activeStudentRecord?.email || activeStudent;
    if (!window.confirm(`Unlink ${studentLabel}? Shared notes and assignments remain with the student account.`)) return;

    setError("");
    try {
      const res = await apiFetch(`/relationships/students/${encodeURIComponent(activeStudent)}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to unlink student."));
      }
      setSelectedStudent("");
      setStudentProgress(null);
      setStudentMastery([]);
      setStudentInsights(null);
      setStudentStudyPlan(null);
      await loadRoleData();
    } catch (err) {
      setError(String(err.message || err));
    }
  };

  const handleApplyGlobalModelProfile = async () => {
    if (!isAdminRole || !selectedModelProfile) return;

    setModelProfileSaving(true);
    setModelProfileStatus("");
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
      setError(String(err.message || err));
    } finally {
      setModelProfileSaving(false);
    }
  };

  const handleToggleAssignmentTarget = (studentUsername) => {
    if (!studentUsername) return;
    setAssignmentTargets((current) => {
      const seedTargets = (current && current.length > 0 ? current : assignmentTargetUsers).filter(Boolean);
      if (seedTargets.includes(studentUsername)) {
        const nextTargets = seedTargets.filter((item) => item !== studentUsername);
        return nextTargets.length > 0 ? nextTargets : [studentUsername];
      }
      return [...seedTargets, studentUsername];
    });
  };

  const handleUseAllAssignmentTargets = () => {
    setAssignmentTargets((students || []).map((item) => item?.username).filter(Boolean));
  };

  const handleUseActiveAssignmentTarget = () => {
    setAssignmentTargets(activeStudent ? [activeStudent] : []);
  };

  const handleApplyAssignmentTemplate = (template) => {
    if (!template) return;
    setAssignmentType(template.assignmentType || "lesson");
    setTemplateCategory(template.category || "general");
    setAssignmentSubject(template.subject || "");
    setAssignmentNote(template.note || "");
  };

  const handleSaveAssignmentTemplate = () => {
    if (previewRole !== "teacher") return;
    const subject = assignmentSubject.trim() || "General";
    const note = assignmentNote.trim() || `Focus on ${subject} with one short ${assignmentType} task this week.`;
    const label = `${subject} ${formatTemplateTypeLabel(assignmentType)} Template`;
    const templateId = `saved-template-${String(label).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

    setSavedAssignmentTemplates((current) => {
      const nextTemplates = [
        {
          id: templateId,
          label,
          assignmentType: assignmentType || "lesson",
          subject,
          note,
          category: templateCategory || "general",
          isFavorite: current.find((item) => item.id === templateId)?.isFavorite || false,
        },
        ...current.filter((item) => item.id !== templateId),
      ].slice(0, 6);
      return nextTemplates;
    });
    setTemplateImportStatus(`Saved template ${label}.`);
    setError("");
  };

  const handleExportTemplateLibrary = () => {
    if ((savedAssignmentTemplates || []).length === 0) return;
    downloadTextFile(
      "teacher-template-library.json",
      JSON.stringify(savedAssignmentTemplates, null, 2),
      "application/json;charset=utf-8",
    );
    setTemplateImportStatus(`Exported ${savedAssignmentTemplates.length} templates.`);
    setError("");
  };

  const handleImportTemplateLibrary = () => {
    if (!templateImportText.trim()) return;
    try {
      const parsed = JSON.parse(templateImportText);
      const importedTemplates = normalizeSavedAssignmentTemplates(parsed);
      if (importedTemplates.length === 0) {
        throw new Error("No templates found in the shared JSON.");
      }

      setSavedAssignmentTemplates((current) => {
        const merged = [...importedTemplates, ...current];
        const seen = new Set();
        return merged.filter((item) => {
          if (seen.has(item.id)) return false;
          seen.add(item.id);
          return true;
        }).slice(0, 12);
      });
      setTemplateImportText("");
      setTemplateImportStatus(`Imported ${importedTemplates.length} templates.`);
      setError("");
    } catch (err) {
      setTemplateImportStatus("");
      setError(String(err?.message || "Unable to import shared templates."));
    }
  };

  const handleStartEditTemplate = (template) => {
    if (!template) return;
    setEditingTemplateId(template.id || null);
    setEditingTemplateLabel(template.label || "");
    setEditingTemplateType(template.assignmentType || "lesson");
    setEditingTemplateCategory(template.category || "general");
    setEditingTemplateSubject(template.subject || "");
    setEditingTemplateNote(template.note || "");
  };

  const handleCancelEditTemplate = () => {
    setEditingTemplateId(null);
    setEditingTemplateLabel("");
    setEditingTemplateType("lesson");
    setEditingTemplateCategory("general");
    setEditingTemplateSubject("");
    setEditingTemplateNote("");
  };

  const handleSaveEditedTemplate = () => {
    if (!editingTemplateId || !editingTemplateLabel.trim()) return;
    setSavedAssignmentTemplates((current) => current.map((item) => (
      item.id === editingTemplateId
        ? {
          ...item,
          label: editingTemplateLabel.trim(),
          assignmentType: editingTemplateType || "lesson",
          category: editingTemplateCategory || "general",
          subject: editingTemplateSubject.trim() || "General",
          note: editingTemplateNote.trim() || `Focus on ${editingTemplateSubject.trim() || "General"} with one short ${editingTemplateType} task this week.`,
        }
        : item
    )));
    handleCancelEditTemplate();
  };

  const handleToggleTemplateFavorite = (templateId) => {
    setSavedAssignmentTemplates((current) => current.map((item) => (
      item.id === templateId ? { ...item, isFavorite: !item.isFavorite } : item
    )));
  };

  const handleDeleteSavedTemplate = (templateId) => {
    setSavedAssignmentTemplates((current) => current.filter((item) => item.id !== templateId));
    if (editingTemplateId === templateId) {
      handleCancelEditTemplate();
    }
    if (previewTemplateId === templateId) {
      setPreviewTemplateId(null);
    }
  };

  const handlePreviewSavedTemplate = (templateId) => {
    setPreviewTemplateId((current) => (current === templateId ? null : templateId));
  };

  const handleDuplicateSavedTemplate = (template) => {
    if (!template) return;

    let duplicateId = "";
    let duplicateLabel = "";

    setSavedAssignmentTemplates((current) => {
      const existingLabels = new Set(current.map((item) => String(item?.label || "").toLowerCase()));
      duplicateLabel = `${template.label} Copy`;
      let suffix = 2;
      while (existingLabels.has(duplicateLabel.toLowerCase())) {
        duplicateLabel = `${template.label} Copy ${suffix}`;
        suffix += 1;
      }
      duplicateId = `saved-template-${String(duplicateLabel).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
      return [
        {
          ...template,
          id: duplicateId,
          label: duplicateLabel,
          isFavorite: false,
        },
        ...current,
      ].slice(0, 12);
    });

    if (duplicateId) {
      setPreviewTemplateId(duplicateId);
      setTemplateImportStatus(`Duplicated template ${duplicateLabel}.`);
      setError("");
    }
  };

  const handleCreateNote = async () => {
    if (!isMentorRole || !activeStudent || !noteText.trim()) return;
    setError("");
    try {
      const res = await apiFetch("/collaboration/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student_username: activeStudent,
          note_text: noteText.trim(),
          visibility,
        }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to save note."));
      }
      setNoteText("");
      await loadStudentViews();
    } catch (err) {
      setError(String(err.message || err));
    }
  };

  const handleAssignTask = async () => {
    const targetStudents = assignmentTargetUsers.filter(Boolean);
    if (!isMentorRole || targetStudents.length === 0) return;
    setError("");
    setAssignmentSubmitting(true);
    try {
      const subjectLabel = assignmentSubject.trim() || studentStudyPlan?.focus_subject || "General";
      const selectedAction = getAssignmentActionMeta(assignmentType, subjectLabel);
      const description = assignmentNote.trim() || `Focus on ${subjectLabel} with one short ${assignmentType} task this week.`;

      await Promise.all(targetStudents.map(async (studentUsername) => {
        const res = await apiFetch(`/students/${encodeURIComponent(studentUsername)}/assignments`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: selectedAction.title,
            description,
            action_tab: assignmentType,
            cta_label: selectedAction.cta,
            chapter_hint: subjectLabel,
            context_hint: description,
            due_label: assignmentDueLabel.trim() || null,
          }),
        });
        if (!res.ok) {
          throw new Error(await parseApiError(res, "Unable to assign a task."));
        }
      }));
      setAssignmentNote("");
      setAssignmentDueLabel("");
      await loadStudentViews();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setAssignmentSubmitting(false);
    }
  };

  const handleUpdateAssignment = async (assignmentId, updates) => {
    if (!activeStudent || !assignmentId) return;
    setAssignmentBusyKey(`update:${assignmentId}`);
    setError("");
    try {
      const res = await apiFetch(`/students/${encodeURIComponent(activeStudent)}/assignments/${encodeURIComponent(assignmentId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to update assignment."));
      }
      await loadStudentViews();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setAssignmentBusyKey("");
    }
  };

  const handleBulkAssignmentUpdate = async (mode = "complete-open") => {
    if (!activeStudent) return;

    const targetAssignments = filteredAssignments.filter((item) => {
      const status = String(item?.status || "assigned").toLowerCase();
      const dueBucket = getAssignmentDueMeta(item?.due_label).bucket;

      if (mode === "dismiss-overdue") {
        return status === "assigned" && dueBucket === "overdue";
      }
      if (mode === "reopen-dismissed") {
        return status === "dismissed";
      }
      return !["completed", "dismissed"].includes(status);
    });

    if (targetAssignments.length === 0) return;

    const nextStatus = mode === "dismiss-overdue"
      ? "dismissed"
      : mode === "reopen-dismissed"
        ? "assigned"
        : "completed";

    setAssignmentBusyKey(`bulk:${mode}`);
    setError("");
    try {
      await Promise.all(
        targetAssignments.map(async (item) => {
          const res = await apiFetch(`/students/${encodeURIComponent(activeStudent)}/assignments/${encodeURIComponent(item.id)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: nextStatus }),
          });
          if (!res.ok) {
            throw new Error(await parseApiError(res, "Unable to update assignments."));
          }
        }),
      );
      if (editingAssignmentId && targetAssignments.some((item) => item.id === editingAssignmentId)) {
        handleCancelEditAssignment();
      }
      await loadStudentViews();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setAssignmentBusyKey("");
    }
  };

  const handleDeleteAssignment = async (assignmentId) => {
    if (!activeStudent || !assignmentId) return;
    setAssignmentBusyKey(`delete:${assignmentId}`);
    setError("");
    try {
      const res = await apiFetch(`/students/${encodeURIComponent(activeStudent)}/assignments/${encodeURIComponent(assignmentId)}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to delete assignment."));
      }
      if (editingAssignmentId === assignmentId) {
        setEditingAssignmentId(null);
        setEditingAssignmentTitle("");
        setEditingAssignmentDescription("");
        setEditingAssignmentType("lesson");
        setEditingAssignmentDueLabel("");
      }
      await loadStudentViews();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setAssignmentBusyKey("");
    }
  };

  const handleStartEditAssignment = (item) => {
    setEditingAssignmentId(item?.id || null);
    setEditingAssignmentTitle(item?.title || "");
    setEditingAssignmentDescription(item?.description || "");
    setEditingAssignmentType(item?.action_tab || "lesson");
    setEditingAssignmentDueLabel(item?.due_label || "");
    setError("");
  };

  const handleCancelEditAssignment = () => {
    setEditingAssignmentId(null);
    setEditingAssignmentTitle("");
    setEditingAssignmentDescription("");
    setEditingAssignmentType("lesson");
    setEditingAssignmentDueLabel("");
  };

  const handleSaveAssignment = async (assignmentId) => {
    if (!activeStudent || !assignmentId || !editingAssignmentTitle.trim() || !editingAssignmentDescription.trim()) return;
    setAssignmentBusyKey(`edit:${assignmentId}`);
    setError("");
    try {
      const assignmentMeta = getAssignmentActionMeta(editingAssignmentType, editingAssignmentTitle.trim());
      const res = await apiFetch(`/students/${encodeURIComponent(activeStudent)}/assignments/${encodeURIComponent(assignmentId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: editingAssignmentTitle.trim(),
          description: editingAssignmentDescription.trim(),
          action_tab: editingAssignmentType,
          cta_label: assignmentMeta.cta,
          context_hint: editingAssignmentDescription.trim(),
          due_label: editingAssignmentDueLabel.trim() || null,
        }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to update assignment."));
      }
      handleCancelEditAssignment();
      await loadStudentViews();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setAssignmentBusyKey("");
    }
  };

  const handleStartEditNote = (note) => {
    setEditingNoteId(note?.id || null);
    setEditingNoteText(note?.note_text || "");
    setEditingNoteVisibility(note?.visibility || "all");
    setError("");
  };

  const handleCancelEditNote = () => {
    setEditingNoteId(null);
    setEditingNoteText("");
    setEditingNoteVisibility("all");
  };

  const handleSaveNote = async (noteId) => {
    if (!activeStudent || !noteId || !editingNoteText.trim()) return;
    setNoteBusyKey(`edit:${noteId}`);
    setError("");
    try {
      const res = await apiFetch(`/students/${encodeURIComponent(activeStudent)}/notes/${encodeURIComponent(noteId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          note_text: editingNoteText.trim(),
          visibility: editingNoteVisibility,
        }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to update note."));
      }
      handleCancelEditNote();
      await loadStudentViews();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setNoteBusyKey("");
    }
  };

  const handleDeleteNote = async (noteId) => {
    if (!activeStudent || !noteId) return;
    setNoteBusyKey(`delete:${noteId}`);
    setError("");
    try {
      const res = await apiFetch(`/students/${encodeURIComponent(activeStudent)}/notes/${encodeURIComponent(noteId)}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to delete note."));
      }
      if (editingNoteId === noteId) {
        handleCancelEditNote();
      }
      await loadStudentViews();
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setNoteBusyKey("");
    }
  };

  const handleExportReport = (format = "json") => {
    const filteredDashboard = {
      ...(studentProgress || {}),
      assignments: (studentProgress?.assignments || []).filter((item) => matchesSubjectFilter([item?.title, item?.description, item?.chapter_hint], reportSubject) && isWithinRange(item?.due_label || item?.created_at || item?.completed_at, reportRange)),
      top_subjects: (studentProgress?.top_subjects || []).filter((item) => matchesSubjectFilter(item?.subject, reportSubject)),
      recent_activity: (studentProgress?.recent_activity || []).filter((item) => matchesSubjectFilter([item?.subject, item?.chapter], reportSubject) && isWithinRange(item?.logged_at, reportRange)),
    };
    const filteredStudyPlan = {
      ...(studentStudyPlan || {}),
      targets: (studentStudyPlan?.targets || []).filter((item) => matchesSubjectFilter([item?.label, item?.chapter_hint], reportSubject)),
      schedule: (studentStudyPlan?.schedule || []).filter((item) => matchesSubjectFilter([item?.title, item?.description, item?.chapter_hint], reportSubject)),
    };
    const exportedNotes = (notes || []).filter((item) => matchesSubjectFilter([item?.note_text, item?.author_role], reportSubject) && isWithinRange(item?.created_at, reportRange));
    const payload = {
      generated_at: new Date().toISOString(),
      filters: {
        subject: reportSubject || null,
        range: reportRange,
      },
      student_username: activeStudent,
      dashboard: filteredDashboard,
      insights: studentInsights,
      study_plan: filteredStudyPlan,
      notes: exportedNotes,
      report_summary: {
        open_assignments: (filteredDashboard.assignments || []).filter((item) => item?.status !== 'completed').length,
        weekly_goal_status: studentStudyPlan?.goal_summary || null,
        history_summary: studentStudyPlan?.history?.comparison?.summary || '',
        filtered_subject: reportSubject || 'All subjects',
        report_range: reportRange,
      },
    };

    if (format === "csv") {
      const rows = [
        ["section", "label", "value"],
        ["filter", "subject", reportSubject || "All subjects"],
        ["filter", "range", reportRange],
        ["student", "username", activeStudent || ""],
        ["summary", "study_time_minutes", Math.round(Number(studentProgress?.total_study_seconds || 0) / 60)],
        ["summary", "streak_days", studentProgress?.streak_days || 0],
        ...((filteredStudyPlan?.targets || []).map((target) => ["goal", target.label || target.id, `${target.current || 0}/${target.target || 0} ${target.unit || ""}`])),
        ...((filteredDashboard.assignments || []).map((item) => ["assignment", item.title || item.id, item.status || "assigned"])),
        ...((exportedNotes || []).map((item) => ["note", item.author_role || item.id, item.note_text || ""])),
      ];
      const csv = rows.map((row) => row.map((value) => `"${String(value ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
      downloadTextFile("student-progress-report.csv", csv, "text/csv;charset=utf-8");
      return;
    }

    downloadTextFile("student-progress-report.json", JSON.stringify(payload, null, 2), "application/json;charset=utf-8");
  };

  const handlePrintReport = () => {
    if (typeof window !== "undefined" && typeof window.print === "function") {
      window.print();
    }
  };

  return (
    <section className="workspace-panel role-hub-panel">
      <div className="role-hub-panel__note-actions" style={{ justifyContent: "flex-end", marginBottom: 12 }}>
        <button type="button" className="icon-button icon-button--ghost" onClick={loadRoleData}>
          <FiRefreshCw />
          <span>Refresh</span>
        </button>
        {isMentorRole ? (
          <>
            {onPlanAction ? (
              <button
                type="button"
                className="secondary-button"
                onClick={() =>
                  onPlanAction({
                    id: "open-student-assignments",
                    action_tab: "assignments",
                    cta_label: "Open Student Assignments",
                    context_hint: "Review and manage work assigned to your linked learner.",
                  })
                }
              >
                Open Student Assignments
              </button>
            ) : null}
            <button type="button" className="secondary-button" onClick={() => handleExportReport("json")}>
              Export Student JSON
            </button>
            <button type="button" className="secondary-button" onClick={() => handleExportReport("csv")}>
              Export Student CSV
            </button>
            <button type="button" className="secondary-button" onClick={handlePrintReport}>
              Print / Save PDF
            </button>
          </>
        ) : null}
      </div>

      {error && <div className="subscription-modal__error">{error}</div>}

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
        {isAdminRole ? (
          <div className="role-hub-panel__note-actions">
            <span>Admin-only controls now live in the dedicated Admin Center tab.</span>
          </div>
        ) : null}
      </div>

      {isMentorRole ? (
        <>
          <div className="role-hub-panel__row">
            <input
              type="email"
              placeholder="student@example.com"
              value={studentEmail}
              onChange={(e) => setStudentEmail(e.target.value)}
            />
            <input
              type="text"
              placeholder="Relation label (optional)"
              value={relationLabel}
              onChange={(e) => setRelationLabel(e.target.value)}
            />
            <button type="button" className="secondary-button" onClick={handleLinkStudent}>
              <FiLink />
              <span>Link Student</span>
            </button>
            <button type="button" className="secondary-button" onClick={handleUnlinkSelectedStudent} disabled={!activeStudent}>
              <FiTrash2 />
              <span>Unlink Selected</span>
            </button>
          </div>
          <p className="sidebar-note">
            Linking is direct for existing student accounts. Teachers and parents can only access students they have linked.
          </p>

          {previewRole === "teacher" ? (
            <>
              <div className="role-hub-panel__note-box">
                <strong>Assignment Templates</strong>
                <p className="sidebar-note">Start with a reusable class routine and send it to the selected learners.</p>
                <p className="sidebar-note">Saved templates are stored in your browser only. Use export/import JSON to move templates between devices.</p>
                <div className="role-hub-panel__note-actions">
                  {DEFAULT_ASSIGNMENT_TEMPLATES.map((template) => (
                    <button
                      key={template.id}
                      type="button"
                      className="secondary-button"
                      onClick={() => handleApplyAssignmentTemplate(template)}
                    >
                      {template.label}
                    </button>
                  ))}
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={handleSaveAssignmentTemplate}
                    disabled={!assignmentSubject.trim() && !assignmentNote.trim()}
                  >
                    Save as Template
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={handleExportTemplateLibrary}
                    disabled={savedAssignmentTemplates.length === 0}
                  >
                    Export Template Library
                  </button>
                </div>
                <label style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10 }}>
                  <span>Import template JSON</span>
                  <textarea
                    aria-label="Import template JSON"
                    rows={3}
                    value={templateImportText}
                    onChange={(event) => setTemplateImportText(event.target.value)}
                    placeholder='Paste shared template JSON here'
                  />
                </label>
                <div className="role-hub-panel__note-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={handleImportTemplateLibrary}
                    disabled={!templateImportText.trim()}
                  >
                    Import Shared Templates
                  </button>
                  {templateImportStatus ? <span>{templateImportStatus}</span> : null}
                </div>
              </div>

              {savedAssignmentTemplates.length > 0 ? (
                <div className="role-hub-panel__note-box">
                  <strong>Saved Templates</strong>
                  <p className="sidebar-note">Reuse your own saved class routines any time. Saved templates are stored locally in the browser.</p>
                  <div className="role-hub-panel__note-actions">
                    <span>{savedTemplateSummary.totalCount} saved templates</span>
                    <span>{savedTemplateSummary.favoriteCount} favorites</span>
                    {savedTemplateSummary.totalCount > 1 || savedTemplateSummary.favoriteCount > 0 ? (
                      <>
                        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span>Saved template category</span>
                          <select
                            aria-label="Saved template category"
                            value={savedTemplateCategoryFilter}
                            onChange={(event) => setSavedTemplateCategoryFilter(event.target.value)}
                          >
                            <option value="all">All categories</option>
                            <option value="general">General</option>
                            <option value="stem">STEM</option>
                            <option value="humanities">Humanities</option>
                            <option value="languages">Languages</option>
                            <option value="exam">Exam Prep</option>
                          </select>
                        </label>
                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => setShowFavoriteTemplatesOnly((current) => !current)}
                        >
                          {showFavoriteTemplatesOnly ? "Show All Templates" : "Show Favorites Only"}
                        </button>
                      </>
                    ) : null}
                  </div>
                  {filteredSavedTemplates.map((template) => {
                    const isEditingTemplate = editingTemplateId === template.id;
                    return (
                      <div key={template.id} className="role-hub-panel__note-box" style={{ marginTop: 8 }}>
                        {isEditingTemplate ? (
                          <>
                            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                              <span>Template name</span>
                              <input
                                aria-label="Template name"
                                type="text"
                                value={editingTemplateLabel}
                                onChange={(event) => setEditingTemplateLabel(event.target.value)}
                              />
                            </label>
                            <div className="role-hub-panel__note-actions">
                              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                                <span>Template type</span>
                                <select
                                  aria-label="Template type"
                                  value={editingTemplateType}
                                  onChange={(event) => setEditingTemplateType(event.target.value)}
                                >
                                  <option value="lesson">Lesson</option>
                                  <option value="quiz">Quiz</option>
                                  <option value="assessment">Assessment</option>
                                  <option value="chat">Chat</option>
                                  <option value="flashcards">Flashcards</option>
                                </select>
                              </label>
                              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                                <span>Edit template category</span>
                                <select
                                  aria-label="Edit template category"
                                  value={editingTemplateCategory}
                                  onChange={(event) => setEditingTemplateCategory(event.target.value)}
                                >
                                  <option value="general">General</option>
                                  <option value="stem">STEM</option>
                                  <option value="humanities">Humanities</option>
                                  <option value="languages">Languages</option>
                                  <option value="exam">Exam Prep</option>
                                </select>
                              </label>
                              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                                <span>Template subject</span>
                                <input
                                  aria-label="Template subject"
                                  type="text"
                                  value={editingTemplateSubject}
                                  onChange={(event) => setEditingTemplateSubject(event.target.value)}
                                />
                              </label>
                            </div>
                            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                              <span>Template note</span>
                              <input
                                aria-label="Template note"
                                type="text"
                                value={editingTemplateNote}
                                onChange={(event) => setEditingTemplateNote(event.target.value)}
                              />
                            </label>
                            <div className="role-hub-panel__note-actions">
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={handleSaveEditedTemplate}
                                disabled={!editingTemplateLabel.trim()}
                              >
                                Save Template Changes
                              </button>
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={handleCancelEditTemplate}
                              >
                                Cancel Template Edit
                              </button>
                            </div>
                          </>
                        ) : (
                          <>
                            <div className="role-hub-panel__note-actions">
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() => handleApplyAssignmentTemplate(template)}
                              >
                                {template.label}
                              </button>
                              <span>{formatTemplateCategoryLabel(template.category)}</span>
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() => handlePreviewSavedTemplate(template.id)}
                              >
                                Preview {template.label}
                              </button>
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() => handleDuplicateSavedTemplate(template)}
                              >
                                Duplicate {template.label}
                              </button>
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() => handleToggleTemplateFavorite(template.id)}
                              >
                                {template.isFavorite ? `Unfavorite ${template.label}` : `Favorite ${template.label}`}
                              </button>
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() => handleStartEditTemplate(template)}
                              >
                                Edit {template.label}
                              </button>
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() => handleDeleteSavedTemplate(template.id)}
                              >
                                Remove Template
                              </button>
                            </div>
                            {previewTemplateId === template.id ? (
                              <div className="role-hub-panel__note-box" style={{ marginTop: 8 }}>
                                <strong>Template Preview</strong>
                                <p className="sidebar-note">
                                  {formatTemplateTypeLabel(template.assignmentType)} · {template.subject || "General"} · {formatTemplateCategoryLabel(template.category)}
                                </p>
                                <p>{template.note}</p>
                              </div>
                            ) : null}
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : null}
            </>
          ) : null}

          {students.length > 1 ? (
            <div className="role-hub-panel__note-box">
              <strong>Assignment Recipients</strong>
              <div className="role-hub-panel__note-actions">
                <span>{assignmentTargetUsers.length} learners selected</span>
                <button type="button" className="secondary-button" onClick={handleUseAllAssignmentTargets}>
                  Select All Learners
                </button>
                <button type="button" className="secondary-button" onClick={handleUseActiveAssignmentTarget}>
                  Use Active Learner Only
                </button>
              </div>
              <div className="role-hub-panel__row">
                {students.map((item) => (
                  <label key={`assignment-target-${item.username}`} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <input
                      type="checkbox"
                      aria-label={`Assign to ${item.first_name || item.email}`}
                      checked={assignmentTargetUsers.includes(item.username)}
                      onChange={() => handleToggleAssignmentTarget(item.username)}
                    />
                    <span>{item.first_name || item.email}</span>
                  </label>
                ))}
              </div>
            </div>
          ) : null}

          <div className="role-hub-panel__row">
            <select value={assignmentType} onChange={(e) => setAssignmentType(e.target.value)}>
              <option value="lesson">Lesson</option>
              <option value="quiz">Quiz</option>
              <option value="assessment">Assessment</option>
              <option value="chat">Chat</option>
              <option value="flashcards">Flashcards</option>
            </select>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span>Template category</span>
              <select
                aria-label="Template category"
                value={templateCategory}
                onChange={(e) => setTemplateCategory(e.target.value)}
              >
                <option value="general">General</option>
                <option value="stem">STEM</option>
                <option value="humanities">Humanities</option>
                <option value="languages">Languages</option>
                <option value="exam">Exam Prep</option>
              </select>
            </label>
            <input
              type="text"
              placeholder="Focus subject or chapter"
              value={assignmentSubject}
              onChange={(e) => setAssignmentSubject(e.target.value)}
            />
            <input
              type="text"
              placeholder="Mentor note (optional)"
              value={assignmentNote}
              onChange={(e) => setAssignmentNote(e.target.value)}
            />
            <input
              type="date"
              placeholder="Optional due date"
              value={assignmentDueLabel}
              onChange={(e) => setAssignmentDueLabel(e.target.value)}
            />
            <button type="button" className="secondary-button" onClick={handleAssignTask} disabled={assignmentTargetUsers.length === 0 || assignmentSubmitting}>
              <span>{assignmentButtonLabel}</span>
            </button>
          </div>

          <div className="role-hub-panel__row">
            <input
              type="text"
              placeholder="Search notes or assignments"
              value={workspaceSearch}
              onChange={(e) => setWorkspaceSearch(e.target.value)}
            />
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span>Assignment filter</span>
              <select
                aria-label="Assignment filter"
                value={assignmentFilter}
                onChange={(e) => setAssignmentFilter(e.target.value)}
              >
                <option value="all">All</option>
                <option value="open">Open</option>
                <option value="overdue">Overdue</option>
                <option value="due-soon">Due soon</option>
                <option value="completed">Completed</option>
                <option value="dismissed">Dismissed</option>
              </select>
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span>Note access</span>
              <select
                aria-label="Note access filter"
                value={noteVisibilityFilter}
                onChange={(e) => setNoteVisibilityFilter(e.target.value)}
              >
                <option value="all">All notes</option>
                <option value="guardians">Guardians only</option>
              </select>
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span>Assignment sort</span>
              <select
                aria-label="Assignment sort"
                value={assignmentSort}
                onChange={(e) => setAssignmentSort(e.target.value)}
              >
                <option value="priority">Priority</option>
                <option value="due-date">Due date</option>
                <option value="title">Title</option>
              </select>
            </label>
          </div>

          <div className="role-hub-panel__row">
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span>Report subject</span>
              <input
                aria-label="Report subject"
                type="text"
                placeholder="All subjects"
                value={reportSubject}
                onChange={(e) => setReportSubject(e.target.value)}
              />
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span>Report range</span>
              <select
                aria-label="Report range"
                value={reportRange}
                onChange={(e) => setReportRange(e.target.value)}
              >
                <option value="all">All time</option>
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
                <option value="90d">Last 90 days</option>
              </select>
            </label>
          </div>

          <div className="role-hub-panel__list">
            {students.map((item) => (
              <button
                key={`${item.username}-${item.linked_at}`}
                type="button"
                className={`role-hub-panel__student ${selectedStudent === item.username ? "is-active" : ""}`}
                onClick={() => setSelectedStudent(item.username)}
              >
                <strong>{item.first_name || item.email}</strong>
                <span>{item.email}</span>
                {item.relation_label ? <small>{item.relation_label}</small> : null}
              </button>
            ))}
            {!loading && students.length === 0 && <p className="sidebar-note">No linked students yet.</p>}
          </div>

          {teacherRosterSummary && (
            <div className="role-hub-panel__insights">
              <div className="role-hub-panel__insight-card">
                <strong>Class Roster Overview</strong>
                <p>
                  Manage linked learners, keep the selected student in focus, and track assignment load across your roster.
                </p>
                <span>{teacherRosterSummary.learnerCount} linked learners</span>
                <span>Selected learner {teacherRosterSummary.selectedLearner}</span>
                <span>{teacherRosterSummary.rosterLabelSummary}</span>
                <span>{teacherRosterSummary.openAssignmentsCount} active assignments</span>
                {onPlanAction ? (
                  <button
                    type="button"
                    className="secondary-button progress-plan-item__action"
                    onClick={() =>
                      onPlanAction({
                        id: "teacher-roster-assignments",
                        action_tab: "assignments",
                        cta_label: "Review Roster Assignments",
                        context_hint: "Open the assignments workspace to review tasks for the selected learner.",
                      })
                    }
                  >
                    Review Roster Assignments
                  </button>
                ) : null}
              </div>
              {teacherClassSummary ? (
                <div className="role-hub-panel__insight-card">
                  <strong>Class Progress Snapshot</strong>
                  <p>
                    Track which learners are on pace this week and who may need extra support before the next due date.
                  </p>
                  <span>{teacherClassSummary.learnerCount} learners tracked</span>
                  <span>{teacherClassSummary.onTrackCount} on track</span>
                  <span>{teacherClassSummary.needsAttentionCount} needs attention</span>
                  {teacherClassSummary.classAverageScore > 0 ? (
                    <span>{teacherClassSummary.classAverageScore}% class avg</span>
                  ) : null}
                  <span>{teacherClassSummary.averageStreak} day avg streak</span>
                  <span>Focus support: {teacherClassSummary.focusLearnerName}</span>
                  {onPlanAction ? (
                    <button
                      type="button"
                      className="secondary-button progress-plan-item__action"
                      onClick={() =>
                        onPlanAction({
                          id: "teacher-class-progress",
                          action_tab: "progress",
                          cta_label: "Open Weekly Progress",
                          context_hint: "Review the selected learner's weekly goals and class momentum.",
                        })
                      }
                    >
                      Open Weekly Progress
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          )}

          {parentSummary && (
            <div className="role-hub-panel__insights">
              <div className="role-hub-panel__insight-card">
                <strong>Parent Dashboard Summary</strong>
                <p>
                  {parentSummary.learnerName} currently has {parentSummary.openAssignmentsCount} open task{parentSummary.openAssignmentsCount === 1 ? "" : "s"}
                  {parentSummary.streakDays > 0 ? ` and a ${parentSummary.streakDays}-day study streak.` : "."}
                </p>
                <span>{parentSummary.openAssignmentsCount} open tasks</span>
                <span>Next due {parentSummary.nextDueLabel}</span>
                <span>{parentSummary.averageScore}% avg</span>
                {parentSummary.latestScore > 0 ? (
                  <span>
                    Latest {parentSummary.latestScore}%
                    {parentSummary.latestSubject ? ` in ${parentSummary.latestSubject}` : ""}
                  </span>
                ) : null}
                <span>Current focus: {parentSummary.nextDueTitle}</span>
                {onPlanAction ? (
                  <button
                    type="button"
                    className="secondary-button progress-plan-item__action"
                    onClick={() =>
                      onPlanAction({
                        id: "parent-review-assignments",
                        action_tab: "assignments",
                        cta_label: "Open Student Assignments",
                        context_hint: "Review upcoming learner tasks and due dates.",
                      })
                    }
                  >
                    Open Student Assignments
                  </button>
                ) : null}
              </div>
            </div>
          )}

          {studentProgress && (
            <div className="role-hub-panel__stats">
              <div><strong>Study Time</strong><span>{Math.round((studentProgress.total_study_seconds || 0) / 60)} min</span></div>
              <div><strong>Streak</strong><span>{studentProgress.streak_days || 0} days</span></div>
              <div><strong>Quizzes</strong><span>{studentProgress.totals?.quizzes || 0}</span></div>
              {Number(studentProgress.assessment_summary?.attempt_count || 0) > 0 && (
                <>
                  <div>
                    <strong>Assessment Avg</strong>
                    <span>{studentProgress.assessment_summary?.average_score_pct || 0}% avg</span>
                  </div>
                  <div>
                    <strong>Best</strong>
                    <span>Best {studentProgress.assessment_summary?.best_score_pct || 0}%</span>
                  </div>
                  <div>
                    <strong>Latest</strong>
                    <span>
                      Latest {studentProgress.assessment_summary?.latest_score_pct || 0}%
                      {studentProgress.assessment_summary?.latest_subject ? ` in ${studentProgress.assessment_summary.latest_subject}` : ""}
                    </span>
                  </div>
                  <div>
                    <strong>Attempts</strong>
                    <span>
                      {studentProgress.assessment_summary?.attempt_count || 0} attempts
                      {Number(studentProgress.assessment_summary?.attempted_assessments || 0) > 0
                        ? ` · ${studentProgress.assessment_summary.attempted_assessments} papers`
                        : ""}
                    </span>
                  </div>
                  {studentProgress.assessment_summary?.last_attempted_at ? (
                    <div>
                      <strong>Last attempt</strong>
                      <span>Last attempt {String(studentProgress.assessment_summary.last_attempted_at).split("T")[0]}</span>
                    </div>
                  ) : null}
                  {Array.isArray(studentProgress.assessment_summary?.recent_scores) && studentProgress.assessment_summary.recent_scores.length > 0 && (
                    <div>
                      <strong>Recent</strong>
                      <span>Recent {studentProgress.assessment_summary.recent_scores.map((score) => `${score}%`).join(", ")}</span>
                    </div>
                  )}
                  {Array.isArray(studentProgress.assessment_summary?.recent_scores) && studentProgress.assessment_summary.recent_scores.length > 1 ? (
                    <div>
                      <strong>Trend</strong>
                      <MiniTrendChart scores={studentProgress.assessment_summary.recent_scores} label="Assessment trend" />
                    </div>
                  ) : null}
                </>
              )}
            </div>
          )}

          {studentInsights && (
            <div className="role-hub-panel__insights">
              <div className="role-hub-panel__insight-card">
                <strong>Coaching Insights</strong>
                {studentInsights.headline && <p>{studentInsights.headline}</p>}
              </div>

              {(studentInsights.notifications || []).map((item) => (
                <div key={item.id || item.title} className="role-hub-panel__insight-card">
                  <strong>{item.title}</strong>
                  <p>{item.message}</p>
                  {item.severity ? (
                    <span className={`progress-pill progress-pill--${item.severity}`}>
                      {item.severity}
                    </span>
                  ) : null}
                </div>
              ))}

              {(studentInsights.recommendations || []).map((item) => (
                <div key={item.id || item.title} className="role-hub-panel__insight-card">
                  <strong>{item.title}</strong>
                  <p>{item.description}</p>
                  {item.priority ? (
                    <span className={`progress-pill progress-pill--${item.priority}`}>
                      {item.priority}
                    </span>
                  ) : null}
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
                </div>
              ))}

              {(studentInsights.badges || []).slice(0, 2).map((badge) => (
                <div key={badge.id || badge.label} className="role-hub-panel__insight-card">
                  <strong>{badge.label}</strong>
                  <p>{badge.description}</p>
                  <span>{badge.progress_pct || 0}% complete</span>
                </div>
              ))}
            </div>
          )}

          {studentStudyPlan && (
            <div className="role-hub-panel__insights">
              <div className="role-hub-panel__insight-card">
                <strong>Student Weekly Plan</strong>
                {studentStudyPlan.headline && <p>{studentStudyPlan.headline}</p>}
                {studentStudyPlan.goal_summary && (
                  <span>
                    {studentStudyPlan.goal_summary.completed || 0} of {studentStudyPlan.goal_summary.total || 0} complete
                  </span>
                )}
              </div>

              {studentStudyPlan.history ? (
                <div className="role-hub-panel__insight-card">
                  <strong>Last Week Snapshot</strong>
                  <p>{studentStudyPlan.history?.comparison?.summary || "This week is now being tracked."}</p>
                  {studentStudyPlan.history?.previous_week ? (
                    <span>
                      {studentStudyPlan.history.previous_week.goal_completed || 0} / {studentStudyPlan.history.previous_week.goal_total || 0} goals last week
                    </span>
                  ) : null}
                </div>
              ) : null}

              {(studentStudyPlan.targets || []).slice(0, 3).map((target) => (
                <div key={target.id || target.label} className="role-hub-panel__insight-card">
                  <strong>{target.label}</strong>
                  <p>
                    {target.current || 0} / {target.target || 0} {target.unit || ""}
                  </p>
                  <span>{target.completed ? "Done" : "In progress"}</span>
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
                </div>
              ))}

              {(studentStudyPlan.schedule || []).slice(0, 3).map((step) => (
                <div key={step.id || step.title} className="role-hub-panel__insight-card">
                  <strong>{step.title}</strong>
                  <p>{step.description}</p>
                  <span>{step.status_label || (step.completed ? "Done" : "Coming up")}</span>
                  {step.duration_minutes ? <span>{step.duration_minutes} min</span> : null}
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
                </div>
              ))}
            </div>
          )}

          {((studentProgress?.assignments || []).length > 0 || studentMastery.length > 0 || (studentProgress?.top_subjects || []).length > 0 || (studentProgress?.recent_activity || []).length > 0) && (
            <div className="role-hub-panel__insights">
              {(studentProgress?.assignments || []).length > 0 && (
                <div className="role-hub-panel__insight-card">
                  <strong>Assigned Tasks</strong>
                  <div className="role-hub-panel__note-box" style={{ marginTop: 12 }}>
                    <strong>Bulk Assignment Actions</strong>
                    <p className="sidebar-note">
                      Apply quick updates to the assignments currently visible for {teacherRosterSummary?.selectedLearner || "the selected learner"}.
                    </p>
                    <div className="role-hub-panel__note-actions">
                      <span>{bulkAssignmentSummary.openVisibleCount} open visible</span>
                      <span>{bulkAssignmentSummary.overdueVisibleCount} overdue</span>
                      {bulkAssignmentSummary.dismissedVisibleCount > 0 ? (
                        <span>{bulkAssignmentSummary.dismissedVisibleCount} dismissed</span>
                      ) : null}
                    </div>
                    <div className="role-hub-panel__note-actions">
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => handleBulkAssignmentUpdate("complete-open")}
                        disabled={assignmentBusyKey.startsWith("bulk:") || bulkAssignmentSummary.openVisibleCount === 0}
                      >
                        Mark Open Done
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => handleBulkAssignmentUpdate("dismiss-overdue")}
                        disabled={assignmentBusyKey.startsWith("bulk:") || bulkAssignmentSummary.overdueVisibleCount === 0}
                      >
                        Dismiss Overdue
                      </button>
                      {bulkAssignmentSummary.dismissedVisibleCount > 0 ? (
                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => handleBulkAssignmentUpdate("reopen-dismissed")}
                          disabled={assignmentBusyKey.startsWith("bulk:")}
                        >
                          Reopen Dismissed
                        </button>
                      ) : null}
                    </div>
                  </div>
                  {filteredAssignments.length === 0 ? (
                    <p className="sidebar-note">No assignments match the current filters.</p>
                  ) : filteredAssignments.map((item) => {
                    const busy = assignmentBusyKey === `edit:${item.id}` || assignmentBusyKey === `update:${item.id}` || assignmentBusyKey === `delete:${item.id}` || assignmentBusyKey.startsWith("bulk:");
                    const dueMeta = getAssignmentDueMeta(item.due_label);
                    const statusLabel = item.status === 'completed' ? 'Done' : item.status === 'dismissed' ? 'Dismissed' : 'Assigned';
                    const isEditingAssignment = editingAssignmentId === item.id;
                    return (
                      <div key={item.id || item.title}>
                        {isEditingAssignment ? (
                          <div className="role-hub-panel__note-box">
                            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                              <span>Assignment title</span>
                              <input
                                aria-label="Assignment title"
                                type="text"
                                value={editingAssignmentTitle}
                                onChange={(event) => setEditingAssignmentTitle(event.target.value)}
                              />
                            </label>
                            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                              <span>Assignment note</span>
                              <textarea
                                aria-label="Assignment note"
                                rows={3}
                                value={editingAssignmentDescription}
                                onChange={(event) => setEditingAssignmentDescription(event.target.value)}
                              />
                            </label>
                            <div className="role-hub-panel__note-actions">
                              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                                <span>Assignment type</span>
                                <select
                                  aria-label="Assignment type"
                                  value={editingAssignmentType}
                                  onChange={(event) => setEditingAssignmentType(event.target.value)}
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
                                  onChange={(event) => setEditingAssignmentDueLabel(event.target.value)}
                                  placeholder="Optional due date"
                                />
                              </label>
                              <button
                                type="button"
                                className="primary-button"
                                onClick={() => handleSaveAssignment(item.id)}
                                disabled={busy || !editingAssignmentTitle.trim() || !editingAssignmentDescription.trim()}
                              >
                                Save Assignment
                              </button>
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={handleCancelEditAssignment}
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
                              <span>{statusLabel}{item.due_label ? ` · Due ${item.due_label}` : ''}</span>
                              {dueMeta.label ? (
                                <span className={`progress-pill progress-pill--${dueMeta.tone}`}>
                                  {dueMeta.label}
                                </span>
                              ) : null}
                            </div>
                          </>
                        )}
                        {!isEditingAssignment && item.cta_label ? (
                          <button
                            type="button"
                            className="secondary-button progress-plan-item__action"
                            onClick={() => onPlanAction?.(item)}
                            disabled={!onPlanAction}
                          >
                            {item.cta_label}
                          </button>
                        ) : null}
                        {isEditingAssignment ? null : (
                          <button
                            type="button"
                            className="secondary-button progress-plan-item__action"
                            onClick={() => handleStartEditAssignment(item)}
                            disabled={busy}
                          >
                            Edit Assignment
                          </button>
                        )}
                        {isEditingAssignment ? null : (
                          <button
                            type="button"
                            className="secondary-button progress-plan-item__action"
                            onClick={() => handleUpdateAssignment(item.id, { status: item.status === 'dismissed' ? 'assigned' : 'dismissed' })}
                            disabled={busy}
                          >
                            {item.status === 'dismissed' ? 'Reopen Assignment' : 'Dismiss Assignment'}
                          </button>
                        )}
                        <button
                          type="button"
                          className="secondary-button progress-plan-item__action"
                          onClick={() => handleDeleteAssignment(item.id)}
                          disabled={busy}
                        >
                          Delete Assignment
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}

              {studentMastery.length > 0 && (
                <div className="role-hub-panel__insight-card">
                  <strong>Subject Mastery</strong>
                  {(studentMastery || []).slice(0, 3).map((item) => {
                    const subjectLabel = item.subject || item.chapter || "Topic";
                    return (
                      <div key={`${item.subject}-${item.chapter}`}>
                        <p>
                          {item.subject}{item.chapter ? ` — ${item.chapter}` : ''} · {item.mastery_pct || 0}% mastery
                        </p>
                        {onPlanAction ? (
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
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              )}

              {(studentProgress?.top_subjects || []).length > 0 && (
                <div className="role-hub-panel__insight-card">
                  <strong>Time by Subject</strong>
                  {(studentProgress.top_subjects || []).slice(0, 3).map((item, index) => {
                    const subjectLabel = item.subject || item.chapter || "Topic";
                    const action = buildTopSubjectAction(item);
                    return (
                      <div key={`${subjectLabel}-${index}`}>
                        <p>{subjectLabel}</p>
                        <span>{Math.max(1, Math.round(Number(item.study_seconds || 0) / 60))} min</span>
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
              )}

              {(studentProgress?.recent_activity || []).length > 0 && (
                <div className="role-hub-panel__insight-card">
                  <strong>Recent Activity</strong>
                  {(studentProgress.recent_activity || []).slice(0, 3).map((item, index) => {
                    const primaryLabel = item.subject && item.chapter && item.subject !== item.chapter
                      ? `${item.subject} — ${item.chapter}`
                      : item.subject || item.chapter || item.activity_type;
                    const detailParts = [];
                    const action = buildRecentActivityAction(item);
                    if (item.activity_type) {
                      detailParts.push(String(item.activity_type).replace(/_/g, " "));
                    }
                    if (Number(item.duration_seconds || 0) > 0) {
                      detailParts.push(`${Math.max(1, Math.round(Number(item.duration_seconds || 0) / 60))} min`);
                    }
                    return (
                      <div key={`${item.activity_type}-${item.subject}-${index}`}>
                        <p>{primaryLabel}</p>
                        {detailParts.length > 0 ? <span>{detailParts.join(" · ")}</span> : null}
                        {action?.cta_label ? (
                          <button
                            type="button"
                            className="secondary-button progress-plan-item__action"
                            onClick={() => onPlanAction?.(action)}
                            disabled={!onPlanAction}
                          >
                            {action.ctaLabel || action.cta_label}
                          </button>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          <div className="role-hub-panel__note-box">
            <textarea
              placeholder="Add a coaching note for this student..."
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              rows={3}
            />
            <div className="role-hub-panel__note-actions">
              <select value={visibility} onChange={(e) => setVisibility(e.target.value)}>
                <option value="all">Visible to all mentors</option>
                <option value="guardians">Only visible to guardians + author</option>
              </select>
              <button type="button" className="primary-button" onClick={handleCreateNote}>
                Add Note
              </button>
            </div>
          </div>
        </>
      ) : isStudentRole ? (
        <div className="role-hub-panel__list">
          <h4>My Mentors</h4>
          {mentors.map((item) => (
            <div key={`${item.username}-${item.linked_at}`} className="role-hub-panel__student">
              <strong>{item.first_name || item.email}</strong>
              <span>{item.role} · {item.email}</span>
            </div>
          ))}
          {!loading && mentors.length === 0 && <p className="sidebar-note">No mentors connected yet.</p>}

          <div className="role-hub-panel__student">
            <strong>Teacher assignments</strong>
            <span>Your assigned work appears in the dedicated <strong>Assignments</strong> workspace.</span>
            {onPlanAction ? (
              <button
                type="button"
                className="secondary-button progress-plan-item__action"
                onClick={() =>
                  onPlanAction({
                    id: "review-mentor-assignments",
                    action_tab: "assignments",
                    cta_label: "Review Mentor Assignments",
                    context_hint: "Open Assignments to review work shared by your teacher or parent.",
                  })
                }
              >
                Review Mentor Assignments
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="role-hub-panel__notes">
        <h4>Recent Notes</h4>
        {filteredNotes.map((n) => {
          const canManageNote = isMentorRole && (n.author_user_id === username || role === "admin");
          const visibilityLabel = n.visibility === "guardians" ? "guardians + author" : "all mentors";
          const isEditingThisNote = editingNoteId === n.id;
          return (
            <div key={n.id} className="role-hub-panel__note-item">
              <strong>{n.author_role}</strong>
              {isEditingThisNote ? (
                <div className="role-hub-panel__note-box">
                  <textarea
                    value={editingNoteText}
                    onChange={(event) => setEditingNoteText(event.target.value)}
                    rows={3}
                  />
                  <div className="role-hub-panel__note-actions">
                    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      <span>Note visibility</span>
                      <select
                        aria-label="Note visibility"
                        value={editingNoteVisibility}
                        onChange={(event) => setEditingNoteVisibility(event.target.value)}
                      >
                        <option value="all">all</option>
                        <option value="guardians">guardians</option>
                      </select>
                    </label>
                    <button
                      type="button"
                      className="primary-button"
                      onClick={() => handleSaveNote(n.id)}
                      disabled={noteBusyKey === `edit:${n.id}` || !editingNoteText.trim()}
                    >
                      Save Note
                    </button>
                    <button type="button" className="secondary-button" onClick={handleCancelEditNote}>
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <p>{n.note_text}</p>
              )}
              <div className="progress-plan-item__meta">
                <span>{visibilityLabel}</span>
                {n.created_at ? <span>{formatNoteDate(n.created_at)}</span> : null}
              </div>
              {canManageNote ? (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {!isEditingThisNote ? (
                    <button
                      type="button"
                      className="secondary-button progress-plan-item__action"
                      onClick={() => handleStartEditNote(n)}
                    >
                      Edit Note
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="secondary-button progress-plan-item__action"
                    onClick={() => handleDeleteNote(n.id)}
                    disabled={noteBusyKey === `delete:${n.id}`}
                  >
                    Delete Note
                  </button>
                </div>
              ) : null}
            </div>
          );
        })}
        {!loading && notes.length === 0 && <p className="sidebar-note">No notes yet.</p>}
        {!loading && notes.length > 0 && filteredNotes.length === 0 && <p className="sidebar-note">No notes match the current search.</p>}
      </div>
    </section>
  );
}
