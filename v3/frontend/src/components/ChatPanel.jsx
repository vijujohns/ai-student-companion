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
import QuizPanel from "./QuizPanel";
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
        buildTab("assignments", "Assignments", FiCheck),
        buildTab("progress", "Progress", FiBarChart2),
        buildTab("assessment", "Assessment", FiEdit),
      ]
      : normalizedRole === "parent"
        ? [
          buildTab("roles", "Family Hub", FiUser, "Family Hub"),
          buildTab("assignments", "Assignments", FiCheck),
          buildTab("progress", "Progress", FiBarChart2),
        ]
        : normalizedRole === "student"
          ? [
            buildTab("chat", "Chat Workspace", FiMessageSquare, "Chat"),
            buildTab("lesson", "Lesson Workspace", FiBook, "Lesson"),
            buildTab("quiz", "Quiz Workspace", FiClipboard, "Quiz"),
            buildTab("flashcards", "Cards Workspace", FiLayers, "Cards"),
            buildTab("assignments", "Assignments", FiCheck),
            buildTab("progress", "Progress", FiBarChart2),
          ]
          : [
            buildTab("roles", "Role Hub", FiUser, "Role Hub"),
            buildTab("chat", "Chat Workspace", FiMessageSquare, "Chat"),
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
  const [isUploading, setIsUploading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [adminRunning, setAdminRunning] = useState(false);
  const [adminMessage, setAdminMessage] = useState("");
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
  const currentStreamMetaRef = useRef({ messageId: null, level: null });
  const isStreamingRef = useRef(false);
  const sessionIdRef = useRef(sessionId);
  const autoSpeakRef = useRef(autoSpeak);
  const activeStreamSessionRef = useRef(null);
  const pendingResponseRef = useRef(false);
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
  const shouldShowContextBar = ["chat", "lesson", "quiz", "flashcards", "assessment"].includes(activeTab);
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

  const handleWorkspaceTabSelect = useCallback((tabId) => {
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
  }, []);

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

  const handleUploadFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!selectedClass || !selectedSubject || !selectedFolder) {
      setUploadNotice({
        level: "ERROR",
        messageId: "MSG-1303",
        text: "Select class, subject, and folder before uploading a PDF.",
      });
      event.target.value = "";
      return;
    }

    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setUploadNotice({
        level: "ERROR",
        messageId: "MSG-1304",
        text: "Only PDF files are supported.",
      });
      event.target.value = "";
      return;
    }

    const displayName = file.name.replace(/\.pdf$/i, "").trim() || file.name;
    const formData = new FormData();
    formData.append("class_name", selectedClass);
    formData.append("subject_name", selectedSubject);
    formData.append("folder_name", selectedFolder);
    formData.append("display_name", displayName);
    formData.append("upload", file);

    setIsUploading(true);
    setUploadNotice(null);

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
        return;
      }

      setUploadNotice({
        level: data?.message?.level || "INFO",
        messageId: data?.message?.message_id || "MSG-1301",
        text:
          data?.message?.user_text ||
          "Upload accepted. Indexing is running in the background. The file becomes selectable after indexing.",
      });

      await loadContents(selectedClass, selectedSubject, selectedFolder);
    } catch (err) {
      console.error("❌ Upload failed:", err);
      setUploadNotice({
        level: "ERROR",
        messageId: "MSG-1304",
        text: "Upload failed. Please try again.",
      });
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
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
            buildCompletedStreamMessage(finalText, currentStreamMetaRef.current),
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
    setAdminRunning(true);
    setAdminMessage("Reindexing knowledge base...");
    try {
      const res = await apiFetch("/admin/reindex", { method: "POST" });
      const data = await res.json();
      const meta = getEnvelopeMessage(data);
      setAdminMessage(meta ? messageSummary(meta) : data.status || "Reindex completed.");
    } catch {
      setAdminMessage("Reindex failed.");
    } finally {
      setAdminRunning(false);
    }
  };

  const handleIncrementalReindex = async () => {
    setAdminRunning(true);
    setAdminMessage("Incremental reindexing...");
    try {
      const res = await apiFetch("/admin/reindex-incremental", { method: "POST" });
      const data = await res.json();
      const meta = getEnvelopeMessage(data);
      setAdminMessage(meta ? messageSummary(meta) : data.status || "Incremental reindex completed.");
    } catch {
      setAdminMessage("Incremental reindex failed.");
    } finally {
      setAdminRunning(false);
    }
  };

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
        <h4>{selectedContent ? `Ask about ${linkedContextName}` : "Start a focused study conversation"}</h4>
        <p>
          {selectedContent
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
            {(selectedContent || hasViewerContent) && (
              <div className="viewer-controls">
                <button
                  type="button"
                  className="icon-button icon-button--ghost"
                  onClick={() => setIsViewerVisible((prev) => !prev)}
                  disabled={!selectedContent}
                  title={isViewerVisible ? "Hide viewer" : "Show viewer"}
                >
                  {isViewerVisible ? <FiEyeOff /> : <FiEye />}
                  <span>{isViewerVisible ? "Hide Viewer" : "Show Viewer"}</span>
                </button>
                <button
                  type="button"
                  className="icon-button icon-button--ghost"
                  onClick={toggleViewerMaximize}
                  disabled={!shouldShowViewer}
                  title={isViewerMaximized ? "Exit popup" : "Open popup"}
                >
                  {isViewerMaximized ? <FiMinimize2 /> : <FiMaximize2 />}
                  <span>{isViewerMaximized ? "Exit Popup" : "Popup"}</span>
                </button>
                <button
                  type="button"
                  className="icon-button icon-button--ghost"
                  onClick={openViewerInNewTab}
                  disabled={!shouldShowViewer}
                  title="Open viewer in a new tab"
                >
                  <FiExternalLink />
                  <span>Open New</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {shouldShowContextBar && (
          <div className="workspace-context-bar">
            <div className="workspace-context-status" role="status" aria-live="polite">
              <div className="workspace-context-status-row">
                <div className="workspace-context-status-text">
                  {uploadNotice ? (
                    <span className={`status-inline status-inline--${String(uploadNotice.level || "INFO").toLowerCase()}`}>
                      <strong>{uploadNotice.level || "INFO"}</strong>
                      <span>{uploadNotice.messageId || "MSG-1000"}</span>
                      <span>{uploadNotice.text}</span>
                    </span>
                  ) : (
                    kbStatusMessage
                  )}
                </div>
              </div>

              {uploadLimitState.blocked && (
                <span className="sidebar-note">
                  Upload limit reached ({uploadLimitState.used}/{uploadLimitState.limit}). Upgrade plan to continue.
                </span>
              )}
              {planSummary && (
                <span className="sidebar-note">{classAccessSummary}</span>
              )}
            </div>

            <div className="workspace-select-wrap workspace-select-wrap--compact">
              <FiLayers />
              <select
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

            <div className="workspace-select-wrap workspace-select-wrap--compact">
              <FiBook />
              <select
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

            <div className="workspace-select-wrap workspace-select-wrap--compact">
              <FiFolder />
              <select
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

            <div className="workspace-select-wrap workspace-select-wrap--compact">
              <FiFileText />
              <select
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

            <div className="workspace-context-actions workspace-context-actions--selectors-row">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleUploadFile}
                style={{ display: "none" }}
              />

              <button
                type="button"
                className="secondary-button"
                disabled={
                  isUploading ||
                  uploadLimitState.blocked ||
                  !selectedClass ||
                  !selectedSubject ||
                  !selectedFolder
                }
                onClick={() => fileInputRef.current?.click()}
              >
                <FiPlus />
                <span>{isUploading ? "Uploading..." : "Upload PDF"}</span>
              </button>

              <button
                type="button"
                className="secondary-button"
                disabled={kbStatus.contentsLoading}
                onClick={refreshIndexedFiles}
              >
                <FiRefreshCw />
                <span>Refresh</span>
              </button>
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
                    <MessageContent content={translatedMessages[index] || msg.text} />
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
              <div className="workspace-input__actions workspace-input__actions--row">
                <VoiceControl onResult={handleVoice} />
                <LanguagePicker onChange={setPreferredLanguage} compact={false} />
                <button
                  type="button"
                  className="secondary-button"
                  onClick={handleNewChat}
                >
                  <FiPlus />
                  <span>New Chat Session</span>
                </button>
                <button
                  type="button"
                  className="icon-button"
                  onClick={toggleAutoSpeak}
                  title={autoSpeak ? "Auto speak on (Ctrl+Shift+S)" : "Auto speak off (Ctrl+Shift+S)"}
                  aria-label={autoSpeak ? "Auto speak on (Ctrl+Shift+S)" : "Auto speak off (Ctrl+Shift+S)"}
                >
                  {autoSpeak ? <FiVolume2 /> : <FiVolumeX />}
                  <span>{autoSpeak ? "Auto Speak On" : "Auto Speak Off"}</span>
                </button>
                <button type="button" className="primary-button" onClick={handleSend}>
                  <FiSend />
                  <span>Send</span>
                </button>
                {isStreaming && (
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => {
                      closeSocket();
                      setIsStreaming(false);
                      setCurrentStream("");
                    }}
                  >
                    <FiSquare />
                    <span>Stop</span>
                  </button>
                )}
              </div>
            </div>
          </div>
          </div>
          )}

          <div style={{ display: activeTab === "lesson" ? "flex" : "none", flex: 1, minHeight: 0 }}>
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
              hasLinkedContent={Boolean(selectedContent)}
              isContextViewerVisible={shouldShowViewer}
              onOpenContext={() => setIsViewerVisible(true)}
              onResultReady={() => activeTab !== "lesson" && setLessonResultReady(true)}
            />
          </div>

          <div style={{ display: activeTab === "quiz" ? "flex" : "none", flex: 1, minHeight: 0 }}>
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
              hasLinkedContent={Boolean(selectedContent)}
              isContextViewerVisible={shouldShowViewer}
              onOpenContext={() => setIsViewerVisible(true)}
              onResultReady={() => activeTab !== "quiz" && setQuizResultReady(true)}
            />
          </div>

          <div style={{ display: activeTab === "flashcards" ? "flex" : "none", flex: 1, minHeight: 0 }}>
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
          </div>

          <div style={{ display: activeTab === "assessment" ? "flex" : "none", flex: 1, minHeight: 0 }}>
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
                      title="Open viewer in a new tab"
                    >
                      <FiExternalLink />
                      <span>Open New</span>
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