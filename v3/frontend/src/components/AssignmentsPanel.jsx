import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FiBookOpen, FiCheckCircle, FiClock, FiRefreshCw } from "react-icons/fi";
import { apiFetch, parseApiError } from "../services/api";

function parseDueDateValue(value) {
  const rawValue = String(value || "").trim();
  if (!rawValue) return null;
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(rawValue) ? `${rawValue}T00:00:00` : rawValue;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function getAssignmentDueMeta(dueLabel) {
  if (!dueLabel) {
    return { label: "", tone: "neutral", bucket: "none", sortTime: Number.MAX_SAFE_INTEGER };
  }

  const parsed = parseDueDateValue(dueLabel);
  if (!parsed) {
    return { label: "Scheduled", tone: "neutral", bucket: "scheduled", sortTime: Number.MAX_SAFE_INTEGER - 1 };
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dueDate = new Date(parsed);
  dueDate.setHours(0, 0, 0, 0);
  const diffDays = Math.round((dueDate.getTime() - today.getTime()) / 86400000);

  if (diffDays < 0) {
    return { label: "Overdue", tone: "high", bucket: "overdue", sortTime: dueDate.getTime() };
  }
  if (diffDays <= 3) {
    return { label: "Due soon", tone: "medium", bucket: "due-soon", sortTime: dueDate.getTime() };
  }
  return { label: "Scheduled", tone: "low", bucket: "scheduled", sortTime: dueDate.getTime() };
}

function matchesAssignmentFilter(item, filterValue = "all") {
  const status = String(item?.status || "assigned").toLowerCase();
  const dueMeta = getAssignmentDueMeta(item?.due_label);

  switch (filterValue) {
    case "open":
      return status === "assigned";
    case "completed":
      return status === "completed";
    case "dismissed":
      return status === "dismissed";
    case "overdue":
      return status === "assigned" && dueMeta.bucket === "overdue";
    case "due-soon":
      return status === "assigned" && dueMeta.bucket === "due-soon";
    default:
      return true;
  }
}

function matchesAssignmentSearch(item, query = "") {
  const searchValue = String(query || "").trim().toLowerCase();
  if (!searchValue) return true;
  const haystack = [item?.title, item?.description, item?.chapter_hint, item?.due_label]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(searchValue);
}

function compareAssignmentsByPriority(left, right) {
  const leftDueMeta = getAssignmentDueMeta(left?.due_label);
  const rightDueMeta = getAssignmentDueMeta(right?.due_label);
  const leftRank = leftDueMeta.bucket === "overdue" ? 0 : leftDueMeta.bucket === "due-soon" ? 1 : 2;
  const rightRank = rightDueMeta.bucket === "overdue" ? 0 : rightDueMeta.bucket === "due-soon" ? 1 : 2;

  if (leftRank !== rightRank) return leftRank - rightRank;
  if (leftDueMeta.sortTime !== rightDueMeta.sortTime) return leftDueMeta.sortTime - rightDueMeta.sortTime;
  return String(left?.title || "").localeCompare(String(right?.title || ""));
}

function sortAssignmentsForMode(items, sortMode = "priority") {
  const list = [...(items || [])];
  if (sortMode === "title") {
    return list.sort((left, right) => String(left?.title || "").localeCompare(String(right?.title || "")));
  }
  if (sortMode === "due-date") {
    return list.sort((left, right) => getAssignmentDueMeta(left?.due_label).sortTime - getAssignmentDueMeta(right?.due_label).sortTime);
  }
  return list.sort(compareAssignmentsByPriority);
}

export default function AssignmentsPanel({ onPlanAction = null, isActive = true, viewRole = null }) {
  const currentUsername = typeof window !== "undefined" ? localStorage.getItem("username") || "" : "";
  const currentRole = String(
    viewRole || (typeof window !== "undefined" ? (localStorage.getItem("role") || "student") : "student")
  ).toLowerCase() === "user"
    ? "student"
    : String(
      viewRole || (typeof window !== "undefined" ? (localStorage.getItem("role") || "student") : "student")
    ).toLowerCase();
  const isStudentRole = currentRole === "student";
  const isMentorRole = currentRole === "teacher" || currentRole === "parent";
  const [linkedStudents, setLinkedStudents] = useState([]);
  const [selectedStudent, setSelectedStudent] = useState("");
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [assignmentSearch, setAssignmentSearch] = useState("");
  const [assignmentFilter, setAssignmentFilter] = useState("all");
  const [assignmentSort, setAssignmentSort] = useState("priority");
  const [savingItemKey, setSavingItemKey] = useState("");
  const wasActiveRef = useRef(isActive);

  const activeStudent = useMemo(() => {
    if (isStudentRole) return currentUsername;
    if (isMentorRole) return selectedStudent || linkedStudents[0]?.username || "";
    return "";
  }, [currentUsername, isMentorRole, isStudentRole, linkedStudents, selectedStudent]);

  const activeStudentDetails = useMemo(
    () => linkedStudents.find((item) => item?.username === activeStudent) || null,
    [activeStudent, linkedStudents],
  );

  const loadLinkedStudents = useCallback(async () => {
    if (!isMentorRole) {
      setLinkedStudents([]);
      return;
    }

    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/relationships/my-students", { method: "GET" });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not load your linked learners."));
      }
      const json = await res.json();
      const nextStudents = Array.isArray(json?.students) ? json.students : Array.isArray(json?.data?.students) ? json.data.students : [];
      setLinkedStudents(nextStudents);
      setSelectedStudent((current) => {
        if (current && nextStudents.some((item) => item?.username === current)) {
          return current;
        }
        return nextStudents[0]?.username || "";
      });
    } catch (err) {
      setLinkedStudents([]);
      setSelectedStudent("");
      setError(err?.message || "Could not load your linked learners.");
    } finally {
      setLoading(false);
    }
  }, [isMentorRole]);

  const loadAssignments = useCallback(async () => {
    if (!activeStudent) {
      setAssignments([]);
      return;
    }

    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`/students/${encodeURIComponent(activeStudent)}/assignments`);
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not load assignments for this learner."));
      }
      const json = await res.json();
      const payload = json?.data || json;
      const nextAssignments = Array.isArray(payload?.assignments)
        ? payload.assignments
        : Array.isArray(payload)
          ? payload
          : [];
      setAssignments(nextAssignments);
    } catch (err) {
      setError(err?.message || "Could not load assignments for this learner.");
    } finally {
      setLoading(false);
    }
  }, [activeStudent]);

  const handleAssignmentStatusUpdate = useCallback(async (item, nextStatus) => {
    if (!item?.id || !activeStudent) return;
    setSavingItemKey(`assignment:${item.id}`);
    setError("");
    try {
      const res = await apiFetch(`/students/${encodeURIComponent(activeStudent)}/assignments/${encodeURIComponent(item.id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res, "Could not update this assignment."));
      }
      await loadAssignments();
    } catch (err) {
      setError(err?.message || "Could not update this assignment.");
    } finally {
      setSavingItemKey("");
    }
  }, [activeStudent, loadAssignments]);

  useEffect(() => {
    if (isActive && isMentorRole) {
      loadLinkedStudents();
    }
  }, [isActive, isMentorRole, loadLinkedStudents]);

  useEffect(() => {
    if (isActive && (isStudentRole || activeStudent)) {
      loadAssignments();
    }
  }, [activeStudent, isActive, isStudentRole, loadAssignments]);

  useEffect(() => {
    if (isActive && !wasActiveRef.current) {
      if (isMentorRole) {
        loadLinkedStudents();
      } else {
        loadAssignments();
      }
    }
    wasActiveRef.current = isActive;
  }, [isActive, isMentorRole, loadAssignments, loadLinkedStudents]);

  const visibleAssignments = useMemo(
    () => sortAssignmentsForMode(
      [...assignments]
        .filter((item) => matchesAssignmentFilter(item, assignmentFilter))
        .filter((item) => matchesAssignmentSearch(item, assignmentSearch)),
      assignmentSort,
    ),
    [assignmentFilter, assignmentSearch, assignmentSort, assignments],
  );

  const assignmentSummary = useMemo(() => {
    const openItems = assignments.filter((item) => String(item?.status || "assigned").toLowerCase() === "assigned");
    const dueSoon = openItems.filter((item) => getAssignmentDueMeta(item?.due_label).bucket === "due-soon").length;
    const overdue = openItems.filter((item) => getAssignmentDueMeta(item?.due_label).bucket === "overdue").length;
    const completed = assignments.filter((item) => String(item?.status || "").toLowerCase() === "completed").length;
    return {
      open: openItems.length,
      dueSoon,
      overdue,
      completed,
    };
  }, [assignments]);

  return (
    <div className="progress-panel workspace-panel">
      <div className="progress-panel__body">
        {!currentUsername ? (
          <section className="progress-section">
            <div className="progress-plan-card">
              <p className="progress-plan-card__headline">Sign in to view your assignments.</p>
            </div>
          </section>
        ) : (
          <>
            {!isStudentRole && !isMentorRole ? (
              <section className="progress-section">
                <div className="progress-plan-card">
                  <p className="progress-plan-card__headline">
                    This workspace is focused on student and guardian assignment tracking.
                  </p>
                </div>
              </section>
            ) : null}

            {isMentorRole ? (
              <section className="progress-section">
                <div className="progress-plan-card">
                  <div className="progress-plan-item__top">
                    <div className="progress-plan-item__title">
                      {activeStudentDetails?.first_name
                        ? `Viewing assignments for ${activeStudentDetails.first_name}`
                        : activeStudent
                          ? `Viewing assignments for ${activeStudent}`
                          : 'No linked learner selected'}
                    </div>
                    <span className="progress-pill progress-pill--neutral">
                      {linkedStudents.length} linked learner{linkedStudents.length === 1 ? '' : 's'}
                    </span>
                  </div>
                  {linkedStudents.length > 0 ? (
                    <div className="progress-toolbar__controls assignments-toolbar__controls assignments-toolbar__controls--compact">
                      <label className="progress-toolbar__field progress-toolbar__field--wide">
                        <span>Linked student</span>
                        <div className="workspace-select-wrap workspace-select-wrap--compact">
                          <select
                            aria-label="Select linked student"
                            value={activeStudent}
                            onChange={(event) => setSelectedStudent(event.target.value)}
                          >
                            {linkedStudents.map((item) => (
                              <option key={item.username} value={item.username}>
                                {item.first_name || item.email || item.username}
                              </option>
                            ))}
                          </select>
                        </div>
                      </label>
                    </div>
                  ) : (
                    <p className="sidebar-note">Link a student in the Role Hub to review assignments here.</p>
                  )}
                </div>
              </section>
            ) : null}

            {error ? (
              <section className="progress-section">
                <div className="progress-panel__error">
                  <p>{error}</p>
                  <button type="button" className="secondary-button" onClick={isMentorRole ? loadLinkedStudents : loadAssignments}>Retry</button>
                </div>
              </section>
            ) : null}

            {(isStudentRole || activeStudent) ? (
              <>
                <section className="progress-section">
                  <div className="progress-toolbar-card assignments-toolbar-card">
                    <div className="progress-toolbar-card__header">
                      <div>
                        <div className="progress-plan-item__title">Assignment filters</div>
                        <p className="progress-toolbar-card__copy">
                          Search by topic, focus on urgent work, and sort what needs attention first.
                        </p>
                      </div>
                      <span className="progress-pill progress-pill--neutral">{visibleAssignments.length} shown</span>
                    </div>
                    <div className="progress-toolbar__controls assignments-toolbar__controls">
                      <label className="progress-toolbar__field progress-toolbar__field--wide">
                        <span>Search assignments</span>
                        <input
                          className="progress-toolbar__input"
                          type="text"
                          aria-label="Search assignments"
                          placeholder="Search assignments"
                          value={assignmentSearch}
                          onChange={(event) => setAssignmentSearch(event.target.value)}
                        />
                      </label>
                      <label className="progress-toolbar__field">
                        <span>Assignment filter</span>
                        <div className="workspace-select-wrap workspace-select-wrap--compact">
                          <select
                            aria-label="Assignment filter"
                            value={assignmentFilter}
                            onChange={(event) => setAssignmentFilter(event.target.value)}
                          >
                            <option value="all">All</option>
                            <option value="open">Open</option>
                            <option value="overdue">Overdue</option>
                            <option value="due-soon">Due soon</option>
                            <option value="completed">Completed</option>
                            <option value="dismissed">Dismissed</option>
                          </select>
                        </div>
                      </label>
                      <label className="progress-toolbar__field">
                        <span>Assignment sort</span>
                        <div className="workspace-select-wrap workspace-select-wrap--compact">
                          <select
                            aria-label="Assignment sort"
                            value={assignmentSort}
                            onChange={(event) => setAssignmentSort(event.target.value)}
                          >
                            <option value="priority">Priority</option>
                            <option value="due-date">Due date</option>
                            <option value="title">Title</option>
                          </select>
                        </div>
                      </label>
                      <div className="progress-toolbar__actions">
                        <button
                          type="button"
                          className="icon-button icon-button--ghost"
                          onClick={isMentorRole ? loadLinkedStudents : loadAssignments}
                          title="Refresh assignments"
                          aria-label="Refresh assignments"
                          disabled={loading}
                        >
                          <FiRefreshCw className={loading ? "spin" : ""} />
                        </button>
                      </div>
                    </div>
                  </div>
                </section>

                <section className="progress-stats-grid assignments-summary-grid">
                  <div className="progress-stat-card">
                    <div className="progress-stat-card__icon"><FiBookOpen /></div>
                    <div className="progress-stat-card__body">
                      <div className="progress-stat-card__value">{assignmentSummary.open}</div>
                      <div className="progress-stat-card__label">Open</div>
                      <div className="progress-stat-card__sub">Assignments to finish</div>
                    </div>
                  </div>
                  <div className="progress-stat-card">
                    <div className="progress-stat-card__icon"><FiClock /></div>
                    <div className="progress-stat-card__body">
                      <div className="progress-stat-card__value">{assignmentSummary.dueSoon + assignmentSummary.overdue}</div>
                      <div className="progress-stat-card__label">Time-sensitive</div>
                      <div className="progress-stat-card__sub">
                        {assignmentSummary.overdue > 0 ? `${assignmentSummary.overdue} overdue` : `${assignmentSummary.dueSoon} due soon`}
                      </div>
                    </div>
                  </div>
                  <div className="progress-stat-card">
                    <div className="progress-stat-card__icon"><FiCheckCircle /></div>
                    <div className="progress-stat-card__body">
                      <div className="progress-stat-card__value">{assignmentSummary.completed}</div>
                      <div className="progress-stat-card__label">Completed</div>
                      <div className="progress-stat-card__sub">Finished and marked done</div>
                    </div>
                  </div>
                </section>

                <section className="progress-section">
                  {loading ? (
                    <div className="progress-panel__loading">
                      <FiRefreshCw className="spin" />
                      <span>Loading assignments…</span>
                    </div>
                  ) : (
                    <div className="progress-plan-list">
                      {visibleAssignments.length === 0 ? (
                        <div className="progress-plan-card assignments-empty-state">
                          <p className="progress-plan-card__headline">No assignments match the current filters.</p>
                          <p className="sidebar-note">When a teacher or parent shares a new task, it will appear here.</p>
                        </div>
                      ) : visibleAssignments.map((item) => {
                        const dueMeta = getAssignmentDueMeta(item?.due_label);
                        const assignmentTone = item?.status === "completed"
                          ? "low"
                          : item?.status === "dismissed"
                            ? "neutral"
                            : dueMeta.bucket === "overdue"
                              ? "high"
                              : "medium";
                        const assignmentLabel = item?.status === "completed"
                          ? "Done"
                          : item?.status === "dismissed"
                            ? "Dismissed"
                            : "Assigned";

                        return (
                          <div key={item.id || item.title} className="progress-plan-item">
                            <div className="progress-plan-item__top">
                              <div className="progress-plan-item__title">{item.title}</div>
                              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                <span className={`progress-pill progress-pill--${assignmentTone}`}>
                                  {assignmentLabel}
                                </span>
                                {dueMeta.label ? (
                                  <span className={`progress-pill progress-pill--${dueMeta.tone}`}>
                                    {dueMeta.label}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                            <div className="progress-plan-item__description">{item.description}</div>
                            <div className="progress-plan-item__meta">
                              {`Assigned by ${item.author_role || "mentor"}${item.due_label ? ` · Due ${item.due_label}` : ""}`}
                            </div>
                            {item.cta_label ? (
                              <button
                                type="button"
                                className="secondary-button progress-plan-item__action"
                                onClick={() => onPlanAction?.(item)}
                                disabled={!onPlanAction}
                              >
                                {item.cta_label}
                              </button>
                            ) : null}
                            <button
                              type="button"
                              className="secondary-button progress-plan-item__action"
                              onClick={() => handleAssignmentStatusUpdate(item, item.status === "completed" ? "assigned" : "completed")}
                              disabled={savingItemKey === `assignment:${item.id}`}
                            >
                              {isStudentRole
                                ? item.status === "completed" ? "Undo" : "Mark Done"
                                : item.status === "completed" ? "Reopen" : "Mark Completed"}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </section>
              </>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
