import { describe, expect, it } from "vitest";
import { filterSessionsByContext } from "../../../frontend/src/utils/chatPanelSelectors";

describe("chatPanelSelectors", () => {
  it("keeps active scoped session visible even if context text does not match", () => {
    const sessions = [
      { id: "s-1", title: "Old Session", chapter: "Chapter 1" },
      { id: "s-2", title: "New Session", chapter: "" },
    ];

    const filtered = filterSessionsByContext(sessions, "Chapter 1", "s-2");

    expect(filtered.map((item) => item.id)).toEqual(["s-1", "s-2"]);
  });

  it("filters by chapter or title when active id is not provided", () => {
    const sessions = [
      { id: "q-1", title: "Quiz Algebra", chapter: "Math" },
      { id: "q-2", title: "Quiz Biology", chapter: "Science" },
    ];

    const filtered = filterSessionsByContext(sessions, "math");

    expect(filtered.map((item) => item.id)).toEqual(["q-1"]);
  });
});
