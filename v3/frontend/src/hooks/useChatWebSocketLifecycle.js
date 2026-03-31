import { useEffect, useRef } from "react";
import { closeSocket, connectWebSocket } from "../services/websocket";

export function useChatWebSocketLifecycle({
  handleIncomingToken,
  clearStreamWatchdog,
  connect = connectWebSocket,
  close = closeSocket,
}) {
  const incomingTokenHandlerRef = useRef(handleIncomingToken);

  useEffect(() => {
    incomingTokenHandlerRef.current = handleIncomingToken;
  }, [handleIncomingToken]);

  useEffect(() => {
    connect(
      (token) => incomingTokenHandlerRef.current(token),
      () => {
        // Let [END] or watchdog finalize UI state; avoid hiding partial stream abruptly.
        clearStreamWatchdog();
      }
    );

    return () => {
      close();
    };
  }, [clearStreamWatchdog, close, connect]);
}