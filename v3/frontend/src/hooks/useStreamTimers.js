import { useCallback, useEffect, useRef } from "react";

export function useStreamTimers({
  loadHistory,
  setStreamStatus,
  setIsStreaming,
  setCurrentStream,
  currentStreamRef,
  isStreamingRef,
  pendingResponseRef,
  activeStreamSessionRef,
}) {
  const streamTimeoutRef = useRef(null);
  const streamStallTimeoutRef = useRef(null);

  const clearStreamWatchdog = useCallback(() => {
    if (streamTimeoutRef.current) {
      clearTimeout(streamTimeoutRef.current);
      streamTimeoutRef.current = null;
    }
  }, []);

  const clearStreamStallHint = useCallback(() => {
    if (streamStallTimeoutRef.current) {
      clearTimeout(streamStallTimeoutRef.current);
      streamStallTimeoutRef.current = null;
    }
  }, []);

  const armStreamStallHint = useCallback(() => {
    clearStreamStallHint();
    setStreamStatus("Generating answer...");
    streamStallTimeoutRef.current = setTimeout(() => {
      setStreamStatus("Still working... finalizing full answer");
    }, 6000);
  }, [clearStreamStallHint, setStreamStatus]);

  const armStreamWatchdog = useCallback(
    (sessionForWatchdog) => {
      if (!sessionForWatchdog) return;
      clearStreamWatchdog();
      streamTimeoutRef.current = setTimeout(() => {
        if (!isStreamingRef.current) return;
        loadHistory(sessionForWatchdog, { force: true });
        isStreamingRef.current = false;
        setIsStreaming(false);
        setCurrentStream("");
        currentStreamRef.current = "";
        pendingResponseRef.current = false;
        activeStreamSessionRef.current = null;
        setStreamStatus("");
      }, 90000);
    },
    [
      activeStreamSessionRef,
      clearStreamWatchdog,
      currentStreamRef,
      isStreamingRef,
      loadHistory,
      pendingResponseRef,
      setCurrentStream,
      setIsStreaming,
      setStreamStatus,
    ]
  );

  useEffect(
    () => () => {
      clearStreamWatchdog();
      clearStreamStallHint();
    },
    [clearStreamStallHint, clearStreamWatchdog]
  );

  return {
    clearStreamWatchdog,
    clearStreamStallHint,
    armStreamStallHint,
    armStreamWatchdog,
  };
}