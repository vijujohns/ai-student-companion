import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useStreamTimers } from "../../../frontend/src/hooks/useStreamTimers";

describe("useStreamTimers", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("updates stream status for stall hint sequence", () => {
    const setStreamStatus = vi.fn();

    const { result } = renderHook(() =>
      useStreamTimers({
        loadHistory: vi.fn(),
        setStreamStatus,
        setIsStreaming: vi.fn(),
        setCurrentStream: vi.fn(),
        currentStreamRef: { current: "" },
        isStreamingRef: { current: true },
        pendingResponseRef: { current: true },
        activeStreamSessionRef: { current: "s1" },
      })
    );

    act(() => {
      result.current.armStreamStallHint();
    });

    expect(setStreamStatus).toHaveBeenCalledWith("Generating answer...");

    act(() => {
      vi.advanceTimersByTime(6000);
    });

    expect(setStreamStatus).toHaveBeenCalledWith("Still working... finalizing full answer");
  });

  it("watchdog finalizes stalled stream and reloads history", () => {
    const loadHistory = vi.fn();
    const setStreamStatus = vi.fn();
    const setIsStreaming = vi.fn();
    const setCurrentStream = vi.fn();
    const currentStreamRef = { current: "partial" };
    const isStreamingRef = { current: true };
    const pendingResponseRef = { current: true };
    const activeStreamSessionRef = { current: "s1" };

    const { result } = renderHook(() =>
      useStreamTimers({
        loadHistory,
        setStreamStatus,
        setIsStreaming,
        setCurrentStream,
        currentStreamRef,
        isStreamingRef,
        pendingResponseRef,
        activeStreamSessionRef,
      })
    );

    act(() => {
      result.current.armStreamWatchdog("session-123");
      vi.advanceTimersByTime(90000);
    });

    expect(loadHistory).toHaveBeenCalledWith("session-123", { force: true });
    expect(setIsStreaming).toHaveBeenCalledWith(false);
    expect(setCurrentStream).toHaveBeenCalledWith("");
    expect(setStreamStatus).toHaveBeenCalledWith("");
    expect(isStreamingRef.current).toBe(false);
    expect(currentStreamRef.current).toBe("");
    expect(pendingResponseRef.current).toBe(false);
    expect(activeStreamSessionRef.current).toBe(null);
  });
});
