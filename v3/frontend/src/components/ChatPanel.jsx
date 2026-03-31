import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  FiArrowDown,
  FiBook,
  FiBookOpen,
  FiClipboard,
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
  FiVolume2,
  FiVolumeX,
  FiZap,
} from "react-icons/fi";
import { apiFetch, parseApiError, getEnvelopeMessage, messageSummary } from "../services/api";
import { closeSocket, sendMessage } from "../services/websocket";
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
import MessageContent from "./MessageContent";
import QuizPanel from "./QuizPanel";
import VoiceControl from "./VoiceControl";
import "./style.css";

export default function ChatPanel() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [currentStream, setCurrentStream] = useState("");
  const [streamStatus, setStreamStatus] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [wsError, setWsError] = useState("");
  const [sessionId, setSessionId] = useState(localStorage.getItem("session_id") || null);
  const userId = localStorage.getItem("username") || "student";
  const userRole = localStorage.getItem("role") || "user";
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
  const [activeTab, setActiveTab] = useState("chat");
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

  const selectedContentItem = contents.find((item) => item.content_id === selectedContent) || null;
  const inferredChapter = selectedContentItem?.title || selectedFolder || "";
  const chapterOptions = contents.map((item) => item.title);
  const currentContextLabel = selectedContentItem?.title || selectedFolder || null;

  const { planSummary, loadPlanSummary, getUsageLimitState } = usePlanSummary();
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
  const hasViewerContent = Boolean(pdfBlobUrl);

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
        formatted.push({ type: "user", text: item.question });
        formatted.push({ type: "ai", text: item.answer });
      });
      setMessages(formatted);
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
    if (value) {
      setIsViewerVisible(true);
      setIsViewerMaximized(false);
    }
  };

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
            {drawerOpen && (
              <div>
                <strong>Workspace</strong>
                <span>Conversations, lessons, and quizzes</span>
              </div>
            )}
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
                <span>Workspace Mode</span>
              </div>
              <div className="sidebar-tabs">
                <button
                  className={activeTab === "chat" ? "active" : ""}
                  onClick={() => setActiveTab("chat")}
                >
                  <FiMessageSquare />
                  <span>Chat Workspace</span>
                </button>
                <button
                  className={activeTab === "lesson" ? "active" : ""}
                  onClick={() => {
                    setActiveTab("lesson");
                    setLessonResultReady(false);
                  }}
                  style={{ position: "relative" }}
                >
                  <FiBook />
                  <span>Lesson Workspace</span>
                  {lessonResultReady && activeTab !== "lesson" && (
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
                <button
                  className={activeTab === "quiz" ? "active" : ""}
                  onClick={() => {
                    setActiveTab("quiz");
                    setQuizResultReady(false);
                  }}
                  style={{ position: "relative" }}
                >
                  <FiClipboard />
                  <span>Quiz Workspace</span>
                  {quizResultReady && activeTab !== "quiz" && (
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
                <button
                  className={activeTab === "flashcards" ? "active" : ""}
                  onClick={() => {
                    setActiveTab("flashcards");
                    setFlashcardResultReady(false);
                  }}
                  style={{ position: "relative" }}
                >
                  <FiLayers />
                  <span>Cards Workspace</span>
                  {flashcardResultReady && activeTab !== "flashcards" && (
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

                {isAdmin && (
                  <div className="workspace-sidebar__section admin-panel">
                    <div className="workspace-sidebar__section-title">
                      <FiShield />
                      <span>Admin Tools</span>
                    </div>
                    <button type="button" className="secondary-button secondary-button--block" onClick={handleReindex} disabled={adminRunning}>
                      <FiBookOpen />
                      <span>Reindex Knowledge Base</span>
                    </button>
                    <button
                      type="button"
                      className="secondary-button secondary-button--block"
                      onClick={handleIncrementalReindex}
                      disabled={adminRunning}
                    >
                      <FiZap />
                      <span>Incremental Reindex</span>
                    </button>
                    {(adminRunning || adminMessage) && (
                      <div className="admin-message">{adminRunning ? "Processing..." : adminMessage}</div>
                    )}
                  </div>
                )}
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
              <button
                type="button"
                className={`icon-button ${activeTab === "chat" ? "active" : ""}`}
                onClick={() => setActiveTab("chat")}
                title="Chat (Ctrl+Shift+1)"
                aria-label="Chat (Ctrl+Shift+1)"
              >
                <FiMessageSquare />
              </button>
              <button
                type="button"
                className={`icon-button ${activeTab === "lesson" ? "active" : ""}`}
                onClick={() => {
                  setActiveTab("lesson");
                  setLessonResultReady(false);
                }}
                title="Lesson (Ctrl+Shift+2)"
                aria-label="Lesson (Ctrl+Shift+2)"
              >
                <FiBook />
                {lessonResultReady && activeTab !== "lesson" && (
                  <span className="compact-ready-dot" aria-hidden="true" />
                )}
              </button>
              <button
                type="button"
                className={`icon-button ${activeTab === "quiz" ? "active" : ""}`}
                onClick={() => {
                  setActiveTab("quiz");
                  setQuizResultReady(false);
                }}
                title="Quiz (Ctrl+Shift+3)"
                aria-label="Quiz (Ctrl+Shift+3)"
              >
                <FiClipboard />
                {quizResultReady && activeTab !== "quiz" && (
                  <span className="compact-ready-dot" aria-hidden="true" />
                )}
              </button>
              <button
                type="button"
                className={`icon-button ${activeTab === "flashcards" ? "active" : ""}`}
                onClick={() => {
                  setActiveTab("flashcards");
                  setFlashcardResultReady(false);
                }}
                title="Cards (Ctrl+Shift+4)"
                aria-label="Cards (Ctrl+Shift+4)"
              >
                <FiLayers />
                {flashcardResultReady && activeTab !== "flashcards" && (
                  <span className="compact-ready-dot" aria-hidden="true" />
                )}
              </button>
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
            </div>
          </div>
        )}
      </aside>

      <main className={`workspace-main ${activeTab === "chat" && !selectedContent ? "workspace-main--chat-expanded" : ""}`}>
        <div className="workspace-topbar">
          <div className="workspace-topbar__left">
            <div>
              <h2>
                {activeTab === "chat"
                  ? "Chat"
                  : activeTab === "lesson"
                    ? "Lessons"
                    : activeTab === "quiz"
                      ? "Quiz"
                      : "Flashcards"}
              </h2>
              <p>
                {activeTab === "chat"
                  ? "Ask questions against your selected material and keep each study session organized."
                  : activeTab === "lesson"
                    ? "Use the lesson panel for guided next steps and structured teaching flow."
                    : activeTab === "quiz"
                      ? "Use the quiz panel for targeted recall and rapid evaluation."
                      : "Generate and review card-based flashcards from lesson steps."}
              </p>
            </div>
          </div>

          <div className="workspace-topbar__status">
            {planSummary && (
              <span className="status-pill status-pill--plan">
                <FiZap />
                <span>
                  {planSummary.planCode}
                  {planSummary.isTrial ? " Trial" : ""}
                  {` · Ask ${planSummary.usage.ask_count || 0}/${planSummary.limits.ask_count || 0}`}
                </span>
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
              {classes.map((item) => (
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
          <section
            ref={chatPanelRef}
            className={`workspace-panel chat-panel ${selectedContent ? "" : "chat-panel--full"}`} 
            style={{ display: activeTab === "chat" ? "flex" : "none" }}
          >
            <div className="workspace-panel__header">
              <div>
                <div className="workspace-panel__eyebrow">
                  <FiMessageSquare />
                  <span>Conversation</span>
                </div>
                <h3>{selectedContent ? "Context-aware chat" : "General chat"}</h3>
                <p>
                  {selectedContent
                    ? "Your responses will stay anchored to the selected study material."
                    : "Select study material to anchor answers, or begin with a general question."}
                </p>
              </div>
            </div>

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
                    <MessageContent content={msg.text} />
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

              <div ref={messagesEndRef} />
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
          </section>

          <div style={{ display: activeTab === "lesson" ? "flex" : "none", flex: 1, minHeight: 0 }}>
            <LessonPanel
              sessionId={sessionId}
              lessonSessionId={lessonSessionId}
              onLessonSessionChange={persistLessonSession}
              onLessonSessionsChange={loadLessonSessions}
              planSummary={planSummary}
              defaultChapter={inferredChapter}
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
              defaultChapter={inferredChapter}
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
        </div>
      </main>
    </div>
  );
}