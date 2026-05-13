/**
 * Shared assignment utilities for date, filter, and sort logic
 * Used by ProgressPanel, RoleHubPanel, and AssignmentsPanel
 */

/**
 * Parse a due date value string into a Date object
 * Handles ISO date strings and full datetime ISO strings
 */
export function parseDueDateValue(value) {
  const rawValue = String(value || "").trim();
  if (!rawValue) return null;
  
  // If it's just a date (YYYY-MM-DD), add time component
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(rawValue) 
    ? `${rawValue}T00:00:00` 
    : rawValue;
  
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/**
 * Get assignment due date metadata
 * Returns label, tone, bucket (for grouping), and sortTime
 */
export function getAssignmentDueMeta(dueLabel) {
  if (!dueLabel) {
    return { 
      label: "", 
      tone: "neutral", 
      bucket: "none", 
      sortTime: Number.MAX_SAFE_INTEGER 
    };
  }

  const parsed = parseDueDateValue(dueLabel);
  if (!parsed) {
    return { 
      label: "Scheduled", 
      tone: "neutral", 
      bucket: "scheduled", 
      sortTime: Number.MAX_SAFE_INTEGER - 1 
    };
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  const dueDate = new Date(parsed);
  dueDate.setHours(0, 0, 0, 0);
  
  const diffDays = Math.round((dueDate.getTime() - today.getTime()) / 86400000);

  if (diffDays < 0) {
    return { 
      label: "Overdue", 
      tone: "high", 
      bucket: "overdue", 
      sortTime: dueDate.getTime() 
    };
  }
  
  if (diffDays <= 3) {
    return { 
      label: "Due soon", 
      tone: "medium", 
      bucket: "due-soon", 
      sortTime: dueDate.getTime() 
    };
  }
  
  return { 
    label: "Scheduled", 
    tone: "low", 
    bucket: "scheduled", 
    sortTime: dueDate.getTime() 
  };
}

/**
 * Check if an assignment matches a given filter
 * Filters: 'all', 'open', 'completed', 'dismissed', 'overdue', 'due-soon'
 */
export function matchesAssignmentFilter(item, filterValue = "all") {
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

/**
 * Check if an assignment matches a search query
 * Searches title, description, chapter_hint, and due_label
 */
export function matchesAssignmentSearch(item, query = "") {
  const searchValue = String(query || "").trim().toLowerCase();
  if (!searchValue) return true;
  
  const haystack = [
    item?.title,
    item?.description,
    item?.chapter_hint,
    item?.due_label,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  
  return haystack.includes(searchValue);
}

/**
 * Compare two assignments by priority
 * Used for sorting: overdue > due-soon > scheduled
 */
export function compareAssignmentsByPriority(left, right) {
  const leftDueMeta = getAssignmentDueMeta(left?.due_label);
  const rightDueMeta = getAssignmentDueMeta(right?.due_label);
  
  // Bucket priority: overdue=0, due-soon=1, scheduled=2
  const leftRank = 
    leftDueMeta.bucket === "overdue" 
      ? 0 
      : leftDueMeta.bucket === "due-soon" 
        ? 1 
        : 2;
  
  const rightRank = 
    rightDueMeta.bucket === "overdue" 
      ? 0 
      : rightDueMeta.bucket === "due-soon" 
        ? 1 
        : 2;

  if (leftRank !== rightRank) return leftRank - rightRank;
  if (leftDueMeta.sortTime !== rightDueMeta.sortTime) {
    return leftDueMeta.sortTime - rightDueMeta.sortTime;
  }
  return String(left?.title || "").localeCompare(String(right?.title || ""));
}

/**
 * Sort assignments based on different modes
 * Modes: 'priority' (default), 'title', 'due-date'
 */
export function sortAssignmentsForMode(items, sortMode = "priority") {
  const list = [...(items || [])];
  
  if (sortMode === "title") {
    return list.sort((left, right) =>
      String(left?.title || "").localeCompare(String(right?.title || ""))
    );
  }
  
  if (sortMode === "due-date") {
    return list.sort(
      (left, right) =>
        getAssignmentDueMeta(left?.due_label).sortTime -
        getAssignmentDueMeta(right?.due_label).sortTime
    );
  }
  
  return list.sort(compareAssignmentsByPriority);
}

/**
 * Filter assignments based on multiple criteria
 * Returns filtered list based on status, due date, and search
 */
export function filterAssignments(items, options = {}) {
  const { 
    filterValue = "all", 
    searchQuery = "", 
    includeCompleted = false 
  } = options;

  let filtered = [...(items || [])];

  // Apply search filter
  if (searchQuery) {
    filtered = filtered.filter((item) =>
      matchesAssignmentSearch(item, searchQuery)
    );
  }

  // Apply status filter
  filtered = filtered.filter((item) =>
    matchesAssignmentFilter(item, filterValue)
  );

  // If excluding completed, filter them out
  if (!includeCompleted) {
    filtered = filtered.filter((item) => item?.status !== "completed");
  }

  return filtered;
}

/**
 * Apply comprehensive assignment transformations
 * Filters, sorts, and returns processed assignment list
 */
export function processAssignmentList(items, options = {}) {
  const {
    filterValue = "all",
    sortMode = "priority",
    searchQuery = "",
    includeCompleted = false,
  } = options;

  // First filter
  let processed = filterAssignments(items, {
    filterValue,
    searchQuery,
    includeCompleted,
  });

  // Then sort
  processed = sortAssignmentsForMode(processed, sortMode);

  return processed;
}

/**
 * Get all unique chapters from a list of assignments
 * Useful for building chapter filter dropdowns
 */
export function getUniqueChaptersFromAssignments(items) {
  const chapters = new Set();
  (items || []).forEach((item) => {
    if (item?.chapter_hint) {
      chapters.add(item.chapter_hint);
    }
  });
  return Array.from(chapters).sort();
}

/**
 * Group assignments by due date bucket
 * Returns object with keys: 'overdue', 'due-soon', 'scheduled', 'none'
 */
export function groupAssignmentsByDueBucket(items) {
  const groups = {
    overdue: [],
    "due-soon": [],
    scheduled: [],
    none: [],
  };

  (items || []).forEach((item) => {
    const meta = getAssignmentDueMeta(item?.due_label);
    const bucket = meta.bucket || "none";
    if (groups[bucket]) {
      groups[bucket].push(item);
    }
  });

  return groups;
}

/**
 * Calculate summary statistics from assignment list
 * Returns counts by status and urgency
 */
export function calculateAssignmentStats(items) {
  const stats = {
    total: 0,
    assigned: 0,
    completed: 0,
    dismissed: 0,
    overdue: 0,
    dueSoon: 0,
    scheduled: 0,
  };

  (items || []).forEach((item) => {
    stats.total += 1;

    const status = String(item?.status || "assigned").toLowerCase();
    switch (status) {
      case "completed":
        stats.completed += 1;
        break;
      case "dismissed":
        stats.dismissed += 1;
        break;
      default:
        stats.assigned += 1;
    }

    const dueMeta = getAssignmentDueMeta(item?.due_label);
    switch (dueMeta.bucket) {
      case "overdue":
        stats.overdue += 1;
        break;
      case "due-soon":
        stats.dueSoon += 1;
        break;
      case "scheduled":
        stats.scheduled += 1;
        break;
    }
  });

  return stats;
}
