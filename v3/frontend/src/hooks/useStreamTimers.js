import { useCallback, useEffect, useRef } from "react";

const STREAM_STALL_HINT_MS = 6000;
const STREAM_WATCHDOG_MS = 210000;

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
    }, STREAM_STALL_HINT_MS);
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
      }, STREAM_WATCHDOG_MS);
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