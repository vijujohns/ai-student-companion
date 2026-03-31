export const WS_ERROR_PREFIX = "\n\n⚠️";

export function shouldSpeakText(text) {
  const normalized = String(text || "").toLowerCase();
  if (!normalized.trim()) return false;

  const blockedFragments = [
    "connection error while contacting the ai server",
    "websocket closed unexpectedly",
    "open browser console for details",
    "check backend logs in debug.log",
    "httpexception",
    "traceback",
  ];

  return !blockedFragments.some((fragment) => normalized.includes(fragment));
}

export function isWebsocketErrorToken(rawToken) {
  return typeof rawToken === "string" && rawToken.startsWith(WS_ERROR_PREFIX);
}

export function normalizeStreamPayload(rawToken) {
  if (typeof rawToken === "object" && rawToken !== null) {
    return {
      text: String(rawToken.text ?? rawToken.token ?? rawToken.content ?? ""),
      messageId: rawToken.message_id || rawToken.messageId || null,
      level: rawToken.level || null,
    };
  }

  return { text: String(rawToken ?? ""), messageId: null, level: null };
}

export function shouldSkipStreamPayload(payload) {
  return !payload?.text || payload.text === "...";
}

export function resetStreamMeta() {
  return { messageId: null, level: null };
}

export function mergeStreamMeta(currentMeta, payload) {
  if (!payload?.messageId && !payload?.level) return currentMeta;

  return {
    messageId: payload.messageId || currentMeta?.messageId || null,
    level: payload.level || currentMeta?.level || null,
  };
}

export function shouldCommitCompletedStream(finalText, wasExpected) {
  return Boolean(finalText && wasExpected);
}

export function buildCompletedStreamMessage(finalText, meta) {
  return {
    type: "ai",
    text: finalText,
    messageId: meta?.messageId || null,
    level: meta?.level || null,
  };
}