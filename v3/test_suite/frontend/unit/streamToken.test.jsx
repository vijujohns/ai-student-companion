import { describe, expect, it } from "vitest";
import {
  buildCompletedStreamMessage,
  isWebsocketErrorToken,
  mergeStreamMeta,
  normalizeStreamPayload,
  resetStreamMeta,
  shouldCommitCompletedStream,
  shouldSkipStreamPayload,
  shouldSpeakText,
  WS_ERROR_PREFIX,
} from "../../../frontend/src/utils/streamToken";

describe("streamToken utilities", () => {
  it("blocks transport/system text for speech", () => {
    expect(shouldSpeakText("WebSocket closed unexpectedly while streaming")).toBe(false);
    expect(shouldSpeakText("This is a normal tutoring answer")).toBe(true);
  });

  it("normalizes object and string token payloads", () => {
    expect(normalizeStreamPayload({ token: "Hello", message_id: "m1", level: "INFO" })).toEqual({
      text: "Hello",
      messageId: "m1",
      level: "INFO",
    });

    expect(normalizeStreamPayload("World")).toEqual({
      text: "World",
      messageId: null,
      level: null,
    });
  });

  it("detects websocket error token prefix", () => {
    expect(isWebsocketErrorToken(`${WS_ERROR_PREFIX} connection issue`)).toBe(true);
    expect(isWebsocketErrorToken("normal token")).toBe(false);
  });

  it("skips empty and obsolete ack payloads", () => {
    expect(shouldSkipStreamPayload({ text: "" })).toBe(true);
    expect(shouldSkipStreamPayload({ text: "..." })).toBe(true);
    expect(shouldSkipStreamPayload({ text: "Useful text" })).toBe(false);
  });

  it("resets and merges stream metadata safely", () => {
    expect(resetStreamMeta()).toEqual({ messageId: null, level: null });

    expect(mergeStreamMeta({ messageId: "m1", level: "INFO" }, { messageId: null, level: "WARN" })).toEqual({
      messageId: "m1",
      level: "WARN",
    });

    expect(mergeStreamMeta({ messageId: "m1", level: "INFO" }, { text: "chunk" })).toEqual({
      messageId: "m1",
      level: "INFO",
    });
  });

  it("builds completion decision and final ai message", () => {
    expect(shouldCommitCompletedStream("answer", true)).toBe(true);
    expect(shouldCommitCompletedStream("", true)).toBe(false);
    expect(shouldCommitCompletedStream("answer", false)).toBe(false);

    expect(buildCompletedStreamMessage("final", { messageId: "m1", level: "INFO" })).toEqual({
      type: "ai",
      text: "final",
      messageId: "m1",
      level: "INFO",
    });
  });
});
