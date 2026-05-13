import {
  parseDueDateValue,
  getAssignmentDueMeta,
  matchesAssignmentFilter,
  matchesAssignmentSearch,
  compareAssignmentsByPriority,
  sortAssignmentsForMode,
  filterAssignments,
  processAssignmentList,
  getUniqueChaptersFromAssignments,
  groupAssignmentsByDueBucket,
  calculateAssignmentStats,
} from "../utils/assignmentUtils";

describe("assignmentUtils", () => {
  describe("parseDueDateValue", () => {
    test("parses ISO date string", () => {
      const result = parseDueDateValue("2026-05-15");
      expect(result).toBeInstanceOf(Date);
      expect(result.getFullYear()).toBe(2026);
      expect(result.getMonth()).toBe(4); // May is month 4 (0-indexed)
      expect(result.getDate()).toBe(15);
    });

    test("parses ISO datetime string", () => {
      const result = parseDueDateValue("2026-05-15T14:30:00");
      expect(result).toBeInstanceOf(Date);
      expect(result.getHours()).toBe(14);
    });

    test("returns null for invalid date", () => {
      const result = parseDueDateValue("not-a-date");
      expect(result).toBeNull();
    });

    test("returns null for empty string", () => {
      const result = parseDueDateValue("");
      expect(result).toBeNull();
    });

    test("returns null for null/undefined", () => {
      expect(parseDueDateValue(null)).toBeNull();
      expect(parseDueDateValue(undefined)).toBeNull();
    });
  });

  describe("getAssignmentDueMeta", () => {
    test("returns neutral state for no due date", () => {
      const meta = getAssignmentDueMeta(null);
      expect(meta.bucket).toBe("none");
      expect(meta.tone).toBe("neutral");
    });

    test("marks overdue assignments", () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const dueLabel = yesterday.toISOString().split("T")[0];

      const meta = getAssignmentDueMeta(dueLabel);
      expect(meta.bucket).toBe("overdue");
      expect(meta.tone).toBe("high");
      expect(meta.label).toBe("Overdue");
    });

    test("marks due soon assignments (within 3 days)", () => {
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const dueLabel = tomorrow.toISOString().split("T")[0];

      const meta = getAssignmentDueMeta(dueLabel);
      expect(meta.bucket).toBe("due-soon");
      expect(meta.tone).toBe("medium");
      expect(meta.label).toBe("Due soon");
    });

    test("marks scheduled assignments (more than 3 days away)", () => {
      const nextWeek = new Date();
      nextWeek.setDate(nextWeek.getDate() + 7);
      const dueLabel = nextWeek.toISOString().split("T")[0];

      const meta = getAssignmentDueMeta(dueLabel);
      expect(meta.bucket).toBe("scheduled");
      expect(meta.tone).toBe("low");
      expect(meta.label).toBe("Scheduled");
    });
  });

  describe("matchesAssignmentFilter", () => {
    const openAssignment = { status: "assigned", due_label: "2026-05-20" };
    const completedAssignment = { status: "completed", due_label: "2026-05-20" };
    const dismissedAssignment = { status: "dismissed", due_label: "2026-05-20" };

    test("all filter matches everything", () => {
      expect(matchesAssignmentFilter(openAssignment, "all")).toBe(true);
      expect(matchesAssignmentFilter(completedAssignment, "all")).toBe(true);
      expect(matchesAssignmentFilter(dismissedAssignment, "all")).toBe(true);
    });

    test("open filter matches only open assignments", () => {
      expect(matchesAssignmentFilter(openAssignment, "open")).toBe(true);
      expect(matchesAssignmentFilter(completedAssignment, "open")).toBe(false);
      expect(matchesAssignmentFilter(dismissedAssignment, "open")).toBe(false);
    });

    test("completed filter matches only completed assignments", () => {
      expect(matchesAssignmentFilter(completedAssignment, "completed")).toBe(
        true
      );
      expect(matchesAssignmentFilter(openAssignment, "completed")).toBe(false);
    });

    test("overdue filter matches open overdue assignments", () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const overdueAssignment = {
        status: "assigned",
        due_label: yesterday.toISOString().split("T")[0],
      };

      expect(matchesAssignmentFilter(overdueAssignment, "overdue")).toBe(true);
      expect(matchesAssignmentFilter(openAssignment, "overdue")).toBe(false);
    });
  });

  describe("matchesAssignmentSearch", () => {
    const assignment = {
      title: "Math Homework",
      description: "Chapter 5 exercises",
      chapter_hint: "Algebra",
      due_label: "2026-05-20",
    };

    test("returns true for empty query", () => {
      expect(matchesAssignmentSearch(assignment, "")).toBe(true);
      expect(matchesAssignmentSearch(assignment, null)).toBe(true);
    });

    test("matches title", () => {
      expect(matchesAssignmentSearch(assignment, "Math")).toBe(true);
      expect(matchesAssignmentSearch(assignment, "homework")).toBe(true);
    });

    test("matches description", () => {
      expect(matchesAssignmentSearch(assignment, "Chapter 5")).toBe(true);
      expect(matchesAssignmentSearch(assignment, "exercises")).toBe(true);
    });

    test("matches chapter hint", () => {
      expect(matchesAssignmentSearch(assignment, "Algebra")).toBe(true);
    });

    test("case insensitive", () => {
      expect(matchesAssignmentSearch(assignment, "MATH")).toBe(true);
      expect(matchesAssignmentSearch(assignment, "algebra")).toBe(true);
    });

    test("returns false for non-matching query", () => {
      expect(matchesAssignmentSearch(assignment, "Physics")).toBe(false);
    });
  });

  describe("compareAssignmentsByPriority", () => {
    test("sorts by bucket priority: overdue > due-soon > scheduled", () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const nextWeek = new Date();
      nextWeek.setDate(nextWeek.getDate() + 7);

      const overdue = {
        title: "A",
        due_label: yesterday.toISOString().split("T")[0],
      };
      const dueSoon = {
        title: "B",
        due_label: tomorrow.toISOString().split("T")[0],
      };
      const scheduled = {
        title: "C",
        due_label: nextWeek.toISOString().split("T")[0],
      };

      expect(compareAssignmentsByPriority(overdue, dueSoon)).toBeLessThan(0);
      expect(compareAssignmentsByPriority(dueSoon, scheduled)).toBeLessThan(0);
    });

    test("sorts alphabetically within same bucket", () => {
      const assignment1 = { title: "Beta", due_label: "2026-05-20" };
      const assignment2 = { title: "Alpha", due_label: "2026-05-20" };

      expect(compareAssignmentsByPriority(assignment1, assignment2)).toBeGreaterThan(0);
      expect(compareAssignmentsByPriority(assignment2, assignment1)).toBeLessThan(0);
    });
  });

  describe("sortAssignmentsForMode", () => {
    const assignments = [
      { title: "Zebra Quiz", due_label: "2026-05-25" },
      { title: "Alpha Homework", due_label: "2026-05-15" },
      { title: "Beta Project", due_label: "2026-05-20" },
    ];

    test("sorts by priority by default", () => {
      const sorted = sortAssignmentsForMode(assignments);
      expect(sorted[0].title).toBe("Alpha Homework"); // Earliest date
      expect(sorted[2].title).toBe("Zebra Quiz"); // Latest date
    });

    test("sorts by title", () => {
      const sorted = sortAssignmentsForMode(assignments, "title");
      expect(sorted[0].title).toBe("Alpha Homework");
      expect(sorted[1].title).toBe("Beta Project");
      expect(sorted[2].title).toBe("Zebra Quiz");
    });

    test("sorts by due date", () => {
      const sorted = sortAssignmentsForMode(assignments, "due-date");
      expect(sorted[0].due_label).toBe("2026-05-15");
      expect(sorted[1].due_label).toBe("2026-05-20");
      expect(sorted[2].due_label).toBe("2026-05-25");
    });
  });

  describe("filterAssignments", () => {
    const assignments = [
      { title: "Open 1", status: "assigned", due_label: "2026-05-20" },
      { title: "Done 1", status: "completed", due_label: "2026-05-20" },
      { title: "Open 2", status: "assigned", due_label: "2026-05-25" },
    ];

    test("filters by status", () => {
      const filtered = filterAssignments(assignments, { filterValue: "open" });
      expect(filtered.length).toBe(2);
      expect(filtered.every((a) => a.status === "assigned")).toBe(true);
    });

    test("filters by search", () => {
      const filtered = filterAssignments(assignments, { searchQuery: "Done" });
      expect(filtered.length).toBe(1);
      expect(filtered[0].title).toBe("Done 1");
    });

    test("excludes completed by default", () => {
      const filtered = filterAssignments(assignments, { includeCompleted: false });
      expect(filtered.every((a) => a.status !== "completed")).toBe(true);
    });

    test("includes completed when specified", () => {
      const filtered = filterAssignments(assignments, { includeCompleted: true });
      expect(filtered.some((a) => a.status === "completed")).toBe(true);
    });
  });

  describe("getUniqueChaptersFromAssignments", () => {
    test("extracts unique chapters", () => {
      const assignments = [
        { title: "A", chapter_hint: "Math" },
        { title: "B", chapter_hint: "Science" },
        { title: "C", chapter_hint: "Math" },
      ];

      const chapters = getUniqueChaptersFromAssignments(assignments);
      expect(chapters).toContain("Math");
      expect(chapters).toContain("Science");
      expect(chapters.length).toBe(2);
    });

    test("returns sorted array", () => {
      const assignments = [
        { title: "A", chapter_hint: "Zebra" },
        { title: "B", chapter_hint: "Apple" },
      ];

      const chapters = getUniqueChaptersFromAssignments(assignments);
      expect(chapters[0]).toBe("Apple");
      expect(chapters[1]).toBe("Zebra");
    });

    test("handles missing chapters", () => {
      const assignments = [
        { title: "A", chapter_hint: "Math" },
        { title: "B" }, // No chapter_hint
      ];

      const chapters = getUniqueChaptersFromAssignments(assignments);
      expect(chapters).toEqual(["Math"]);
    });
  });

  describe("groupAssignmentsByDueBucket", () => {
    test("groups assignments by due bucket", () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const nextWeek = new Date();
      nextWeek.setDate(nextWeek.getDate() + 7);

      const assignments = [
        { title: "Overdue", due_label: yesterday.toISOString().split("T")[0] },
        { title: "Due Soon", due_label: tomorrow.toISOString().split("T")[0] },
        { title: "Scheduled", due_label: nextWeek.toISOString().split("T")[0] },
        { title: "No Date", due_label: null },
      ];

      const groups = groupAssignmentsByDueBucket(assignments);
      expect(groups.overdue.length).toBe(1);
      expect(groups["due-soon"].length).toBe(1);
      expect(groups.scheduled.length).toBe(1);
      expect(groups.none.length).toBe(1);
    });
  });

  describe("calculateAssignmentStats", () => {
    test("calculates stats correctly", () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);

      const assignments = [
        { status: "assigned", due_label: tomorrow.toISOString().split("T")[0] },
        { status: "completed", due_label: "2026-05-20" },
        { status: "assigned", due_label: yesterday.toISOString().split("T")[0] },
        { status: "dismissed", due_label: "2026-05-20" },
      ];

      const stats = calculateAssignmentStats(assignments);
      expect(stats.total).toBe(4);
      expect(stats.assigned).toBe(2);
      expect(stats.completed).toBe(1);
      expect(stats.dismissed).toBe(1);
      expect(stats.overdue).toBe(1);
      expect(stats.dueSoon).toBe(1);
    });
  });

  describe("processAssignmentList", () => {
    test("applies filter, search, and sort", () => {
      const assignments = [
        { title: "Math Open", status: "assigned", due_label: "2026-05-25" },
        { title: "Science Done", status: "completed", due_label: "2026-05-20" },
        { title: "English Open", status: "assigned", due_label: "2026-05-15" },
      ];

      const processed = processAssignmentList(assignments, {
        filterValue: "open",
        searchQuery: "Open",
        sortMode: "due-date",
      });

      expect(processed.length).toBe(2);
      expect(processed[0].title).toBe("English Open");
      expect(processed[1].title).toBe("Math Open");
    });
  });
});
