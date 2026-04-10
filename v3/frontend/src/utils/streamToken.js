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

function normalizeQuickReplies(rawQuickReplies) {
  if (!Array.isArray(rawQuickReplies)) return [];
  return rawQuickReplies
    .map((item) => {
      if (typeof item === "string") {
        return { label: item, value: item };
      }
      if (item && typeof item === "object") {
        const label = String(item.label ?? item.text ?? item.value ?? "").trim();
        const value = String(item.value ?? item.label ?? item.text ?? "").trim();
        if (label && value) return { label, value };
      }
      return null;
    })
    .filter(Boolean);
}

export function normalizeStreamPayload(rawToken) {
  if (typeof rawToken === "object" && rawToken !== null) {
    return {
      text: String(rawToken.text ?? rawToken.token ?? rawToken.content ?? ""),
      messageId: rawToken.message_id || rawToken.messageId || null,
      level: rawToken.level || null,
      replaceText: Boolean(rawToken.replaceText ?? rawToken.replace ?? false),
      quickReplies: normalizeQuickReplies(rawToken.quickReplies ?? rawToken.quick_replies),
    };
  }

  return { text: String(rawToken ?? ""), messageId: null, level: null, replaceText: false, quickReplies: [] };
}

export function shouldSkipStreamPayload(payload) {
  return (!payload?.text && !payload?.replaceText) || payload.text === "...";
}

export function resetStreamMeta() {
  return { messageId: null, level: null, quickReplies: [] };
}

export function mergeStreamMeta(currentMeta, payload) {
  const nextQuickReplies = Array.isArray(payload?.quickReplies) && payload.quickReplies.length
    ? payload.quickReplies
    : currentMeta?.quickReplies || [];

  if (!payload?.messageId && !payload?.level && nextQuickReplies === (currentMeta?.quickReplies || [])) {
    return currentMeta;
  }

  return {
    messageId: payload?.messageId || currentMeta?.messageId || null,
    level: payload?.level || currentMeta?.level || null,
    quickReplies: nextQuickReplies,
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
    quickReplies: Array.isArray(meta?.quickReplies) ? meta.quickReplies : [],
  };
}