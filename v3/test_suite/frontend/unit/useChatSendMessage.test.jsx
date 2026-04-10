import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatSendMessage } from "../../../frontend/src/hooks/useChatSendMessage";

describe("useChatSendMessage", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("does nothing for blank input", async () => {
    const send = vi.fn();
    const { result } = renderHook(() =>
      useChatSendMessage({
        input: "   ",
        sessionId: "s1",
        selectedContent: null,
        setMessages: vi.fn(),
        setCurrentStream: vi.fn(),
        setWsError: vi.fn(),
        setIsStreaming: vi.fn(),
        setSessionId: vi.fn(),
        setInput: vi.fn(),
        currentStreamRef: { current: "" },
        currentStreamMetaRef: { current: { messageId: "x", level: "INFO", quickReplies: [] } },
        pendingResponseRef: { current: false },
        isStreamingRef: { current: false },
        activeStreamSessionRef: { current: null },
        armStreamStallHint: vi.fn(),
        armStreamWatchdog: vi.fn(),
        loadSessions: vi.fn(),
        apiFetch: vi.fn(),
        send,
      })
    );

    await act(async () => {
      await result.current.handleSend();
    });

    expect(send).not.toHaveBeenCalled();
  });

  it("sends message and persists selected content", async () => {
    vi.spyOn(Date, "now").mockReturnValue(123456);

    const setMessages = vi.fn();
    const setCurrentStream = vi.fn();
    const setWsError = vi.fn();
    const setIsStreaming = vi.fn();
    const setSessionId = vi.fn();
    const setInput = vi.fn();
    const armStreamStallHint = vi.fn();
    const armStreamWatchdog = vi.fn();
    const loadSessions = vi.fn();
    const apiFetch = vi.fn().mockResolvedValue({ ok: true });
    const send = vi.fn();
    const currentStreamRef = { current: "existing" };
    const currentStreamMetaRef = { current: { messageId: "old", level: "WARN", quickReplies: [{ label: "old", value: "old" }] } };
    const pendingResponseRef = { current: false };
    const isStreamingRef = { current: false };
    const activeStreamSessionRef = { current: null };

    const { result } = renderHook(() =>
      useChatSendMessage({
        input: "Explain this chapter",
        sessionId: null,
        selectedContent: "kb:abc",
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
        send,
      })
    );

    await act(async () => {
      await result.current.handleSend();
    });

    expect(setSessionId).toHaveBeenCalledWith("123456");
    expect(localStorage.getItem("session_id")).toBe("123456");
    expect(setCurrentStream).toHaveBeenCalledWith("");
    expect(setWsError).toHaveBeenCalledWith("");
    expect(setIsStreaming).toHaveBeenCalledWith(true);
    expect(armStreamStallHint).toHaveBeenCalledTimes(1);
    expect(armStreamWatchdog).toHaveBeenCalledWith("123456");
    expect(apiFetch).toHaveBeenCalledWith("/sessions/123456/content", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content_id: "kb:abc" }),
    });
    expect(send).toHaveBeenCalledWith({
      query: "Explain this chapter",
      session_id: "123456",
      context_id: "kb:abc",
    });
    expect(setInput).toHaveBeenCalledWith("");

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(loadSessions).toHaveBeenCalledTimes(1);
    expect(currentStreamRef.current).toBe("");
    expect(currentStreamMetaRef.current).toEqual({ messageId: null, level: null, quickReplies: [] });
    expect(pendingResponseRef.current).toBe(true);
    expect(isStreamingRef.current).toBe(true);
    expect(activeStreamSessionRef.current).toBe("123456");
  });
});
