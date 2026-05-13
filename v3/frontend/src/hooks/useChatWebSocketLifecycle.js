import { useEffect, useRef } from "react";
import { closeSocket, connectWebSocket } from "../services/websocket";

export function useChatWebSocketLifecycle({
  handleIncomingToken,
  handleError = () => {},
  clearStreamWatchdog,
  connect = connectWebSocket,
  close = closeSocket,
}) {
  const incomingTokenHandlerRef = useRef(handleIncomingToken);
  const errorHandlerRef = useRef(handleError);

  useEffect(() => {
    incomingTokenHandlerRef.current = handleIncomingToken;
  }, [handleIncomingToken]);

  useEffect(() => {
    errorHandlerRef.current = handleError;
  }, [handleError]);

  useEffect(() => {
    connect(
      (token) => incomingTokenHandlerRef.current(token),
      () => {
        // Let [END] or watchdog finalize UI state; avoid hiding partial stream abruptly.
        clearStreamWatchdog();
      },
      (error) => errorHandlerRef.current(error)
    );

    return () => {
      close();
    };
  }, [clearStreamWatchdog, close, connect]);
}