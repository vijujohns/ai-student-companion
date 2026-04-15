import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  FiGlobe,
  FiArrowDown,
  FiBook,
  FiBookOpen,
  FiCheck,
  FiClipboard,
  FiCreditCard,
  FiExternalLink,
  FiEye,
  FiEyeOff,
  FiEdit,
  FiFileText,
  FiFolder,
  FiLayers,
  FiMaximize2,
  FiMenu,
  FiMessageSquare,
  FiMinimize2,
  FiPlus,
  FiRefreshCw,
  FiSend,
  FiShield,
  FiSquare,
  FiTrash2,
  FiBarChart2,
  FiUser,
  FiVolume2,
  FiVolumeX,
  FiX,
  FiZap,
} from "react-icons/fi";
import { apiFetch, parseApiError, getEnvelopeMessage, messageSummary } from "../services/api";
import { sendMessage } from "../services/websocket";
import { useChatSendMessage } from "../hooks/useChatSendMessage";
import { useChatWebSocketLifecycle } from "../hooks/useChatWebSocketLifecycle";
import { useChatScroll } from "../hooks/useChatScroll";
import { usePlanSummary } from "../hooks/usePlanSummary";
import { useScopedSessionActions } from "../hooks/useScopedSessionActions";
import { useSessionLoaders } from "../hooks/useSessionLoaders";
import { useKnowledgeBaseLoader } from "../hooks/useKnowledgeBaseLoader";
import { useKnowledgeBaseSelectionHandlers } from "../hooks/useKnowledgeBaseSelectionHandlers";
import { useStreamTimers } from "../hooks/useStreamTimers";
import { useChatComposerLayout } from "../hooks/useChatComposerLayout";
import { useViewerLayout } from "../hooks/useViewerLayout";
import { filterSessionsByContext } from "../utils/chatPanelSelectors";
import { buildKnowledgeBaseStatusMessage, countPendingUploadsInScope } from "../utils/kbSelectors";
import {
  buildCompletedStreamMessage,
  isWebsocketErrorToken,
  mergeStreamMeta,
  normalizeStreamPayload,
  resetStreamMeta,
  shouldCommitCompletedStream,
  shouldSkipStreamPayload,
  shouldSpeakText,
} from "../utils/streamToken";
import { speakText } from "../utils/speech";
import FlashcardPanel from "./FlashcardPanel";
import LessonPanel from "./LessonPanel";
import AssessmentPanel from "./AssessmentPanel";
import AssignmentsPanel from "./AssignmentsPanel";
import ProgressPanel from "./ProgressPanel";
import RoleHubPanel from "./RoleHubPanel";
import AdminPanel from "./AdminPanel";
import MessageContent from "./MessageContent";
import NotesPanel from "./NotesPanel";
import QuizPanel from "./QuizPanel";
import SummaryViewer, { looksLikeStructuredSummary } from "./SummaryViewer";
import VoiceControl from "./VoiceControl";
import LanguagePicker from "./LanguagePicker";
import ProfilePanel from "./ProfilePanel";
import BillingPanel from "./BillingPanel";
import "./style.css";

function formatInrFromCents(cents, currency = "INR") {
  const amount = Number(cents || 0) / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

function getActivePanelMeta(activeTab, userRole = "student") {
  const normalizedRole = String(userRole || "student").toLowerCase() === "user"
    ? "student"
    : String(userRole || "student").toLowerCase();
  const roleHubTitle = normalizedRole === "teacher"
    ? "Teacher Hub"
    : normalizedRole === "parent"
      ? "Family Hub"
      : "Role Hub";
  const roleHubDescription = normalizedRole === "teacher"
    ? "Manage linked learners, assignments, and class progress without extra student screens."
    : normalizedRole === "parent"
      ? "Keep up with your learner’s assignments, notes, and progress in one place."
      : normalizedRole === "admin"
        ? "Preview the selected role workspace without the admin-only settings mixed into it."
        : "Review linked learners, mentor notes, and shared progress views.";

  switch (activeTab) {
    case "lesson":
      return {
        title: "Lessons",
        description: "Use the lesson panel for guided next steps and structured teaching flow.",
      };
    case "quiz":
      return {
        title: "Quiz",
        description: "Use the quiz panel for targeted recall and rapid evaluation.",
      };
    case "flashcards":
      return {
        title: "Flashcards",
        description: "Generate and review card-based flashcards from lesson steps.",
      };
    case "assessment":
      return {
        title: "Assessment",
        description: "Build subject quizzes and question papers from your study context.",
      };
    case "assignments":
      return {
        title: "Assignments",
        description: "Review teacher tasks, watch due dates, and jump directly into the next required activity.",
      };
    case "notes":
      return {
        title: "Notes",
        description: "Review saved summaries, polish revision notes, and keep key study points in one place.",
      };
    case "progress":
      return {
        title: "Progress",
        description: "Track mastery, study streaks, and recent activity across sessions.",
      };
    case "admin":
      return {
        title: "Admin Center",
        description: "Manage global AI behavior, indexing, and the active role preview from one dedicated admin-only workspace.",
      };
    case "roles":
      return {
        title: roleHubTitle,
        description: roleHubDescription,
      };
    case "profile":
      return {
        title: "Profile",
        description: "Update account details and review the subscription and class access attached to your workspace.",
      };
    case "billing":
      return {
        title: "Billing & Plan",
        description: "See your plan status, renewal timing, active classes, and upgrade options in one workspace.",
      };
    case "chat":
    default:
      return {
        title: "Chat",
        description: "Ask questions against your selected material and keep each study session organized.",
      };
  }
}

function getWorkspaceNavSections(userRole = "student", actualUserRole = userRole) {
  const normalizedRole = String(userRole || "student").toLowerCase() === "user"
    ? "student"
    : String(userRole || "student").toLowerCase();
  const normalizedActualRole = String(actualUserRole || normalizedRole).toLowerCase() === "user"
    ? "student"
    : String(actualUserRole || normalizedRole).toLowerCase();
  const buildTab = (id, label, icon, shortLabel = label) => ({ id, label, icon, shortLabel });

  if (normalizedActualRole === "admin") {
    const previewTabs = normalizedRole === "teacher"
      ? [
        buildTab("roles", "Teacher Hub", FiUser, "Teacher Hub"),
        buildTab("notes", "Notes", FiBookOpen),
        buildTab("assignments", "Assignments", FiCheck),
        buildTab("progress", "Progress", FiBarChart2),
        buildTab("assessment", "Assessment", FiEdit),
      ]
      : normalizedRole === "parent"
        ? [
          buildTab("roles", "Family Hub", FiUser, "Family Hub"),
          buildTab("notes", "Notes", FiBookOpen),
          buildTab("assignments", "Assignments", FiCheck),
          buildTab("progress", "Progress", FiBarChart2),
        ]
        : normalizedRole === "student"
          ? [
            buildTab("chat", "Chat Workspace", FiMessageSquare, "Chat"),
            buildTab("notes", "Notes Workspace", FiBookOpen, "Notes"),
            buildTab("lesson", "Lesson Workspace", FiBook, "Lesson"),
            buildTab("quiz", "Quiz Workspace", FiClipboard, "Quiz"),
            buildTab("flashcards", "Cards Workspace", FiLayers, "Cards"),
            buildTab("assignments", "Assignments", FiCheck),
            buildTab("progress", "Progress", FiBarChart2),
          ]
          : [
            buildTab("roles", "Role Hub", FiUser, "Role Hub"),
            buildTab("chat", "Chat Workspace", FiMessageSquare, "Chat"),
            buildTab("notes", "Notes Workspace", FiBookOpen, "Notes"),
            buildTab("lesson", "Lesson Workspace", FiBook, "Lesson"),
            buildTab("quiz", "Quiz Workspace", FiClipboard, "Quiz"),
            buildTab("flashcards", "Cards Workspace", FiLayers, "Cards"),
            buildTab("assignments", "Assignments", FiCheck),
            buildTab("progress", "Progress", FiBarChart2),
            buildTab("assessment", "Assessment", FiEdit),
          ];

    return [
      {
        key: "admin-access",
        title: "Admin tools",
        tabs: [buildTab("admin", "Admin Center", FiShield, "Admin")],
      },
      {
        key: "admin-preview",
        title: normalizedRole === "admin" ? "Admin preview" : `${normalizedRole.charAt(0).toUpperCase()}${normalizedRole.slice(1)} preview`,
        tabs: previewTabs,
      },
    ];
  }

  if (normalizedRole === "teacher") {
    return [
      {
        key: "teaching",
        title: "Teaching tools",
        tabs: [
          buildTab("roles", "Teacher Hub", FiShield),
          buildTab("notes", "Notes", FiBookOpen),
          buildTab("assignments", "Assignments", FiCheck),
          buildTab("progress", "Progress", FiBarChart2),
          buildTab("assessment", "Assessment", FiEdit),
        ],
      },
    ];
  }

  if (normalizedRole === "parent") {
    return [
      {
        key: "family",
        title: "Family tools",
        tabs: [
          buildTab("roles", "Family Hub", FiShield),
          buildTab("notes", "Notes", FiBookOpen),
          buildTab("assignments", "Assignments", FiCheck),
          buildTab("progress", "Progress", FiBarChart2),
        ],
      },
    ];
  }

  if (normalizedRole === "admin") {
    return [
      {
        key: "admin",
        title: "Admin tools",
        tabs: [
          buildTab("roles", "Admin Hub", FiShield),
          buildTab("notes", "Notes", FiBookOpen),
          buildTab("progress", "Progress", FiBarChart2),
        ],
      },
    ];
  }

  return [
    {
      key: "study",
      title: "Study tools",
      tabs: [
        buildTab("chat", "Chat Workspace", FiMessageSquare, "Chat"),
        buildTab("notes", "Notes Workspace", FiBookOpen, "Notes"),
        buildTab("lesson", "Lesson Workspace", FiBook, "Lesson"),
        buildTab("quiz", "Quiz Workspace", FiClipboard, "Quiz"),
        buildTab("flashcards", "Cards Workspace", FiLayers, "Cards"),
      ],
    },
    {
      key: "track",
      title: "Stay on track",
      tabs: [
        buildTab("assignments", "Assignments", FiCheck),
        buildTab("progress", "Progress", FiBarChart2),
      ],
    },
  ];
}

function formatIndexTargetLabel(target = "") {
  const normalized = String(target || "").trim().toLowerCase();
  const labels = {
    concept_index: "concept",
    summary_index: "summary",
    qa_index: "Q&A",
    formula_index: "formula",
    image_index: "image",
    general_index: "general",
  };
  return labels[normalized] || normalized.replace(/_/g, " ");
}

function buildRunningAdminStatus(mode = "full") {
  const isIncremental = mode === "incremental";
  return {
    tone: "medium",
    mode,
    title: isIncremental ? "Incremental reindex is running…" : "Knowledge base reindex is running…",
    detail: isIncremental
      ? "Scanning changed study files in the background and refreshing only the affected concept, summary, Q&A, formula, and image indexes. You can keep using the app normally."
      : "Scanning the knowledge base in the background and rebuilding the concept, summary, Q&A, formula, and image indexes from scratch. You can keep using the app normally.",
    stats: null,
    currentFile: "",
    processedFiles: [],
    errors: [],
  };
}

function isAdminReindexActive(payload) {
  const reindex = payload?.reindex && typeof payload.reindex === "object" ? payload.reindex : null;
  const progressState = String(reindex?.status || payload?.status || "").toLowerCase();
  return Boolean(reindex?.running) || ["queued", "started", "running"].includes(progressState);
}

function buildLiveAdminStatus(payload, fallbackMode = "full") {
  const reindex = payload?.reindex && typeof payload.reindex === "object" ? payload.reindex : null;
  if (!reindex) {
    return buildRunningAdminStatus(fallbackMode);
  }

  const progressState = String(reindex.status || payload?.status || "").toLowerCase();
  if (["idle", "queued", "started"].includes(progressState)) {
    return buildRunningAdminStatus(fallbackMode);
  }

  if (!isAdminReindexActive(payload)) {
    return buildCompletedAdminStatus(payload, fallbackMode === "incremental" ? "Incremental reindex completed." : "Reindex completed.");
  }

  const progressPercent = Number(reindex.progress_percent || 0);
  const indexTargets = Array.isArray(reindex.index_targets)
    ? reindex.index_targets.map(formatIndexTargetLabel).filter(Boolean)
    : [];
  const currentFile = String(reindex.current_file || "").trim();
  const phase = String(reindex.phase || "").trim();
  const titleBase = fallbackMode === "incremental" ? "Incremental reindex is running…" : "Knowledge base reindex is running…";
  const detailParts = [];
  if (phase) detailParts.push(phase.endsWith(".") ? phase : `${phase}.`);
  if (currentFile) detailParts.push(`Current file: ${currentFile}.`);
  if (indexTargets.length) detailParts.push(`Refreshing ${indexTargets.join(", ")} indexes.`);

  return {
    tone: "medium",
    mode: fallbackMode,
    title: `${titleBase} ${progressPercent}%`,
    detail: detailParts.join(" ").trim() || titleBase,
    stats: {
      scanned: Number(reindex.scanned_files || 0),
      total: Number(reindex.total_files || 0),
      reindexed: Number(reindex.reindexed_files || 0),
      skipped: Number(reindex.skipped_files || 0),
      removed: Number(reindex.removed_files || 0),
    },
    currentFile,
    processedFiles: Array.isArray(reindex.processed_files) ? reindex.processed_files.slice(-6) : [],
    errors: Array.isArray(reindex.errors) ? reindex.errors.filter(Boolean) : [],
  };
}

function buildCompletedAdminStatus(payload, fallbackTitle = "Reindex completed.") {
  const reindex = payload?.reindex && typeof payload.reindex === "object" ? payload.reindex : null;
  const rawTitle = String(payload?.status || "").trim();
  const title = rawTitle && !["idle", "running", "completed", "error"].includes(rawTitle.toLowerCase())
    ? rawTitle
    : (fallbackTitle || "Reindex completed.");

  if (!reindex) {
    return {
      tone: "neutral",
      title,
      detail: "The indexing request finished and the latest knowledge-base state is now available.",
      stats: null,
      processedFiles: [],
      errors: [],
    };
  }

  const indexTargets = Array.isArray(reindex.index_targets)
    ? reindex.index_targets.map(formatIndexTargetLabel).filter(Boolean)
    : [];
  const processedFiles = Array.isArray(reindex.processed_files) ? reindex.processed_files.filter(Boolean) : [];
  const skippedPaths = Array.isArray(reindex.skipped_paths) ? reindex.skipped_paths.filter(Boolean) : [];
  const removedPaths = Array.isArray(reindex.removed_paths) ? reindex.removed_paths.filter(Boolean) : [];
  const errors = Array.isArray(reindex.errors) ? reindex.errors.filter(Boolean) : [];
  const modeLabel = String(reindex.mode || "reindex").replace(/^[a-z]/, (char) => char.toUpperCase());
  const detail = `${modeLabel} scan finished. Scanned ${reindex.scanned_files ?? 0} file(s), reindexed ${reindex.reindexed_files ?? 0}, skipped ${reindex.skipped_files ?? 0}, and removed ${reindex.removed_files ?? 0}.${indexTargets.length ? ` Refreshed ${indexTargets.join(", ")} indexes.` : ""}`;

  return {
    tone: errors.length ? "high" : "neutral",
    mode: reindex.mode || "full",
    title,
    detail,
    stats: {
      scanned: Number(reindex.scanned_files || 0),
      total: Number(reindex.total_files || 0),
      reindexed: Number(reindex.reindexed_files || 0),
      skipped: Number(reindex.skipped_files || 0),
      removed: Number(reindex.removed_files || 0),
    },
    currentFile: "",
    processedFiles: processedFiles.length ? processedFiles.slice(0, 6) : [...skippedPaths, ...removedPaths].slice(0, 6),
    errors,
  };
}

function buildFailedAdminStatus(actionLabel, detailText) {
  return {
    tone: "high",
    title: `${actionLabel} failed.`,
    detail: detailText || "The request could not finish. Please check the backend logs and try again.",
    stats: null,
    processedFiles: [],
    errors: detailText ? [detailText] : [],
  };
}

function NotesSidebarSection({ isActive = false, onNoteSelected = null }) {
  const [notes, setNotes] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadNotes = useCallback(async () => {
    if (!isActive) return;
    setLoading(true);
    setError("");

    try {
      const res = await apiFetch("/notes", { method: "GET" });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not load your notes."));
      }

      const payload = await res.json();
      const nextNotes = Array.isArray(payload?.notes) ? payload.notes : [];
      setNotes(nextNotes);
    } catch (err) {
      setError(err?.message || "Could not load your notes.");
    } finally {
      setLoading(false);
    }
  }, [isActive]);

  useEffect(() => {
    if (!isActive) return;
    loadNotes();
  }, [isActive, loadNotes]);

  useEffect(() => {
    if (!isActive) return undefined;

    const handleNotesUpdated = () => loadNotes();
    const handleNotesSelected = (event) => {
      const nextId = String(event?.detail?.selectedId || "").trim();
      setSelectedId(nextId);
    };

    window.addEventListener("notes:updated", handleNotesUpdated);
    window.addEventListener("notes:selected", handleNotesSelected);

    return () => {
      window.removeEventListener("notes:updated", handleNotesUpdated);
      window.removeEventListener("notes:selected", handleNotesSelected);
    };
  }, [isActive, loadNotes]);

  const handleSelectNote = (note) => {
    const nextId = String(note.id || "");
    setSelectedId(nextId);
    window.dispatchEvent(new CustomEvent("notes:selected", { detail: { selectedId: nextId } }));
    if (typeof onNoteSelected === "function") {
      onNoteSelected(note);
    }
  };

  const handleRenameNote = async (note) => {
    const newTitle = window.prompt("Rename note:", note.title || "");
    if (!newTitle || newTitle.trim() === note.title) return;

    try {
      const res = await apiFetch(`/notes/${encodeURIComponent(note.id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle.trim(), content: note.content }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not rename the note."));
      }

      setNotice("Note renamed.");
      window.dispatchEvent(new CustomEvent("notes:updated"));
      await loadNotes();
      if (selectedId === String(note.id)) {
        window.dispatchEvent(new CustomEvent("notes:selected", { detail: { selectedId: String(note.id) } }));
      }
    } catch (err) {
      setError(err?.message || "Could not rename the note.");
    }
  };

  const handleDeleteNote = async (note) => {
    if (!window.confirm(`Delete "${note.title || "Untitled note"}"? This action cannot be undone.`)) return;

    try {
      const res = await apiFetch(`/notes/${encodeURIComponent(note.id)}`, { method: "DELETE" });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not delete the note."));
      }

      setNotice("Note deleted.");
      window.dispatchEvent(new CustomEvent("notes:updated"));
      await loadNotes();
    } catch (err) {
      setError(err?.message || "Could not delete the note.");
    }
  };

  return (
    <div className="workspace-sidebar__section">
      <div className="workspace-sidebar__section-title">
        <FiBookOpen />
        <span>Saved Notes</span>
      </div>

      <button
        type="button"
        className="secondary-button secondary-button--block"
        onClick={loadNotes}
        disabled={loading}
      >
        <FiRefreshCw />
        <span>{loading ? "Refreshing..." : "Refresh Notes"}</span>
      </button>

      <div className="sidebar-note">{notes.length} saved notes ready to open and edit.</div>
      {error ? <p className="sidebar-note" role="alert">{error}</p> : null}
      {notice ? <p className="sidebar-note" role="status">{notice}</p> : null}

      <div className="session-list">
        {loading && notes.length === 0 ? (
          <div className="sidebar-note">
            <span>Loading notes…</span>
          </div>
        ) : notes.length === 0 ? (
          <div className="progress-plan-card notes-panel__empty">
            <p className="progress-plan-card__headline">No saved notes yet.</p>
            <p className="sidebar-note">Your saved notes will appear here after you save a summary from chat.</p>
          </div>
        ) : (
          notes.map((note) => (
            <div key={note.id} className={`session-item ${selectedId === String(note.id) ? "active" : ""}`}>
              <button
                type="button"
                className="session-title"
                onClick={() => handleSelectNote(note)}
                title={note.title || "Untitled note"}
              >
                <FiFileText className="session-icon" size={14} />
                <span className="session-text">{note.title || "Untitled note"}</span>
              </button>
              <div className="session-actions">
                <button type="button" className="icon-button icon-button--ghost" onClick={() => handleRenameNote(note)}>
                  <FiEdit />
                </button>
                <button type="button" className="icon-button icon-button--ghost" onClick={() => handleDeleteNote(note)}>
                  <FiTrash2 />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

const LEARNING_CONTEXT_STORAGE_KEY = "learning_context_v1";
const CONTEXT_REQUIRED_TABS = ["lesson", "quiz", "flashcards"];

function readStoredLearningContext() {
  try {
    const raw = localStorage.getItem(LEARNING_CONTEXT_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writeStoredLearningContext(context) {
  try {
    localStorage.setItem(LEARNING_CONTEXT_STORAGE_KEY, JSON.stringify(context || {}));
  } catch {
    // Ignore localStorage quota/runtime failures.
  }
}

function buildFriendlyProcessingState(statusItem) {
  const normalizedStatus = String(statusItem?.upload_status || "").trim().toUpperCase();
  const normalizedReason = String(statusItem?.status_reason || "").trim().toLowerCase();

  if (statusItem?.indexed || normalizedStatus === "INDEXED") {
    return {
      progress: 100,
      title: "Your content is ready.",
      detail: "You can now use it across chat and study tools.",
      tone: "success",
      ready: true,
    };
  }

  if (normalizedStatus === "FAILED" || normalizedReason.includes("fail")) {
    return {
      progress: 78,
      title: "We are fixing your content. It will be ready soon.",
      detail: "You can continue using the app while we retry in the background.",
      tone: "warning",
      ready: false,
    };
  }

  return {
    progress: normalizedStatus === "UPLOADED" ? 38 : 64,
    title: "Preparing your content...",
    detail: "This will be ready shortly. You can continue using the app.",
    tone: "info",
    ready: false,
  };
}

export default function ChatPanel({ initialActiveTab = null, externalTabRequest = null }) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [currentStream, setCurrentStream] = useState("");
  const [streamStatus, setStreamStatus] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [wsError, setWsError] = useState("");
  const [sessionId, setSessionId] = useState(localStorage.getItem("session_id") || null);
  const userId = localStorage.getItem("username") || "student";
  const rawUserRole = localStorage.getItem("role") || "student";
  const userRole = rawUserRole === "user" ? "student" : rawUserRole;
  const [adminViewRole, setAdminViewRole] = useState(() => {
    const stored = String(localStorage.getItem("admin_view_as_role") || "admin").toLowerCase();
    return ["admin", "student", "teacher", "parent"].includes(stored) ? stored : "admin";
  });
  const effectiveUserRole = userRole === "admin" ? adminViewRole : userRole;
  const [autoSpeak, setAutoSpeak] = useState(localStorage.getItem("autoSpeak") === "true");
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState(null);
  const [subjects, setSubjects] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState(null);
  const [folders, setFolders] = useState([]);
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [contents, setContents] = useState([]);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [selectedContent, setSelectedContent] = useState(null);
  const [contextMode, setContextMode] = useState(() => readStoredLearningContext().mode || null);
  const [isContextModalOpen, setIsContextModalOpen] = useState(false);
  const [contextPrompt, setContextPrompt] = useState("");
  const [contextHydrated, setContextHydrated] = useState(false);
  const [hasPromptedForContext, setHasPromptedForContext] = useState(false);
  const [contextDropActive, setContextDropActive] = useState(false);
  const [contextProcessing, setContextProcessing] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [adminRunning, setAdminRunning] = useState(false);
  const [adminMessage, setAdminMessage] = useState("");
  const [adminStatus, setAdminStatus] = useState(null);
  const [adminActionMode, setAdminActionMode] = useState("full");
  const [adminJobId, setAdminJobId] = useState(null);
  const initialWorkspaceTab = initialActiveTab || (userRole === "admin" ? "admin" : userRole === "teacher" || userRole === "parent" ? "roles" : "chat");
  const [activeTab, setActiveTab] = useState(initialWorkspaceTab);
  const [lessonResultReady, setLessonResultReady] = useState(false);
  const [quizResultReady, setQuizResultReady] = useState(false);
  const [flashcardResultReady, setFlashcardResultReady] = useState(false);
  const [kbStatus, setKbStatus] = useState({
    classesLoading: false,
    subjectsLoading: false,
    foldersLoading: false,
    contentsLoading: false,
    error: "",
  });
  const [isSubscriptionModalOpen, setIsSubscriptionModalOpen] = useState(false);
  const [subscriptionCatalog, setSubscriptionCatalog] = useState(null);
  const [subscriptionQuote, setSubscriptionQuote] = useState(null);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);
  const [subscriptionQuoting, setSubscriptionQuoting] = useState(false);
  const [subscriptionActivating, setSubscriptionActivating] = useState(false);
  const [subscriptionActivated, setSubscriptionActivated] = useState(null);
  const [subscriptionError, setSubscriptionError] = useState("");
  const [selectedSubscriptionClasses, setSelectedSubscriptionClasses] = useState([]);
  const [promoCode, setPromoCode] = useState("");
  const [autoRenewSubscription, setAutoRenewSubscription] = useState(true);
  const [planActionPrefill, setPlanActionPrefill] = useState({
    lesson: { chapter: "", context: "", autoRunToken: "", generatedPayload: null },
    quiz: { chapter: "", context: "", autoRunToken: "", generatedPayload: null },
    assessment: { subject: "", context: "", autoRunToken: "", mode: "exam", difficulty: "mixed", numQuestions: 5 },
  });

  const selectedContentItem = contents.find((item) => item.content_id === selectedContent) || null;
  const inferredChapter = selectedContentItem?.title || selectedFolder || "";
  const chapterOptions = contents.map((item) => item.title);
  const currentContextLabel = selectedContentItem?.title || selectedFolder || null;
  const lessonDefaultChapter = planActionPrefill.lesson.chapter || inferredChapter;
  const quizDefaultChapter = planActionPrefill.quiz.chapter || inferredChapter;

  const { planSummary, loadPlanSummary, getUsageLimitState } = usePlanSummary();
  const activeSubscribedClasses = useMemo(() => {
    const items = Array.isArray(planSummary?.classes) ? planSummary.classes : [];
    return items
      .map((item) => String(item?.class_name || "").trim())
      .filter(Boolean);
  }, [planSummary]);
  const hasClassScopedAccess = activeSubscribedClasses.length > 0;
  const visibleClasses = hasClassScopedAccess
    ? classes.filter((item) => activeSubscribedClasses.includes(item) || item === "MyDocs")
    : classes;
  const classAccessSummary = hasClassScopedAccess
    ? `Subscribed classes: ${activeSubscribedClasses.join(", ")}`
    : "All available classes are currently visible for your current plan.";
  const {
    sessions,
    setSessions,
    lessonSessions,
    setLessonSessions,
    quizSessions,
    setQuizSessions,
    flashcardSessions,
    setFlashcardSessions,
    loadSessions,
    loadLessonSessions,
    loadQuizSessions,
    loadFlashcardSessions,
  } = useSessionLoaders();

  const chatPanelRef = useRef(null);
  const chatComposerRef = useRef(null);
  const fileInputRef = useRef(null);
  const currentStreamRef = useRef("");
  const currentStreamMetaRef = useRef({ messageId: null, level: null, quickReplies: [] });
  const isStreamingRef = useRef(false);
  const sessionIdRef = useRef(sessionId);
  const autoSpeakRef = useRef(autoSpeak);
  const activeStreamSessionRef = useRef(null);
  const pendingResponseRef = useRef(false);
  const contextRetryFileIdsRef = useRef(new Set());
  const isAdmin = userRole === "admin";
  const isTeacherView = effectiveUserRole === "teacher";
  const isParentView = effectiveUserRole === "parent";
  const isAdminView = effectiveUserRole === "admin";
  const hasViewerContent = Boolean(pdfBlobUrl);
  const workspaceNavSections = useMemo(() => getWorkspaceNavSections(effectiveUserRole, userRole), [effectiveUserRole, userRole]);
  const visibleWorkspaceTabIds = useMemo(
    () => workspaceNavSections.flatMap((section) => section.tabs.map((tab) => tab.id)),
    [workspaceNavSections],
  );
  const primaryWorkspaceSection = workspaceNavSections[0] || { tabs: [] };
  const compactSecondaryTabs = workspaceNavSections.slice(1).flatMap((section) => section.tabs);
  const workspaceBrandSummary = isAdmin && effectiveUserRole !== "admin"
    ? `Previewing the ${effectiveUserRole} workspace while keeping admin controls available.`
    : isTeacherView
      ? "Classroom tools and learner support"
      : isParentView
        ? "Progress, assignments, and family updates"
        : isAdminView
          ? "Admin, billing, and oversight tools"
          : "AI-powered learning workspace";
  const shouldShowContextBar = ["chat", "lesson", "quiz", "flashcards", "assessment", "notes"].includes(activeTab);
  const isExplorerMode = contextMode === "explorer";
  const hasRequiredStudyContext = Boolean(selectedClass && selectedSubject);
  const requiresStructuredContext = CONTEXT_REQUIRED_TABS.includes(activeTab);
  const hasStructuredPrefill = !isExplorerMode && (
    (activeTab === "lesson" && Boolean(planActionPrefill.lesson.chapter || planActionPrefill.lesson.context || selectedContent)) ||
    (activeTab === "quiz" && Boolean(planActionPrefill.quiz.chapter || planActionPrefill.quiz.context || selectedContent)) ||
    (activeTab === "flashcards" && Boolean(selectedContent || selectedFolder))
  );
  const shouldGateStructuredWorkspace = requiresStructuredContext && (isExplorerMode || (!hasRequiredStudyContext && !hasStructuredPrefill));
  const panelMeta = useMemo(() => getActivePanelMeta(activeTab, effectiveUserRole), [activeTab, effectiveUserRole]);
  const workspaceEyebrow = effectiveUserRole === "teacher"
    ? "Teaching workspace"
    : effectiveUserRole === "parent"
      ? "Family workspace"
      : effectiveUserRole === "admin"
        ? "Admin workspace"
        : "Study workspace";
  const planAskUsed = Number(planSummary?.usage?.ask_count || 0);

  const handleAdminViewRoleChange = useCallback((nextRole) => {
    if (!isAdmin) return;
    const normalized = ["admin", "student", "teacher", "parent"].includes(String(nextRole || "").toLowerCase())
      ? String(nextRole).toLowerCase()
      : "admin";
    setAdminViewRole(normalized);
    localStorage.setItem("admin_view_as_role", normalized);
  }, [isAdmin]);
  const planAskLimit = Number(planSummary?.limits?.ask_count || 0);
  const planAskRemaining = planAskLimit > 0 ? Math.max(planAskLimit - planAskUsed, 0) : 0;
  const planUsageSummary = planSummary
    ? `${planSummary.planCode}${planSummary.isTrial ? " Trial" : ""} · ${planAskLimit > 0 ? `${planAskRemaining} asks left` : `${planAskUsed} asks used`}`
    : "";
  const contextPillItems = isExplorerMode
    ? []
    : [
        { key: "class", icon: FiLayers, label: "Class", value: selectedClass },
        { key: "subject", icon: FiBook, label: "Subject", value: selectedSubject },
        { key: "folder", icon: FiFolder, label: "Folder", value: selectedFolder },
        { key: "file", icon: FiFileText, label: "File", value: selectedContentItem?.title },
      ].filter((item) => Boolean(item.value));

  const handleWorkspaceTabSelect = useCallback((tabId) => {
    if (CONTEXT_REQUIRED_TABS.includes(tabId) && (!selectedClass || !selectedSubject || contextMode === "explorer")) {
      setContextPrompt("Please select your class and subject to continue");
      setIsContextModalOpen(true);
    }

    if (tabId === "lesson") {
      setActiveTab("lesson");
      setLessonResultReady(false);
      return;
    }
    if (tabId === "quiz") {
      setActiveTab("quiz");
      setQuizResultReady(false);
      return;
    }
    if (tabId === "flashcards") {
      setActiveTab("flashcards");
      setFlashcardResultReady(false);
      return;
    }
    setActiveTab(tabId);
  }, [contextMode, selectedClass, selectedSubject]);

  const shouldShowWorkspaceReadyDot = useCallback((tabId) => {
    if (tabId === "lesson") return lessonResultReady && activeTab !== "lesson";
    if (tabId === "quiz") return quizResultReady && activeTab !== "quiz";
    if (tabId === "flashcards") return flashcardResultReady && activeTab !== "flashcards";
    return false;
  }, [activeTab, flashcardResultReady, lessonResultReady, quizResultReady]);

  useEffect(() => {
    if (initialActiveTab) {
      handleWorkspaceTabSelect(initialActiveTab);
    }
  }, [handleWorkspaceTabSelect, initialActiveTab]);

  useEffect(() => {
    if (!externalTabRequest?.tab) return;
    handleWorkspaceTabSelect(externalTabRequest.tab);
  }, [externalTabRequest, handleWorkspaceTabSelect]);

  useEffect(() => {
    const hiddenTabsAllowedByRole = ["profile", "billing"];
    if (effectiveUserRole === "student") {
      hiddenTabsAllowedByRole.push("assessment");
    }
    if (visibleWorkspaceTabIds.includes(activeTab) || hiddenTabsAllowedByRole.includes(activeTab)) {
      return;
    }

    const fallbackTab = userRole === "admin"
      ? "admin"
      : effectiveUserRole === "teacher" || effectiveUserRole === "parent"
        ? "roles"
        : "chat";

    setActiveTab(fallbackTab);
  }, [activeTab, effectiveUserRole, userRole, visibleWorkspaceTabIds]);

  const {
    workspaceBodyRef,
    isViewerVisible,
    setIsViewerVisible,
    isViewerMaximized,
    setIsViewerMaximized,
    isDraggingViewer,
    shouldShowViewer,
    shouldShowSideViewer,
    effectiveViewerWidth,
    toggleViewerMaximize,
    startViewerDrag,
  } = useViewerLayout({ hasViewerContent });

  useEffect(() => {
    isStreamingRef.current = isStreaming;
  }, [isStreaming]);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    autoSpeakRef.current = autoSpeak;
  }, [autoSpeak]);

  useEffect(() => {
    if (!hasClassScopedAccess || !selectedClass) return;
    if (visibleClasses.includes(selectedClass)) return;

    setSelectedClass(null);
    setSelectedSubject(null);
    setSelectedFolder(null);
    setContents([]);
    setSelectedContent(null);
  }, [hasClassScopedAccess, selectedClass, visibleClasses, setContents]);

  const { chatMessagesRef, messagesEndRef, isNearBottom, scrollToConversationEnd } = useChatScroll({
    activeTab,
    messages,
    currentStream,
  });

  useChatComposerLayout({
    panelRef: chatPanelRef,
    composerRef: chatComposerRef,
    activeTab,
    drawerOpen,
    shouldShowSideViewer,
    effectiveViewerWidth,
  });



  const handleVoice = (text) => setInput(text);

  const {
    lessonSessionId,
    quizSessionId,
    flashcardSessionId,
    persistLessonSession,
    persistQuizSession,
    persistFlashcardSession,
    handleNewLessonSession,
    handleNewQuizSession,
    handleNewFlashcardSession,
    renameLessonSession,
    deleteLessonSession,
    renameQuizSession,
    deleteQuizSession,
    renameFlashcardSession,
    deleteFlashcardSession,
  } = useScopedSessionActions({
    setActiveTab,
    setLessonResultReady,
    setQuizResultReady,
    setFlashcardResultReady,
    setLessonSessions,
    setQuizSessions,
    setFlashcardSessions,
    apiFetch,
    parseApiError,
  });

  const handleProgressPlanAction = useCallback(async (step) => {
    const requestedTab = step?.action_tab || step?.activity_type || "chat";
    const normalizedTab = requestedTab === "flashcard" ? "flashcards" : requestedTab;
    const chapterHint = String(step?.chapter_hint || "").trim();
    const contextHint = String(step?.context_hint || step?.description || "").trim();
    const shouldAutoRun = Boolean(step?.auto_run);
    const autoRunToken = shouldAutoRun && (normalizedTab === "lesson" || normalizedTab === "quiz" || normalizedTab === "assessment")
      ? `${normalizedTab}-${Date.now()}`
      : "";

    let activeLessonSessionId = lessonSessionId;
    let activeQuizSessionId = quizSessionId;

    if (normalizedTab === "lesson") {
      if (!activeLessonSessionId) {
        activeLessonSessionId = Date.now().toString();
        persistLessonSession(activeLessonSessionId);
        setLessonResultReady(false);
      }
      setPlanActionPrefill((prev) => ({
        ...prev,
        lesson: {
          chapter: chapterHint || prev.lesson.chapter,
          context: contextHint || prev.lesson.context,
          autoRunToken,
          generatedPayload: null,
        },
      }));
    }
    if (normalizedTab === "quiz") {
      if (!activeQuizSessionId) {
        activeQuizSessionId = Date.now().toString();
        persistQuizSession(activeQuizSessionId);
        setQuizResultReady(false);
      }
      setPlanActionPrefill((prev) => ({
        ...prev,
        quiz: {
          chapter: chapterHint || prev.quiz.chapter,
          context: contextHint || prev.quiz.context,
          autoRunToken,
          generatedPayload: null,
        },
      }));
    }
    if (normalizedTab === "assessment") {
      setPlanActionPrefill((prev) => ({
        ...prev,
        assessment: {
          subject: chapterHint || prev.assessment.subject,
          context: contextHint || prev.assessment.context,
          autoRunToken,
          mode: String(step?.mode_hint || "exam"),
          difficulty: String(step?.difficulty_hint || "mixed"),
          numQuestions: Number(step?.question_count_hint || 5),
        },
      }));
    }
    if (normalizedTab === "chat" && contextHint) {
      setInput(contextHint);
    }

    if (normalizedTab === "flashcards" && !flashcardSessionId) {
      handleNewFlashcardSession();
    }

    setActiveTab(normalizedTab);

    if (shouldAutoRun && (normalizedTab === "lesson" || normalizedTab === "quiz" || normalizedTab === "assessment")) {
      return;
    }
  }, [flashcardSessionId, handleNewFlashcardSession, lessonSessionId, persistLessonSession, persistQuizSession, quizSessionId]);

  const loadHistory = useCallback(async (session, options = {}) => {
    const { force = false } = options;
    if (!session) return;
    if (!force && isStreamingRef.current && session === sessionId) return;

    try {
      const res = await apiFetch(`/history?session_id=${session}`);
      if (!res.ok) return;
      const data = await res.json();
      const historyRows = Array.isArray(data) ? data : Array.isArray(data?.history) ? data.history : [];
      const formatted = [];
      historyRows.forEach((item) => {
        const questionText = String(item?.question || "").trim();
        const answerText = String(item?.answer || "");

        if (questionText) {
          formatted.push({ type: "user", text: questionText });
        }
        if (answerText.trim()) {
          formatted.push({ type: "ai", text: answerText });
        }
      });
      setMessages((prev) => {
        if (force && formatted.length === 0 && prev.length > 0) {
          return prev;
        }
        return formatted;
      });
    } catch (err) {
      console.error("❌ Failed to load history:", err);
    }
  }, [sessionId]);

  const { clearStreamWatchdog, clearStreamStallHint, armStreamStallHint, armStreamWatchdog } = useStreamTimers({
    loadHistory,
    setStreamStatus,
    setIsStreaming,
    setCurrentStream,
    currentStreamRef,
    isStreamingRef,
    pendingResponseRef,
    activeStreamSessionRef,
  });

  const handleNewChat = () => {
    const newSession = Date.now().toString();
    setSessionId(newSession);
    localStorage.setItem("session_id", newSession);
    setMessages([]);
    setSelectedContent(null);
  };

  const switchSession = (sessionObj) => {
    const session = sessionObj.id;
    setSessionId(session);
    localStorage.setItem("session_id", session);
    loadHistory(session);
    setSelectedContent(sessionObj.selected_content || null);
    if (sessionObj.selected_content) {
      setIsViewerVisible(true);
    }
  };

  const deleteSession = async (sessionToDelete) => {
    try {
      await apiFetch(`/sessions/${sessionToDelete.id}`, { method: "DELETE" });
      const updated = sessions.filter((s) => s.id !== sessionToDelete.id);
      setSessions(updated);

      if (sessionId === sessionToDelete.id) {
        if (updated.length > 0) {
          switchSession(updated[0]);
        } else {
          setSessionId(null);
          localStorage.removeItem("session_id");
          setMessages([]);
          setSelectedContent(null);
        }
      }
    } catch (err) {
      console.error("❌ Delete failed:", err);
    }
  };

  const renameSession = async (sessionObj) => {
    const newTitle = prompt("Rename chat:", sessionObj.title);
    if (!newTitle) return;

    try {
      await apiFetch(`/sessions/${sessionObj.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle }),
      });

      setSessions((prev) =>
        prev.map((session) =>
          session.id === sessionObj.id ? { ...session, title: newTitle } : session
        )
      );
    } catch (err) {
      console.error("❌ Rename failed:", err);
    }
  };

  const filteredLessonSessions = filterSessionsByContext(
    lessonSessions,
    currentContextLabel,
    lessonSessionId
  );

  // Quiz sessions can be created from multiple sources and may not always carry
  // chapter metadata immediately, so avoid context filtering here to prevent
  // newly generated quizzes from appearing missing until a refresh.
  const filteredQuizSessions = quizSessions;

  const filteredFlashcardSessions = filterSessionsByContext(
    flashcardSessions,
    currentContextLabel,
    flashcardSessionId
  );

  const { loadClasses, loadSubjects, loadFolders, loadContents } = useKnowledgeBaseLoader({
    apiFetch,
    parseApiError,
    setKbStatus,
    setClasses,
    setSubjects,
    setFolders,
    setContents,
    setUploadedFiles,
    setSelectedContent,
  });

  const { handleClassChange, handleSubjectChange, handleFolderChange } = useKnowledgeBaseSelectionHandlers({
    selectedClass,
    selectedSubject,
    setSelectedClass,
    setSelectedSubject,
    setSelectedFolder,
    setSelectedContent,
    setSubjects,
    setFolders,
    setContents,
    setUploadedFiles,
    setUploadNotice,
    loadSubjects,
    loadFolders,
    loadContents,
  });

  const uploadSelectedFile = async (file, resetInput = () => {}) => {
    if (!file) return;

    if (uploadLimitState.blocked) {
      setUploadNotice({
        level: "WARN",
        messageId: "MSG-1201",
        text: `Upload limit reached (${uploadLimitState.used}/${uploadLimitState.limit}). Upgrade plan to continue.`,
      });
      setContextProcessing(null);
      resetInput();
      return;
    }

    if (!selectedClass || !selectedSubject) {
      setUploadNotice({
        level: "ERROR",
        messageId: "MSG-1303",
        text: "Please choose your class and subject before adding a file.",
      });
      setContextPrompt("Please select your class and subject to continue");
      setIsContextModalOpen(true);
      resetInput();
      return;
    }

    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setUploadNotice({
        level: "ERROR",
        messageId: "MSG-1304",
        text: "Only PDF files are supported.",
      });
      resetInput();
      return;
    }

    const uploadFolder = selectedFolder || "Notes";
    const displayName = file.name.replace(/\.pdf$/i, "").trim() || file.name;
    const formData = new FormData();
    formData.append("class_name", selectedClass);
    formData.append("subject_name", selectedSubject);
    formData.append("folder_name", uploadFolder);
    formData.append("display_name", displayName);
    formData.append("upload", file);

    setIsUploading(true);
    setUploadNotice({
      level: "INFO",
      messageId: "MSG-1301",
      text: "Preparing your content... This will be ready shortly. You can continue using the app.",
    });
    setContextProcessing({
      fileId: null,
      progress: 18,
      title: "Preparing your content...",
      detail: "This will be ready shortly. You can continue using the app.",
      tone: "info",
      ready: false,
    });

    try {
      const res = await apiFetch("/files/upload", {
        method: "POST",
        body: formData,
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data?.detail;
        const message =
          typeof detail === "string"
            ? detail
            : detail?.message || `Upload failed (${res.status}).`;
        setUploadNotice({
          level: "ERROR",
          messageId: detail?.message_id || data?.message?.message_id || "MSG-1304",
          text: message,
        });
        setContextProcessing(null);
        return;
      }

      if (!selectedFolder) {
        setSelectedFolder(uploadFolder);
      }
      setContextMode((prev) => prev || "contextual");
      setUploadNotice({
        level: "INFO",
        messageId: data?.message?.message_id || "MSG-1301",
        text: "Preparing your content... This will be ready shortly. You can continue using the app.",
      });
      setContextProcessing({
        fileId: data?.file_id || null,
        progress: 30,
        title: "Preparing your content...",
        detail: "This will be ready shortly. You can continue using the app.",
        tone: "info",
        ready: false,
      });

      await loadContents(selectedClass, selectedSubject, uploadFolder);
    } catch (err) {
      console.error("❌ Upload failed:", err);
      setUploadNotice({
        level: "ERROR",
        messageId: "MSG-1304",
        text: "Upload failed. Please try again.",
      });
      setContextProcessing(null);
    } finally {
      setIsUploading(false);
      resetInput();
    }
  };

  const handleUploadFile = async (event) => {
    const file = event.target.files?.[0];
    await uploadSelectedFile(file, () => {
      event.target.value = "";
    });
  };

  const refreshIndexedFiles = async () => {
    await loadContents(selectedClass, selectedSubject, selectedFolder);
  };

  const pendingUploadsInScope = countPendingUploadsInScope(
    uploadedFiles,
    selectedClass,
    selectedSubject,
    selectedFolder
  );
  const uploadLimitState = getUsageLimitState("upload");

  const kbStatusMessage = buildKnowledgeBaseStatusMessage({
    kbStatus,
    classes,
    subjects,
    folders,
    contents,
    selectedClass,
    selectedSubject,
    selectedFolder,
    pendingUploadsInScope,
  });
  const supplementalContextStatus = !contextProcessing && !uploadNotice && kbStatusMessage && kbStatusMessage !== "Knowledge base loaded."
    ? kbStatusMessage
    : "";

  const handleContentChange = (event) => {
    const value = event.target.value || null;
    setSelectedContent(value);

    if (sessionId) {
      const body = value ? { content_id: value } : {};
      apiFetch(`/sessions/${sessionId}/content`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }).catch((err) => {
        console.error("❌ Failed to persist selected content:", err);
      });
    }

    if (value) {
      setIsViewerVisible(true);
      setIsViewerMaximized(false);
    }
  };

  const applyPersistedContext = useCallback(async (nextContext = {}) => {
    const nextMode = String(nextContext?.mode || "contextual").toLowerCase() === "explorer" ? "explorer" : "contextual";
    const nextClass = nextContext?.class_name || null;
    const nextSubject = nextContext?.subject_name || null;
    const nextFolder = nextContext?.folder_name || null;
    const nextContent = nextContext?.content_id || null;

    setContextMode(nextMode);
    setSelectedClass(nextClass);
    setSelectedSubject(nextSubject);
    setSelectedFolder(nextFolder);
    setSelectedContent(nextContent);

    if (nextClass) {
      await loadSubjects(nextClass);
    }
    if (nextClass && nextSubject) {
      await loadFolders(nextClass, nextSubject);
    }
    if (nextClass && nextSubject && nextFolder) {
      await loadContents(nextClass, nextSubject, nextFolder);
    }
  }, [loadContents, loadFolders, loadSubjects]);

  const openContextModal = useCallback((promptText = "Please select your class and subject to continue") => {
    setContextPrompt(promptText);
    setIsContextModalOpen(true);
    if (classes.length === 0) {
      loadClasses();
    }
    if (selectedClass && subjects.length === 0) {
      loadSubjects(selectedClass);
    }
    if (selectedClass && selectedSubject && folders.length === 0) {
      loadFolders(selectedClass, selectedSubject);
    }
  }, [classes.length, folders.length, loadClasses, loadFolders, loadSubjects, selectedClass, selectedSubject, subjects.length]);

  const saveLearningContext = useCallback(async () => {
    if (!selectedClass || !selectedSubject) {
      setContextPrompt("Please select your class and subject to continue");
      return;
    }
    setContextMode("contextual");
    if (selectedClass && selectedSubject && selectedFolder) {
      await loadContents(selectedClass, selectedSubject, selectedFolder);
    }
    setContextPrompt("");
    setIsContextModalOpen(false);
  }, [loadContents, selectedClass, selectedFolder, selectedSubject]);

  const handleExplorerModeSelection = useCallback(() => {
    setContextMode("explorer");
    setContextPrompt("");
    setSelectedContent(null);
    setIsViewerVisible(false);
    setIsContextModalOpen(false);
    setActiveTab("chat");
  }, [setIsViewerVisible]);

  const handleContextDrop = useCallback(async (event) => {
    event.preventDefault();
    setContextDropActive(false);
    const file = event.dataTransfer?.files?.[0];
    await uploadSelectedFile(file);
  }, [uploadSelectedFile]);

  const renderContextGate = useCallback((tabLabel) => (
    <div className="context-required-gate" role="status" aria-live="polite">
      <div className="workspace-panel__eyebrow">
        <FiBookOpen />
        <span>{tabLabel}</span>
      </div>
      <h3>Choose a learning context for {tabLabel}</h3>
      <p>
        {isExplorerMode
          ? "Explorer Mode keeps chat open for general learning only. Choose a class and subject to unlock guided lessons, quizzes, and file-based study tools."
          : "Pick your class and subject to unlock guided lessons, quizzes, flashcards, and content-based study support."}
      </p>
      <button type="button" className="primary-button" onClick={() => openContextModal("Please select your class and subject to continue")}>
        <FiEdit />
        <span>Choose learning context</span>
      </button>
    </div>
  ), [isExplorerMode, openContextModal]);

  const toggleSubscriptionClass = useCallback((className) => {
    setSelectedSubscriptionClasses((prev) => {
      if (prev.includes(className)) {
        return prev.filter((item) => item !== className);
      }
      return [...prev, className];
    });
  }, []);

  const openSubscriptionModal = useCallback(async () => {
    setIsSubscriptionModalOpen(true);
    setSubscriptionError("");

    if (subscriptionCatalog) {
      return;
    }

    setSubscriptionLoading(true);
    try {
      const res = await apiFetch("/subscription/catalog");
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to load subscription catalog."));
      }

      const data = await res.json();
      const classRates = Array.isArray(data?.class_rates) ? data.class_rates : [];
      const defaults = Array.from(
        new Set([
          ...activeSubscribedClasses.filter((className) => classRates.some((item) => item.class_name === className)),
          ...(selectedClass && classRates.some((item) => item.class_name === selectedClass) ? [selectedClass] : []),
        ])
      );
      if (defaults.length === 0) {
        const firstPaid = classRates.find((item) => Number(item.annual_price_cents || 0) > 0);
        if (firstPaid?.class_name) {
          defaults.push(firstPaid.class_name);
        }
      }
      if (defaults.length > 0) {
        setSelectedSubscriptionClasses(defaults);
      }
      setSubscriptionCatalog(data);
    } catch (err) {
      setSubscriptionError(err?.message || "Unable to load subscription catalog.");
    } finally {
      setSubscriptionLoading(false);
    }
  }, [activeSubscribedClasses, selectedClass, subscriptionCatalog]);

  const requestSubscriptionQuote = useCallback(async () => {
    if (selectedSubscriptionClasses.length === 0) {
      setSubscriptionError("Select at least one class to get a quote.");
      return;
    }

    setSubscriptionError("");
    setSubscriptionQuoting(true);
    try {
      const res = await apiFetch("/subscription/quote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          class_names: selectedSubscriptionClasses,
          promo_code: promoCode.trim() || null,
          auto_renew: autoRenewSubscription,
        }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Unable to fetch quote."));
      }

      const data = await res.json();
      setSubscriptionQuote(data);
      setSubscriptionActivated(null);
      loadPlanSummary();
    } catch (err) {
      setSubscriptionQuote(null);
      setSubscriptionError(err?.message || "Unable to fetch quote.");
    } finally {
      setSubscriptionQuoting(false);
    }
  }, [autoRenewSubscription, loadPlanSummary, promoCode, selectedSubscriptionClasses]);

  const confirmSubscription = useCallback(async () => {
    if (!subscriptionQuote || selectedSubscriptionClasses.length === 0) return;

    setSubscriptionError("");
    setSubscriptionActivating(true);
    try {
      const res = await apiFetch("/subscription/activate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          class_names: selectedSubscriptionClasses,
          promo_code: promoCode.trim() || null,
          auto_renew: autoRenewSubscription,
        }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Activation failed. Please try again."));
      }
      const data = await res.json();
      setSubscriptionActivated(data);
      setSubscriptionQuote(null);
      loadPlanSummary();
    } catch (err) {
      setSubscriptionError(err?.message || "Activation failed. Please try again.");
    } finally {
      setSubscriptionActivating(false);
    }
  }, [autoRenewSubscription, loadPlanSummary, promoCode, selectedSubscriptionClasses, subscriptionQuote]);

  useEffect(() => {
    if (!selectedContent) {
      setPdfBlobUrl(null);
      return;
    }

    apiFetch(`/pdf?content_id=${encodeURIComponent(selectedContent)}`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load PDF");
        return res.blob();
      })
      .then((blob) => setPdfBlobUrl(URL.createObjectURL(blob)))
      .catch((err) => {
        console.error("❌ PDF load failed:", err);
        setPdfBlobUrl(null);
      });
  }, [selectedContent]);

  const openViewerInNewTab = () => {
    if (!pdfBlobUrl) return;
    window.open(pdfBlobUrl, "_blank", "noopener,noreferrer");
  };

  const handleIncomingToken = useCallback(
    (rawToken) => {
      if (rawToken === "[END]") {
        clearStreamWatchdog();
        clearStreamStallHint();
        const finalText = currentStreamRef.current;
        const finalMeta = currentStreamMetaRef.current;
        const wasExpected = pendingResponseRef.current;
        pendingResponseRef.current = false;
        activeStreamSessionRef.current = null;
        setCurrentStream("");
        currentStreamRef.current = "";
        currentStreamMetaRef.current = resetStreamMeta();
        setStreamStatus("");
        isStreamingRef.current = false;
        setIsStreaming(false);
        // Only commit to chat if this END closes a user-initiated query
        if (shouldCommitCompletedStream(finalText, wasExpected)) {
          setMessages((prev) => [
            ...prev,
            buildCompletedStreamMessage(finalText, finalMeta),
          ]);
          if (autoSpeakRef.current && shouldSpeakText(finalText)) {
            speakText(finalText);
          }
        }
        // Session title/history list is persisted at stream completion; refresh now.
        loadSessions();
        return;
      }

      const payload = normalizeStreamPayload(rawToken);

      // Route WS infrastructure error messages to the error banner, not the chat
      if (isWebsocketErrorToken(rawToken)) {
        setWsError(rawToken.trim());
        return;
      }

      currentStreamMetaRef.current = mergeStreamMeta(currentStreamMetaRef.current, payload);

      if (shouldSkipStreamPayload(payload)) return;

      armStreamStallHint();
      armStreamWatchdog(activeStreamSessionRef.current || sessionIdRef.current);

      if (payload.replaceText) {
        setCurrentStream(payload.text);
        currentStreamRef.current = payload.text;
        return;
      }

      setCurrentStream((prev) => {
        const next = prev + payload.text;
        currentStreamRef.current = next;
        return next;
      });
    },
    [armStreamWatchdog, loadSessions]
  );

  useChatWebSocketLifecycle({ handleIncomingToken, clearStreamWatchdog });

  const [preferredLanguage, setPreferredLanguage] = useState("en");
  const [translatedMessages, setTranslatedMessages] = useState({});
  const [translatingId, setTranslatingId] = useState(null);

  const handleTranslateMessage = async (index, text) => {
    if (translatedMessages[index]) {
      setTranslatedMessages((prev) => { const next = { ...prev }; delete next[index]; return next; });
      return;
    }
    setTranslatingId(index);
    try {
      const res = await apiFetch("/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, target_language: preferredLanguage, source_language: "auto" }),
      });
      const data = await res.json();
      if (data.translated_text) {
        setTranslatedMessages((prev) => ({ ...prev, [index]: data.translated_text }));
      }
    } catch { /* silently ignore */ } finally {
      setTranslatingId(null);
    }
  };

  const { handleSend } = useChatSendMessage({
    input,
    sessionId,
    selectedContent,
    chatTask: isExplorerMode ? "explorer" : null,
    setMessages,
    setCurrentStream,
    setWsError,
    setIsStreaming,
    setSessionId,
    setInput,
    currentStreamRef,
    currentStreamMetaRef,
    pendingResponseRef,
    isStreamingRef,
    activeStreamSessionRef,
    armStreamStallHint,
    armStreamWatchdog,
    loadSessions,
    apiFetch,
    send: sendMessage,
  });

  const handleReindex = async () => {
    const runningStatus = buildRunningAdminStatus("full");
    setAdminActionMode("full");
    setAdminRunning(true);
    setAdminStatus(runningStatus);
    setAdminMessage(runningStatus.title);
    try {
      const res = await apiFetch("/admin/reindex/full", { method: "POST" });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Reindex failed."));
      }
      const data = await res.json();
      const meta = getEnvelopeMessage(data);
      setAdminJobId(data?.job_id || data?.reindex?.job_id || null);
      const nextStatus = buildLiveAdminStatus(data, "full");
      setAdminStatus(nextStatus);
      setAdminMessage(meta ? `${messageSummary(meta)} ${nextStatus.detail || nextStatus.title}` : (nextStatus.detail || nextStatus.title));
      if (!isAdminReindexActive(data)) {
        setAdminRunning(false);
      }
    } catch (err) {
      const failureStatus = buildFailedAdminStatus("Knowledge base reindex", String(err?.message || "Reindex failed."));
      setAdminStatus(failureStatus);
      setAdminMessage(failureStatus.title);
      setAdminRunning(false);
      setAdminJobId(null);
    }
  };

  const handleIncrementalReindex = async () => {
    const runningStatus = buildRunningAdminStatus("incremental");
    setAdminActionMode("incremental");
    setAdminRunning(true);
    setAdminStatus(runningStatus);
    setAdminMessage(runningStatus.title);
    try {
      const res = await apiFetch("/admin/reindex/incremental", { method: "POST" });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Incremental reindex failed."));
      }
      const data = await res.json();
      const meta = getEnvelopeMessage(data);
      setAdminJobId(data?.job_id || data?.reindex?.job_id || null);
      const nextStatus = buildLiveAdminStatus(data, "incremental");
      setAdminStatus(nextStatus);
      setAdminMessage(meta ? `${messageSummary(meta)} ${nextStatus.detail || nextStatus.title}` : (nextStatus.detail || nextStatus.title));
      if (!isAdminReindexActive(data)) {
        setAdminRunning(false);
      }
    } catch (err) {
      const failureStatus = buildFailedAdminStatus("Incremental reindex", String(err?.message || "Incremental reindex failed."));
      setAdminStatus(failureStatus);
      setAdminMessage(failureStatus.title);
      setAdminRunning(false);
      setAdminJobId(null);
    }
  };

  useEffect(() => {
    if (!adminRunning) return undefined;

    let cancelled = false;
    const pollStatus = async () => {
      try {
        const statusUrl = adminJobId ? `/admin/reindex/status/${encodeURIComponent(adminJobId)}` : "/admin/reindex-status";
        const res = await apiFetch(statusUrl, { method: "GET" });
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        const liveStatus = buildLiveAdminStatus(data, adminActionMode);
        setAdminStatus(liveStatus);
        if (liveStatus?.title) {
          setAdminMessage(liveStatus.title);
        }
        if (!isAdminReindexActive(data)) {
          setAdminRunning(false);
          setAdminJobId(null);
        }
      } catch {
        // Keep the last visible status if polling fails temporarily.
      }
    };

    pollStatus();
    const intervalId = window.setInterval(pollStatus, 1200);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [adminRunning, adminActionMode, adminJobId]);

  useEffect(() => {
    loadSessions();
    loadLessonSessions();
    loadQuizSessions();
    loadFlashcardSessions();
    loadClasses();
    loadPlanSummary();
  }, [loadClasses, loadFlashcardSessions, loadLessonSessions, loadPlanSummary, loadQuizSessions, loadSessions]);

  useEffect(() => {
    if (classes.length === 0) {
      loadClasses();
    }
  }, [classes.length, loadClasses]);

  useEffect(() => {
    let cancelled = false;
    const localContext = readStoredLearningContext();
    const hasLocalContext = Boolean(
      localContext?.mode ||
      localContext?.class_name ||
      localContext?.subject_name ||
      localContext?.folder_name ||
      localContext?.content_id
    );

    if (hasLocalContext) {
      applyPersistedContext(localContext).catch(() => {
        // Keep bootstrapping even if local restoration is partial.
      });
    }

    const loadSavedContext = async () => {
      try {
        const res = await apiFetch("/context", { skipSessionExpiredEvent: true });
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        const hasSavedContext = Boolean(
          data?.mode === "explorer" ||
          data?.class_name ||
          data?.subject_name ||
          data?.folder_name ||
          data?.content_id
        );
        if (hasSavedContext) {
          writeStoredLearningContext(data);
          await applyPersistedContext(data);
        }
      } catch {
        // Local storage fallback is enough if the session endpoint is unavailable.
      } finally {
        if (!cancelled) {
          setContextHydrated(true);
        }
      }
    };

    loadSavedContext();
    return () => {
      cancelled = true;
    };
  }, [apiFetch, applyPersistedContext]);

  useEffect(() => {
    if (!contextHydrated || !contextMode) return;
    const payload = {
      mode: contextMode === "explorer" ? "explorer" : "contextual",
      class_name: selectedClass || null,
      subject_name: selectedSubject || null,
      folder_name: selectedFolder || null,
      content_id: selectedContent || null,
    };
    writeStoredLearningContext(payload);
    apiFetch("/context", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch(() => {
      // Local storage persistence is still available offline or during transient backend failures.
    });
  }, [apiFetch, contextHydrated, contextMode, selectedClass, selectedContent, selectedFolder, selectedSubject]);

  useEffect(() => {
    if (hasPromptedForContext || !contextHydrated || effectiveUserRole !== "student") return;
    const hasSavedChoice = contextMode === "explorer" || Boolean(selectedClass && selectedSubject);
    if (!hasSavedChoice) {
      setContextPrompt("Choose your class and subject to personalize the workspace, or continue in Explorer Mode.");
      setIsContextModalOpen(true);
    }
    setHasPromptedForContext(true);
  }, [contextHydrated, contextMode, effectiveUserRole, hasPromptedForContext, selectedClass, selectedSubject]);

  useEffect(() => {
    if (!shouldGateStructuredWorkspace) return;
    setContextPrompt("Please select your class and subject to continue");
    setIsContextModalOpen(true);
  }, [shouldGateStructuredWorkspace]);

  useEffect(() => {
    if (!contextProcessing?.fileId) return undefined;

    let cancelled = false;
    const pollProcessing = async () => {
      try {
        const res = await apiFetch(`/files/index-status?file_id=${encodeURIComponent(contextProcessing.fileId)}`);
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        const item = Array.isArray(data?.items) ? data.items[0] : null;
        if (!item) return;

        const friendly = buildFriendlyProcessingState(item);
        setContextProcessing({ fileId: item.file_id, ...friendly });

        const needsRetry = !friendly.ready && String(item?.upload_status || "").toUpperCase() === "FAILED";
        if (needsRetry && !contextRetryFileIdsRef.current.has(item.file_id)) {
          contextRetryFileIdsRef.current.add(item.file_id);
          const retryBody = new FormData();
          retryBody.append("scope", "file");
          retryBody.append("file_id", String(item.file_id));
          apiFetch("/files/reindex", { method: "POST", body: retryBody }).catch(() => {
            contextRetryFileIdsRef.current.delete(item.file_id);
          });
        }

        if (friendly.ready && selectedClass && selectedSubject) {
          await loadContents(selectedClass, selectedSubject, selectedFolder || "Notes");
        }
      } catch {
        // Keep the last visible friendly status if polling fails temporarily.
      }
    };

    pollProcessing();
    const intervalId = window.setInterval(pollProcessing, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [apiFetch, contextProcessing?.fileId, loadContents, selectedClass, selectedFolder, selectedSubject]);

  useEffect(() => {
    if (sessionId) {
      loadHistory(sessionId);
    }
  }, [loadHistory, sessionId]);

  const toggleAutoSpeak = useCallback(() => {
    setAutoSpeak((prev) => {
      localStorage.setItem("autoSpeak", !prev);
      return !prev;
    });
  }, []);

  useEffect(() => {
    const handleShortcut = (event) => {
      const target = event.target;
      const isTypingTarget =
        target instanceof HTMLElement &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);

      if (isTypingTarget) return;
      if (!(event.ctrlKey && event.shiftKey)) return;

      const key = event.key.toLowerCase();
      if (key === "1") {
        event.preventDefault();
        setActiveTab("chat");
        return;
      }
      if (key === "2") {
        event.preventDefault();
        setActiveTab("lesson");
        setLessonResultReady(false);
        return;
      }
      if (key === "3") {
        event.preventDefault();
        setActiveTab("quiz");
        setQuizResultReady(false);
        return;
      }
      if (key === "4") {
        event.preventDefault();
        setActiveTab("flashcards");
        setFlashcardResultReady(false);
        return;
      }
      if (key === "5") {
        event.preventDefault();
        setActiveTab("assessment");
        return;
      }
      if (key === "6") {
        event.preventDefault();
        setActiveTab("progress");
        return;
      }
      if (key === "7") {
        event.preventDefault();
        setActiveTab("assignments");
        return;
      }
      if (key === "8") {
        event.preventDefault();
        setActiveTab("billing");
        return;
      }
      if (key === "n") {
        event.preventDefault();
        if (activeTab === "lesson") {
          handleNewLessonSession();
          return;
        }
        if (activeTab === "quiz") {
          handleNewQuizSession();
          return;
        }
        if (activeTab === "flashcards") {
          handleNewFlashcardSession();
          return;
        }
        handleNewChat();
        return;
      }
      if (key === "s") {
        event.preventDefault();
        toggleAutoSpeak();
      }
    };

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [activeTab, handleNewFlashcardSession, handleNewLessonSession, handleNewQuizSession, toggleAutoSpeak]);

  const renderEmptyState = () => {
    if (messages.length > 0 || isStreaming) return null;

    const linkedContextName = currentContextLabel || selectedContentItem?.title || "selected content";

    return (
      <div className="empty-state empty-state--chat">
        <FiMessageSquare />
        <h4>
          {isExplorerMode
            ? "Explore a topic with general learning help"
            : selectedContent
              ? `Ask about ${linkedContextName}`
              : "Start a focused study conversation"}
        </h4>
        <p>
          {isExplorerMode
            ? "Explorer Mode is open for broad educational questions. Choose a class and subject any time to unlock guided lessons, quizzes, flashcards, and file-based help."
            : selectedContent
              ? `The chat is linked to ${linkedContextName}. Ask for explanations, summaries, or problem-solving help based on this material.`
              : "Select content from the knowledge base, then ask for explanations, summaries, or problem-solving help in a clean, distraction-free workspace."}
        </p>
      </div>
    );
  };

  return (
    <div className={`workspace-shell ${drawerOpen ? "" : "workspace-shell--sidebar-collapsed"}`}>
      <aside className={`workspace-sidebar ${drawerOpen ? "" : "workspace-sidebar--collapsed"}`}>
        <div className="workspace-sidebar__header">
          <button
            type="button"
            className="icon-button icon-button--ghost workspace-sidebar__toggle"
            onClick={() => setDrawerOpen((prev) => !prev)}
            title={drawerOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            <FiMenu />
          </button>
          <div className="workspace-sidebar__brand">
            {drawerOpen ? <span>{workspaceBrandSummary}</span> : null}
          </div>
        </div>

        {drawerOpen ? (
          <>
            {activeTab === "chat" && (
              <div className="workspace-sidebar__actions">
                <button
                  type="button"
                  className="primary-button primary-button--block"
                  onClick={handleNewChat}
                >
                  <FiPlus />
                  <span>New Chat Session</span>
                </button>
              </div>
            )}

            <div className="workspace-sidebar__section">
              <div className="workspace-sidebar__section-title">
                <FiLayers />
                <span>Available for you</span>
              </div>
              <div style={{ display: "grid", gap: 12 }}>
                {workspaceNavSections.map((section) => (
                  <div key={section.key}>
                    {workspaceNavSections.length > 1 ? (
                      <div className="sidebar-note" style={{ marginBottom: 8 }}>
                        {section.title}
                      </div>
                    ) : null}
                    <div className="sidebar-tabs">
                      {section.tabs.map((tab) => {
                        const Icon = tab.icon;
                        const showReadyDot = shouldShowWorkspaceReadyDot(tab.id);
                        return (
                          <button
                            key={tab.id}
                            className={activeTab === tab.id ? "active" : ""}
                            onClick={() => handleWorkspaceTabSelect(tab.id)}
                            style={showReadyDot ? { position: "relative" } : undefined}
                          >
                            <Icon />
                            <span>{tab.label}</span>
                            {showReadyDot && (
                              <span
                                style={{
                                  position: "absolute",
                                  top: "-4px",
                                  right: "-4px",
                                  width: "8px",
                                  height: "8px",
                                  borderRadius: "50%",
                                  background: "#10a37f",
                                  boxShadow: "0 0 3px rgba(16, 163, 127, 0.8)",
                                }}
                              />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {activeTab === "chat" && (
              <>
                <div className="workspace-sidebar__section">
                  <div className="workspace-sidebar__section-title">
                    <FiMessageSquare />
                    <span>Chat Sessions</span>
                  </div>

                  <button
                    type="button"
                    className="secondary-button secondary-button--block"
                    onClick={loadSessions}
                  >
                    <FiRefreshCw />
                    <span>Refresh Sessions</span>
                  </button>

                  <div className="session-list">
                    {sessions.length === 0 && (
                      <div className="sidebar-note">Your saved chat sessions will appear here.</div>
                    )}

                    {sessions.map((session) => (
                      <div
                        key={session.id}
                        className={`session-item ${session.id === sessionId ? "active" : ""}`}
                      >
                        <button
                          type="button"
                          className="session-title"
                          onClick={() => switchSession(session)}
                          title={session.title || "New Chat"}
                        >
                          <FiMessageSquare className="session-icon" size={14} />
                          <span className="session-text">{session.title || "New Chat"}</span>
                        </button>
                        <div className="session-actions">
                          <button type="button" className="icon-button icon-button--ghost" onClick={() => renameSession(session)}>
                            <FiEdit />
                          </button>
                          <button type="button" className="icon-button icon-button--ghost" onClick={() => deleteSession(session)}>
                            <FiTrash2 />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

              </>
            )}

            {activeTab === "lesson" && (
              <div className="workspace-sidebar__section">
                <div className="workspace-sidebar__section-title">
                  <FiBookOpen />
                  <span>Saved Lesson Plans</span>
                </div>

                <button
                  type="button"
                  className="secondary-button secondary-button--block"
                  onClick={loadLessonSessions}
                >
                  <FiRefreshCw />
                  <span>Refresh Lesson Plans</span>
                </button>

                <div className="session-list">
                  {filteredLessonSessions.length === 0 && (
                    <div className="sidebar-note">
                      {currentContextLabel
                        ? "No saved lesson plans for selected content."
                        : "Your saved lesson plans will appear here."}
                    </div>
                  )}

                  {filteredLessonSessions.map((item) => (
                    <div
                      key={item.id}
                      className={`session-item ${item.id === lessonSessionId ? "active" : ""}`}
                    >
                      <button
                        type="button"
                        className="session-title"
                        onClick={() => {
                          persistLessonSession(item.id);
                          setActiveTab("lesson");
                          setLessonResultReady(false);
                        }}
                        title={item.title || "Lesson Session"}
                      >
                        <FiBookOpen className="session-icon" size={14} />
                        <span className="session-text">{item.title || "Lesson Session"}</span>
                      </button>
                      <div className="session-actions">
                        <button
                          type="button"
                          className="icon-button icon-button--ghost"
                          onClick={() => renameLessonSession(item)}
                        >
                          <FiEdit />
                        </button>
                        <button
                          type="button"
                          className="icon-button icon-button--ghost"
                          onClick={() => deleteLessonSession(item)}
                        >
                          <FiTrash2 />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "quiz" && (
              <div className="workspace-sidebar__section">
                <div className="workspace-sidebar__section-title">
                  <FiClipboard />
                  <span>Saved Quizzes</span>
                </div>

                <button
                  type="button"
                  className="secondary-button secondary-button--block"
                  onClick={loadQuizSessions}
                >
                  <FiRefreshCw />
                  <span>Refresh Quizzes</span>
                </button>

                <div className="session-list">
                  {filteredQuizSessions.length === 0 && (
                    <div className="sidebar-note">
                      {currentContextLabel
                        ? "No saved quizzes for selected content."
                        : "Your saved quiz sessions will appear here."}
                    </div>
                  )}

                  {filteredQuizSessions.map((item) => (
                    <div key={item.id} className={`session-item ${item.id === quizSessionId ? "active" : ""}`}>
                      <button
                        type="button"
                        className="session-title"
                        onClick={() => {
                          persistQuizSession(item.id);
                          setActiveTab("quiz");
                          setQuizResultReady(false);
                        }}
                        title={item.title || "Quiz Session"}
                      >
                        <FiClipboard className="session-icon" size={14} />
                        <span className="session-text">{item.title || "Quiz Session"}</span>
                      </button>
                      <div className="session-actions">
                        <button type="button" className="icon-button icon-button--ghost" onClick={() => renameQuizSession(item)}>
                          <FiEdit />
                        </button>
                        <button type="button" className="icon-button icon-button--ghost" onClick={() => deleteQuizSession(item)}>
                          <FiTrash2 />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "flashcards" && (
              <div className="workspace-sidebar__section">
                <div className="workspace-sidebar__section-title">
                  <FiLayers />
                  <span>Saved Cards</span>
                </div>

                <button
                  type="button"
                  className="secondary-button secondary-button--block"
                  onClick={loadFlashcardSessions}
                >
                  <FiRefreshCw />
                  <span>Refresh Cards</span>
                </button>

                <div className="session-list">
                  {filteredFlashcardSessions.length === 0 && (
                    <div className="sidebar-note">
                      {currentContextLabel
                        ? "No saved cards for selected content."
                        : "Your saved card sessions will appear here."}
                    </div>
                  )}

                  {filteredFlashcardSessions.map((item) => (
                    <div
                      key={item.id}
                      className={`session-item ${item.id === flashcardSessionId ? "active" : ""}`}
                    >
                      <button
                        type="button"
                        className="session-title"
                        onClick={() => {
                          persistFlashcardSession(item.id);
                          setActiveTab("flashcards");
                          setFlashcardResultReady(false);
                        }}
                        title={item.title || "Cards Session"}
                      >
                        <FiLayers className="session-icon" size={14} />
                        <span className="session-text">{item.title || "Cards Session"}</span>
                      </button>
                      <div className="session-actions">
                        <button
                          type="button"
                          className="icon-button icon-button--ghost"
                          onClick={() => renameFlashcardSession(item)}
                        >
                          <FiEdit />
                        </button>
                        <button
                          type="button"
                          className="icon-button icon-button--ghost"
                          onClick={() => deleteFlashcardSession(item)}
                        >
                          <FiTrash2 />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "notes" && (
              <NotesSidebarSection 
                isActive={activeTab === "notes"} 
                onNoteSelected={(note) => {
                  if (note?.selected_content) {
                    setSelectedContent(note.selected_content);
                  }
                }}
              />
            )}
          </>
        ) : (
          <>
          <div className="workspace-sidebar__compact-actions">
            <div className="workspace-sidebar__compact-group workspace-sidebar__compact-group--top">
              {activeTab === "chat" && (
                <button
                  type="button"
                  className="icon-button"
                  onClick={handleNewChat}
                  title="New chat session (Ctrl+Shift+N)"
                  aria-label="New chat session (Ctrl+Shift+N)"
                >
                  <FiPlus />
                </button>
              )}
            </div>

            <div className="workspace-sidebar__compact-group workspace-sidebar__compact-group--modes">
              {primaryWorkspaceSection.tabs.map((tab) => {
                const Icon = tab.icon;
                const showReadyDot = shouldShowWorkspaceReadyDot(tab.id);
                return (
                  <button
                    key={tab.id}
                    type="button"
                    className={`icon-button ${activeTab === tab.id ? "active" : ""}`}
                    onClick={() => handleWorkspaceTabSelect(tab.id)}
                    title={tab.shortLabel}
                    aria-label={tab.shortLabel}
                  >
                    <Icon />
                    {showReadyDot && <span className="compact-ready-dot" aria-hidden="true" />}
                  </button>
                );
              })}
            </div>

            <div className="workspace-sidebar__compact-group workspace-sidebar__compact-group--bottom">
              {activeTab === "chat" && (
                <button
                  type="button"
                  className="icon-button"
                  onClick={loadSessions}
                  title="Refresh sessions"
                  aria-label="Refresh sessions"
                >
                  <FiRefreshCw />
                </button>
              )}
              {compactSecondaryTabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    className={`icon-button ${activeTab === tab.id ? "active" : ""}`}
                    onClick={() => handleWorkspaceTabSelect(tab.id)}
                    title={tab.shortLabel}
                    aria-label={tab.shortLabel}
                  >
                    <Icon />
                  </button>
                );
              })}
            </div>

          </div>
        </>
        )}
      </aside>

      <main className="workspace-panel">

        <div className="workspace-topbar">
          <div className="workspace-topbar__left">
            <div>
              <div className="workspace-panel__title-row">
                <h2>{panelMeta.title}</h2>
                <span className="workspace-panel__eyebrow workspace-topbar__eyebrow">{workspaceEyebrow}</span>
              </div>
              <p className="sidebar-note">{panelMeta.description}</p>
            </div>
          </div>
          <div className="workspace-topbar__status">
            {planSummary && (
              <span className="status-pill status-pill--plan" title={planUsageSummary}>
                <FiZap />
                <span>{planUsageSummary}</span>
              </span>
            )}
            {selectedContent && (
              <span className="status-pill status-pill--accent">
                <FiFileText />
                <span>Content linked</span>
              </span>
            )}
          </div>
        </div>

        {isExplorerMode && (
          <div className="workspace-mode-banner" role="status" aria-live="polite">
            <FiGlobe />
            <span>Explorer Mode · choose a class to unlock guided study tools</span>
          </div>
        )}

        {shouldShowContextBar && (
          <div className="workspace-context-bar">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={handleUploadFile}
              style={{ display: "none" }}
            />

            <div className="workspace-context-status" role="status" aria-live="polite">
              <div className="workspace-context-status-row">
                <div className="workspace-context-summary" aria-label="Selected learning context">
                  {isExplorerMode ? (
                    <span className="status-pill status-pill--accent workspace-context-pill">General learning only</span>
                  ) : (
                    <>
                      {contextPillItems.length > 0 && (
                        <span className="workspace-context-summary__label">Current Context</span>
                      )}
                      {contextPillItems.map(({ key, icon: Icon, label, value }) => (
                        <span key={key} className="status-pill status-pill--accent workspace-context-pill" title={`${label}: ${value}`}>
                          <Icon />
                          <span className="workspace-context-pill__text">{value}</span>
                        </span>
                      ))}
                    </>
                  )}

                  {(selectedContent || hasViewerContent) && (
                    <button
                      type="button"
                      className="status-pill status-pill--button workspace-context-pill"
                      onClick={() => setIsViewerVisible((prev) => !prev)}
                      disabled={!selectedContent}
                      title={isViewerVisible ? "Hide document" : "Show document"}
                      aria-label={isViewerVisible ? "Hide document" : "Show document"}
                    >
                      {isViewerVisible ? <FiEyeOff /> : <FiEye />}
                      <span>{isViewerVisible ? "Hide Document" : "Show Document"}</span>
                    </button>
                  )}
                </div>

                <div className="workspace-context-actions workspace-context-actions--selectors-row">
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => openContextModal("Choose your class and subject to personalize the workspace.")}
                  >
                    <FiEdit />
                    <span>Edit Context</span>
                  </button>
                </div>
              </div>

              {contextProcessing ? (
                <div className="workspace-context-status-text">
                  <div className={`context-processing context-processing--${contextProcessing.tone || "info"}`}>
                    <strong>{contextProcessing.title}</strong>
                    <span>{contextProcessing.detail}</span>
                    <div className="context-processing__bar" aria-hidden="true">
                      <span style={{ width: `${Math.max(0, Math.min(100, Number(contextProcessing.progress || 0)))}%` }} />
                    </div>
                  </div>
                </div>
              ) : uploadNotice ? (
                <div className="workspace-context-status-text">
                  <span className={`status-inline status-inline--${String(uploadNotice.level || "INFO").toLowerCase()}`}>
                    <strong>{uploadNotice.level || "INFO"}</strong>
                    <span>{uploadNotice.messageId || "MSG-1000"}</span>
                    <span>{uploadNotice.text}</span>
                  </span>
                </div>
              ) : supplementalContextStatus ? (
                <div className="workspace-context-status-text">
                  <span>{supplementalContextStatus}</span>
                </div>
              ) : null}

              {uploadLimitState.blocked && (
                <span className="sidebar-note">
                  Upload limit reached ({uploadLimitState.used}/{uploadLimitState.limit}). Upgrade plan to continue.
                </span>
              )}
              {!isExplorerMode && !hasRequiredStudyContext && (
                <span className="sidebar-note">Please select your class and subject to continue</span>
              )}
            </div>
          </div>
        )}

        <div
          ref={workspaceBodyRef}
          className={`workspace-body ${isDraggingViewer ? "workspace-body--resizing" : ""}`}
          style={
            shouldShowSideViewer
              ? {
                  gridTemplateColumns: `minmax(0, ${100 - effectiveViewerWidth}%) 8px minmax(0, ${effectiveViewerWidth}%)`,
                }
              : { gridTemplateColumns: "1fr" }
          }
        >
          {activeTab === "chat" && (
          <div ref={chatPanelRef} className="workspace-main chat-panel">
            <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>

            <div ref={chatMessagesRef} className="workspace-messages chat-messages">
              {wsError && (
                <div className="ws-error-banner">
                  <span>{wsError}</span>
                  <button
                    type="button"
                    className="icon-button icon-button--ghost"
                    onClick={() => setWsError("")}
                    aria-label="Dismiss"
                  >
                    ×
                  </button>
                </div>
              )}
              {renderEmptyState()}

              {messages.map((msg, index) => (
                <div key={index} className={`message-row ${msg.type}`}>
                  <div className="message-bubble">
                    {msg.type === "ai" && looksLikeStructuredSummary(msg.text) ? (
                      <SummaryViewer
                        content={translatedMessages[index] || msg.text}
                        sourceQuery={index > 0 && messages[index - 1]?.type === "user" ? messages[index - 1].text : ""}
                        sessionId={sessionId}
                        selectedContent={selectedContent}
                        onOpenNotes={() => handleWorkspaceTabSelect("notes")}
                      />
                    ) : (
                      <MessageContent content={translatedMessages[index] || msg.text} />
                    )}
                    {msg.type === "ai" && preferredLanguage !== "en" && (
                      <button
                        type="button"
                        className="message-translate-btn"
                        onClick={() => handleTranslateMessage(index, msg.text)}
                        disabled={translatingId === index}
                        aria-label={translatedMessages[index] ? "Show original" : `Translate to ${preferredLanguage}`}
                        title={translatedMessages[index] ? "Show original" : `Translate to ${preferredLanguage}`}
                      >
                        <FiGlobe aria-hidden="true" />
                        <span>{translatingId === index ? "…" : translatedMessages[index] ? "Original" : "Translate"}</span>
                      </button>
                    )}
                    {msg.type === "ai" && Array.isArray(msg.quickReplies) && msg.quickReplies.length > 0 && (
                      <div className="message-quick-replies">
                        {msg.quickReplies.map((reply, replyIndex) => {
                          const label = String(reply?.label ?? reply?.value ?? reply ?? "").trim();
                          const value = String(reply?.value ?? reply?.label ?? reply ?? "").trim();
                          if (!label || !value) return null;
                          return (
                            <button
                              key={`${index}-${replyIndex}-${value}`}
                              type="button"
                              className="secondary-button message-quick-reply"
                              onClick={() => handleSend(value)}
                              disabled={isStreaming}
                            >
                              {label}
                            </button>
                          );
                        })}
                      </div>
                    )}
                    {(msg.level || msg.messageId) && (
                      <div className="message-meta">
                        {msg.level && <span>{msg.level}</span>}
                        {msg.messageId && <span>{msg.messageId}</span>}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {isStreaming && (
                <div className="message-row ai">
                  <div className="message-bubble">
                    {currentStream ? (
                      <>
                        <div style={{ display: "inline" }}>
                          <MessageContent content={currentStream} />
                          <span className="cursor">▌</span>
                        </div>
                        {streamStatus && (
                          <div className="stream-status">
                            <span>{streamStatus}</span>
                          </div>
                        )}
                      </>
                    ) : (
                      <span className="thinking">
                        {streamStatus || "Thinking"}
                        <span className="dots"></span>
                      </span>
                    )}
                  </div>
                </div>
              )}

              <div
                ref={messagesEndRef}
                style={{ height: 1, scrollMarginBottom: "calc(var(--chat-composer-height, 112px) + 24px)" }}
              />
            </div>

            {!isNearBottom && messages.length > 0 && (
              <button
                type="button"
                className="scroll-to-bottom-button"
                onClick={scrollToConversationEnd}
                aria-label="Scroll to latest message"
                title="Scroll to latest message"
              >
                <FiArrowDown />
              </button>
            )}

            <div ref={chatComposerRef} className="workspace-input chat-input-container">
              <div className="workspace-input__field">
                <input
                  type="text"
                  placeholder="Ask a question, request a summary, or work through a problem..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                />
              </div>
              <div className="workspace-input__actions workspace-input__actions--row chat-composer-toolbar">
                <div className="chat-composer-toolbar__group chat-composer-toolbar__group--left">
                  <VoiceControl onResult={handleVoice} compact />
                  <LanguagePicker onChange={setPreferredLanguage} compact={false} />
                </div>

                <div className="chat-composer-toolbar__group chat-composer-toolbar__group--right">
                  <button
                    type="button"
                    className="icon-button chat-composer-tool"
                    onClick={handleNewChat}
                    title="New chat session"
                    aria-label="New chat session"
                  >
                    <FiPlus />
                  </button>
                  <button
                    type="button"
                    className={`icon-button chat-composer-tool ${autoSpeak ? "chat-composer-tool--active" : ""}`}
                    onClick={toggleAutoSpeak}
                    title={autoSpeak ? "Turn auto speak off (Ctrl+Shift+S)" : "Turn auto speak on (Ctrl+Shift+S)"}
                    aria-label={autoSpeak ? "Turn auto speak off (Ctrl+Shift+S)" : "Turn auto speak on (Ctrl+Shift+S)"}
                  >
                    {autoSpeak ? <FiVolume2 /> : <FiVolumeX />}
                  </button>
                  {isStreaming && (
                    <button
                      type="button"
                      className="secondary-button chat-composer-stop"
                      onClick={() => {
                        closeSocket();
                        setIsStreaming(false);
                        setCurrentStream("");
                      }}
                      title="Stop response"
                      aria-label="Stop response"
                    >
                      <FiSquare />
                      <span>Stop</span>
                    </button>
                  )}
                  <button
                    type="button"
                    className="primary-button chat-composer-send"
                    onClick={handleSend}
                    title="Send message"
                    aria-label="Send message"
                  >
                    <FiSend />
                    <span>Send</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
          </div>
          )}

          <div style={{ display: activeTab === "lesson" ? "flex" : "none", flex: 1, minHeight: 0 }}>
            {shouldGateStructuredWorkspace ? renderContextGate("Lessons") : (
              <LessonPanel
                sessionId={sessionId}
                lessonSessionId={lessonSessionId}
                onLessonSessionChange={persistLessonSession}
                onLessonSessionsChange={loadLessonSessions}
                planSummary={planSummary}
                defaultChapter={lessonDefaultChapter}
                prefillContext={planActionPrefill.lesson.context}
                autoRunToken={planActionPrefill.lesson.autoRunToken}
                prefilledPlanData={planActionPrefill.lesson.generatedPayload}
                currentContextLabel={currentContextLabel}
                selectedContentId={selectedContent || null}
                hasLinkedContent={Boolean(selectedContent)}
                isContextViewerVisible={shouldShowViewer}
                onOpenContext={() => setIsViewerVisible(true)}
                onResultReady={() => activeTab !== "lesson" && setLessonResultReady(true)}
              />
            )}
          </div>

          <div style={{ display: activeTab === "quiz" ? "flex" : "none", flex: 1, minHeight: 0 }}>
            {shouldGateStructuredWorkspace ? renderContextGate("Quiz") : (
              <QuizPanel
                sessionId={sessionId}
                quizSessionId={quizSessionId}
                onQuizSessionChange={persistQuizSession}
                onQuizSessionsChange={loadQuizSessions}
                planSummary={planSummary}
                defaultChapter={quizDefaultChapter}
                prefillContext={planActionPrefill.quiz.context}
                autoRunToken={planActionPrefill.quiz.autoRunToken}
                prefilledQuizData={planActionPrefill.quiz.generatedPayload}
                chapterOptions={chapterOptions}
                currentContextLabel={currentContextLabel}
                selectedContentId={selectedContent || null}
                hasLinkedContent={Boolean(selectedContent)}
                isContextViewerVisible={shouldShowViewer}
                onOpenContext={() => setIsViewerVisible(true)}
                onResultReady={() => activeTab !== "quiz" && setQuizResultReady(true)}
              />
            )}
          </div>

          <div style={{ display: activeTab === "flashcards" ? "flex" : "none", flex: 1, minHeight: 0 }}>
            {shouldGateStructuredWorkspace ? renderContextGate("Flashcards") : (
              <FlashcardPanel
                sessionId={sessionId}
                flashcardSessionId={flashcardSessionId}
                onFlashcardSessionChange={persistFlashcardSession}
                onFlashcardSessionsChange={loadFlashcardSessions}
                planSummary={planSummary}
                defaultChapter={inferredChapter}
                selectedClass={selectedClass}
                selectedSubject={selectedSubject}
                selectedFolder={selectedFolder}
                chapterOptions={chapterOptions}
                currentContextLabel={currentContextLabel}
                hasLinkedContent={Boolean(selectedContent)}
                isContextViewerVisible={shouldShowViewer}
                onOpenContext={() => setIsViewerVisible(true)}
                onResultReady={() => activeTab !== "flashcards" && setFlashcardResultReady(true)}
              />
            )}
          </div>

          <div style={{ display: activeTab === "assessment" ? "flex" : "none", flex: 1, minHeight: 0 }}>
            {shouldGateStructuredWorkspace ? renderContextGate("Assessment") : (
              <AssessmentPanel
                planSummary={planSummary}
                defaultSubject={selectedSubject || ""}
                selectedClass={selectedClass || ""}
                prefillSubject={planActionPrefill.assessment.subject}
                prefillContext={planActionPrefill.assessment.context}
                prefillQuizMode={planActionPrefill.assessment.mode}
                prefillDifficulty={planActionPrefill.assessment.difficulty}
                prefillNumQuestions={planActionPrefill.assessment.numQuestions}
                autoRunToken={planActionPrefill.assessment.autoRunToken}
              />
            )}
          </div>

          <div style={{ display: activeTab === "notes" ? "flex" : "none", flex: 1, minHeight: 0 }}>
            <NotesPanel
              isActive={activeTab === "notes"}
              contextPillItems={contextPillItems}
              hasLinkedContent={Boolean(selectedContent)}
              hasViewerContent={hasViewerContent}
              isContextViewerVisible={shouldShowViewer}
              onToggleViewer={() => setIsViewerVisible((prev) => !prev)}
              onOpenContext={() => openContextModal("Choose your class and subject to personalize the workspace.")}
            />
          </div>

          <div style={{ display: activeTab === "assignments" ? "flex" : "none", flex: 1, minHeight: 0 }}>
            <AssignmentsPanel
              onPlanAction={handleProgressPlanAction}
              isActive={activeTab === "assignments"}
              viewRole={effectiveUserRole}
            />
          </div>

          <div style={{ display: activeTab === "progress" ? "flex" : "none", flex: 1, minHeight: 0 }}>
            <ProgressPanel
              planSummary={planSummary}
              onPlanAction={handleProgressPlanAction}
              isActive={activeTab === "progress"}
            />
          </div>

          <div style={{ display: activeTab === "admin" ? "flex" : "none", flex: 1, minHeight: 0 }}>
            <AdminPanel
              viewRole={effectiveUserRole}
              onAdminViewRoleChange={handleAdminViewRoleChange}
              onAdminReindex={handleReindex}
              onAdminIncrementalReindex={handleIncrementalReindex}
              adminRunning={adminRunning}
              adminMessage={adminMessage}
              adminStatus={adminStatus}
              isActive={activeTab === "admin"}
            />
          </div>

          <div style={{ display: activeTab === "roles" ? "flex" : "none", flex: 1, minHeight: 0 }}>
            <RoleHubPanel
              onPlanAction={handleProgressPlanAction}
              actualRole={userRole}
              viewRole={effectiveUserRole}
              onAdminViewRoleChange={handleAdminViewRoleChange}
              onAdminReindex={handleReindex}
              onAdminIncrementalReindex={handleIncrementalReindex}
              adminRunning={adminRunning}
              adminMessage={adminMessage}
            />
          </div>

          <div style={{ display: activeTab === "profile" ? "flex" : "none", flex: 1, minHeight: 0 }}>
            <ProfilePanel
              planSummary={planSummary}
              onOpenSubscription={openSubscriptionModal}
              onProfileUpdated={loadPlanSummary}
              isActive={activeTab === "profile"}
            />
          </div>

          <div style={{ display: activeTab === "billing" ? "flex" : "none", flex: 1, minHeight: 0 }}>
            <BillingPanel
              planSummary={planSummary}
              onOpenSubscription={openSubscriptionModal}
              onRefresh={loadPlanSummary}
              isLoading={subscriptionLoading}
            />
          </div>

          {shouldShowSideViewer && (
            <div
              className="viewer-splitter"
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize source viewer"
              onMouseDown={startViewerDrag}
            />
          )}

          {shouldShowSideViewer && (
            <aside className="pdf-view">
              <div className="workspace-panel__header workspace-panel__header--compact">
                <div>
                  <div className="workspace-panel__eyebrow">
                    <FiFileText />
                    <span>Source viewer</span>
                  </div>
                  <h3>Attached document</h3>
                </div>
                <div className="viewer-toolbar">
                  <button
                    type="button"
                    className="icon-button icon-button--ghost viewer-close-button"
                    onClick={toggleViewerMaximize}
                    disabled={!shouldShowViewer}
                    title={isViewerMaximized ? "Exit popup" : "Open popup"}
                    aria-label={isViewerMaximized ? "Exit popup" : "Open popup"}
                  >
                    {isViewerMaximized ? <FiMinimize2 /> : <FiMaximize2 />}
                  </button>
                  <button
                    type="button"
                    className="icon-button icon-button--ghost viewer-close-button"
                    onClick={openViewerInNewTab}
                    disabled={!shouldShowViewer}
                    title="Open in new tab"
                    aria-label="Open in new tab"
                  >
                    <FiExternalLink />
                  </button>
                  <button
                    type="button"
                    className="icon-button icon-button--ghost viewer-close-button"
                    onClick={() => setIsViewerVisible(false)}
                    title="Close source viewer"
                    aria-label="Close source viewer"
                  >
                    <FiX />
                  </button>
                </div>
              </div>
              <iframe src={pdfBlobUrl} title="PDF Viewer" width="100%" height="100%" />
            </aside>
          )}

          {shouldShowViewer && isViewerMaximized && (
            <div className="viewer-modal" role="dialog" aria-modal="true" aria-label="Expanded source viewer">
              <div className="viewer-modal__content">
                <div className="viewer-modal__header">
                  <div className="workspace-panel__eyebrow">
                    <FiFileText />
                    <span>Source viewer</span>
                  </div>
                  <div className="viewer-toolbar">
                    <button
                      type="button"
                      className="icon-button icon-button--ghost"
                      onClick={openViewerInNewTab}
                      title="Open in new tab"
                    >
                      <FiExternalLink />
                      <span>Open in New Tab</span>
                    </button>
                    <button
                      type="button"
                      className="icon-button icon-button--ghost"
                      onClick={toggleViewerMaximize}
                      title="Exit popup"
                    >
                      <FiMinimize2 />
                      <span>Exit</span>
                    </button>
                  </div>
                </div>
                <iframe src={pdfBlobUrl} title="PDF Viewer Popup" width="100%" height="100%" />
              </div>
            </div>
          )}

          {isContextModalOpen && (
            <div
              className="context-modal"
              role="dialog"
              aria-modal="true"
              aria-label="Choose learning context"
              onClick={() => setIsContextModalOpen(false)}
            >
              <div className="context-modal__content" onClick={(event) => event.stopPropagation()}>
                <div className="subscription-modal__header">
                  <div>
                    <div className="workspace-panel__eyebrow">
                      <FiBookOpen />
                      <span>Learning setup</span>
                    </div>
                    <h3>Choose your learning context</h3>
                    <p>{contextPrompt || "Select your class and subject, or continue in Explorer Mode for general learning chat."}</p>
                  </div>
                  <button
                    type="button"
                    className="icon-button icon-button--ghost"
                    onClick={() => setIsContextModalOpen(false)}
                    aria-label="Close learning setup"
                  >
                    <FiX />
                  </button>
                </div>

                <div className="context-modal__grid">
                  <section className="subscription-card context-modal__section">
                    <h4>1. Pick your study area</h4>
                    <div className="context-modal__field-list">
                      <div className="workspace-select-wrap">
                        <FiLayers />
                        <select
                          aria-label="Select class"
                          value={selectedClass || ""}
                          onChange={handleClassChange}
                          onFocus={() => {
                            if (classes.length === 0) loadClasses();
                          }}
                        >
                          <option value="">Class</option>
                          {visibleClasses.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="workspace-select-wrap">
                        <FiBook />
                        <select
                          aria-label="Select subject"
                          value={selectedSubject || ""}
                          onChange={handleSubjectChange}
                          disabled={!selectedClass}
                        >
                          <option value="">Subject</option>
                          {subjects.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="workspace-select-wrap">
                        <FiFolder />
                        <select
                          aria-label="Select folder"
                          value={selectedFolder || ""}
                          onChange={handleFolderChange}
                          disabled={!selectedSubject}
                        >
                          <option value="">Folder</option>
                          {folders.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="workspace-select-wrap">
                        <FiFileText />
                        <select
                          aria-label="Select file"
                          value={selectedContent || ""}
                          onChange={handleContentChange}
                          disabled={contents.length === 0}
                        >
                          <option value="">File</option>
                          {contents.map((item) => (
                            <option key={item.content_id} value={item.content_id} disabled={item.selectable === false}>
                              {item.selectable === false
                                ? `${item.title} [${item.status_label || "Processing"}]`
                                : item.title}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <p className="sidebar-note">Class and subject are required for guided study tools. Folder and file are optional.</p>
                    {planSummary && <p className="sidebar-note">{classAccessSummary}</p>}
                  </section>

                  <section className="subscription-card context-modal__section">
                    <h4>2. Add your own notes</h4>
                    <div
                      className={`context-dropzone ${contextDropActive ? "is-active" : ""}`}
                      onDragOver={(event) => {
                        event.preventDefault();
                        setContextDropActive(true);
                      }}
                      onDragLeave={() => setContextDropActive(false)}
                      onDrop={handleContextDrop}
                    >
                      <FiArrowDown />
                      <strong>Drag and drop a PDF here</strong>
                      <span>
                        We’ll save it to <strong>{selectedFolder || "Notes"}</strong>, prepare it in the background, and let you keep studying.
                      </span>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={!selectedClass || !selectedSubject || isUploading || uploadLimitState.blocked}
                      >
                        <FiPlus />
                        <span>{isUploading ? "Uploading..." : "Choose PDF"}</span>
                      </button>
                      {uploadLimitState.blocked ? (
                        <span className="sidebar-note">
                          Upload limit reached ({uploadLimitState.used}/{uploadLimitState.limit}). Upgrade plan to continue.
                        </span>
                      ) : null}
                    </div>

                    <div className="context-modal__actions">
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={refreshIndexedFiles}
                        disabled={!selectedClass || !selectedSubject || kbStatus.contentsLoading}
                      >
                        <FiRefreshCw />
                        <span>Refresh files</span>
                      </button>
                      <button type="button" className="secondary-button" onClick={handleExplorerModeSelection}>
                        <FiGlobe />
                        <span>Proceed in Explorer Mode</span>
                      </button>
                      <button
                        type="button"
                        className="primary-button"
                        onClick={saveLearningContext}
                        disabled={!selectedClass || !selectedSubject}
                      >
                        <FiCheck />
                        <span>Continue with this context</span>
                      </button>
                    </div>
                  </section>
                </div>
              </div>
            </div>
          )}

          {isSubscriptionModalOpen && (
            <div
              className="subscription-modal"
              role="dialog"
              aria-modal="true"
              aria-label="Subscription planner"
              onClick={() => setIsSubscriptionModalOpen(false)}
            >
              <div className="subscription-modal__content" onClick={(event) => event.stopPropagation()}>
                <div className="subscription-modal__header">
                  <div>
                    <div className="workspace-panel__eyebrow">
                      <FiCreditCard />
                      <span>Subscription planner</span>
                    </div>
                    <h3>Estimate your annual plan</h3>
                  </div>
                  <button
                    type="button"
                    className="icon-button icon-button--ghost"
                    onClick={() => setIsSubscriptionModalOpen(false)}
                    aria-label="Close subscription planner"
                  >
                    <FiX />
                  </button>
                </div>

                {subscriptionLoading ? (
                  <p className="sidebar-note">Loading subscription catalog...</p>
                ) : (
                  <>
                    {subscriptionError && (
                      <div className="subscription-modal__error">{subscriptionError}</div>
                    )}

                    <div className="subscription-modal__grid">
                      <section className="subscription-card">
                        <h4>Select classes</h4>
                        <div className="subscription-class-list">
                          {(subscriptionCatalog?.class_rates || []).map((item) => {
                            const className = item.class_name;
                            const checked = selectedSubscriptionClasses.includes(className);
                            return (
                              <label key={className} className={`subscription-class-item ${checked ? "is-active" : ""}`}>
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={() => toggleSubscriptionClass(className)}
                                />
                                <span>{className}</span>
                                <strong>{formatInrFromCents(item.annual_price_cents, item.currency)}</strong>
                              </label>
                            );
                          })}
                        </div>

                        <div className="subscription-form-row">
                          <label htmlFor="promoCode">Promo code</label>
                          <input
                            id="promoCode"
                            type="text"
                            value={promoCode}
                            onChange={(event) => setPromoCode(event.target.value.toUpperCase())}
                            placeholder="WELCOME10"
                          />
                        </div>

                        <label className="subscription-checkbox-row">
                          <input
                            type="checkbox"
                            checked={autoRenewSubscription}
                            onChange={(event) => setAutoRenewSubscription(event.target.checked)}
                          />
                          <span>Enable auto-renew on annual cycle</span>
                        </label>

                        <button
                          type="button"
                          className="primary-button primary-button--block"
                          onClick={requestSubscriptionQuote}
                          disabled={subscriptionQuoting}
                        >
                          <FiZap />
                          <span>{subscriptionQuoting ? "Calculating..." : "Get Quote"}</span>
                        </button>
                      </section>

                      <section className="subscription-card">
                        <h4>Quote summary</h4>
                        {!subscriptionQuote ? (
                          <p className="sidebar-note">
                            Pick classes and request a quote to view subtotal, discount, and annual total.
                          </p>
                        ) : (
                          <>
                            <div className="subscription-quote-row">
                              <span>Subtotal</span>
                              <strong>{formatInrFromCents(subscriptionQuote.subtotal_cents, subscriptionQuote.currency)}</strong>
                            </div>
                            <div className="subscription-quote-row">
                              <span>Discount</span>
                              <strong>-{formatInrFromCents(subscriptionQuote.discount_cents, subscriptionQuote.currency)}</strong>
                            </div>
                            <div className="subscription-quote-row subscription-quote-row--total">
                              <span>Annual total</span>
                              <strong>{formatInrFromCents(subscriptionQuote.total_cents, subscriptionQuote.currency)}</strong>
                            </div>

                            {subscriptionQuote?.promo?.code && (
                              <p className="sidebar-note">
                                Applied promo: <strong>{subscriptionQuote.promo.code}</strong>
                              </p>
                            )}

                            <button
                              className="btn-primary subscription-confirm-btn"
                              onClick={confirmSubscription}
                              disabled={subscriptionActivating}
                            >
                              <FiCreditCard />
                              <span>{subscriptionActivating ? "Processing..." : "Confirm & Subscribe"}</span>
                            </button>
                          </>
                        )}

                        {subscriptionActivated && (
                          <div className="subscription-activated">
                            <FiCheck />
                            <div>
                              <strong>Subscription active!</strong>
                              <p>
                                {(subscriptionActivated.active_classes || [])
                                  .map((item) => (typeof item === "string" ? item : item?.class_name))
                                  .filter(Boolean)
                                  .join(", ") || "Selected classes"} — expires{" "}
                                {new Date(subscriptionActivated.expires_at).toLocaleDateString()}
                              </p>
                            </div>
                          </div>
                        )}

                        <h4>Current plan entitlements</h4>
                        {Array.isArray(planSummary?.classes) && planSummary.classes.length > 0 ? (
                          <p className="sidebar-note">
                            Active classes: {planSummary.classes.map((item) => item?.class_name).filter(Boolean).join(", ")}
                          </p>
                        ) : (
                          <p className="sidebar-note">No class-specific subscriptions are active yet.</p>
                        )}
                        <div className="subscription-entitlements">
                          {(planSummary?.entitlements || []).slice(0, 7).map((item) => (
                            <div key={item.feature_key} className="subscription-entitlement-item">
                              <FiCheck />
                              <span>
                                {item.feature_key.replace(/_/g, " ")}
                                {item.enabled ? "" : " (upgrade required)"}
                              </span>
                            </div>
                          ))}
                        </div>
                      </section>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}