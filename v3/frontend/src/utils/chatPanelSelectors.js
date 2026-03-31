export function buildUsageLimitState(planSummary, action) {
  if (!planSummary) {
    return { blocked: false, used: 0, limit: 0, remaining: 0 };
  }

  const fieldByAction = {
    upload: "uploads_count",
    quiz: "quiz_count",
    flashcard: "flashcard_count",
    lesson: "lesson_count",
    ask: "ask_count",
  };

  const field = fieldByAction[action];
  if (!field) return { blocked: false, used: 0, limit: 0, remaining: 0 };

  const used = Number(planSummary.usage?.[field] || 0);
  const limit = Number(planSummary.limits?.[field] || 0);
  const blocked = limit > 0 ? used >= limit : false;
  const remaining = Math.max(limit - used, 0);

  return { blocked, used, limit, remaining };
}

export function filterSessionsByContext(sessions, currentContextLabel, activeSessionId = "") {
  if (!currentContextLabel) return sessions;

  const context = String(currentContextLabel).toLowerCase();
  const activeId = String(activeSessionId || "");

  return sessions.filter((item) => {
    if (activeId && String(item?.id || "") === activeId) return true;
    const chapter = String(item?.chapter || "").toLowerCase();
    const title = String(item?.title || "").toLowerCase();
    return chapter.includes(context) || title.includes(context);
  });
}