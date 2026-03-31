import { useCallback } from "react";
import { sendMessage } from "../services/websocket";

export function useChatSendMessage({
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
  send = sendMessage,
}) {
  const handleSend = useCallback(async () => {
    if (!input.trim()) return;

    const currentSession = sessionId || Date.now().toString();

    setMessages((prev) => [...prev, { type: "user", text: input }]);
    setCurrentStream("");
    currentStreamRef.current = "";
    currentStreamMetaRef.current = { messageId: null, level: null };
    pendingResponseRef.current = true;
    isStreamingRef.current = true;
    activeStreamSessionRef.current = currentSession;
    armStreamStallHint();
    setWsError("");
    setIsStreaming(true);

    if (!sessionId) {
      setSessionId(currentSession);
      localStorage.setItem("session_id", currentSession);
    }

    if (selectedContent) {
      try {
        await apiFetch(`/sessions/${currentSession}/content`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content_id: selectedContent }),
        });
      } catch (err) {
        console.error("❌ Failed to persist selected content:", err);
      }
    }

    send({
      query: input,
      session_id: currentSession,
      context_id: selectedContent,
    });

    armStreamWatchdog(currentSession);
    setInput("");

    setTimeout(() => loadSessions(), 500);
  }, [
    activeStreamSessionRef,
    apiFetch,
    armStreamStallHint,
    armStreamWatchdog,
    currentStreamMetaRef,
    currentStreamRef,
    input,
    isStreamingRef,
    loadSessions,
    pendingResponseRef,
    selectedContent,
    send,
    sessionId,
    setCurrentStream,
    setInput,
    setIsStreaming,
    setMessages,
    setSessionId,
    setWsError,
  ]);

  return { handleSend };
}
