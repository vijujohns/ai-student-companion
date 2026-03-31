import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useChatWebSocketLifecycle } from "../../../frontend/src/hooks/useChatWebSocketLifecycle";

describe("useChatWebSocketLifecycle", () => {
  it("wires message/close callbacks and cleans up socket on unmount", () => {
    let messageHandler;
    let closeHandler;

    const connect = vi.fn((onMessage, onClose) => {
      messageHandler = onMessage;
      closeHandler = onClose;
    });
    const close = vi.fn();
    const clearStreamWatchdog = vi.fn();
    const firstHandler = vi.fn();
    const secondHandler = vi.fn();

    const { rerender, unmount } = renderHook(
      ({ handler }) =>
        useChatWebSocketLifecycle({
          handleIncomingToken: handler,
          clearStreamWatchdog,
          connect,
          close,
        }),
      { initialProps: { handler: firstHandler } }
    );

    expect(connect).toHaveBeenCalledTimes(1);

    messageHandler("token-1");
    expect(firstHandler).toHaveBeenCalledWith("token-1");

    rerender({ handler: secondHandler });
    messageHandler("token-2");
    expect(secondHandler).toHaveBeenCalledWith("token-2");

    closeHandler();
    expect(clearStreamWatchdog).toHaveBeenCalledTimes(1);

    unmount();
    expect(close).toHaveBeenCalledTimes(1);
  });
});
