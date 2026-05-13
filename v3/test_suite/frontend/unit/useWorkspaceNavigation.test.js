import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import {
  useWorkspaceNavigation,
  getWorkspacePanelMeta,
  getAvailablePanels,
} from "../hooks/useWorkspaceNavigation";

// Wrapper component for testing the hook
function TestComponent() {
  const { activePanel, setActivePanel, getPanelState, navigateTo } =
    useWorkspaceNavigation("chat");

  const state = getPanelState();

  return (
    <div>
      <div data-testid="active-panel">{activePanel}</div>
      <div data-testid="is-chat">{state.isActive("chat") ? "active" : "inactive"}</div>
      <button onClick={() => setActivePanel("progress")}>Set Progress</button>
      <button onClick={() => navigateTo("lessons")}>Navigate Lessons</button>
    </div>
  );
}

describe("useWorkspaceNavigation", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test("initializes with default panel", () => {
    render(<TestComponent />);
    const activePanel = screen.getByTestId("active-panel");
    expect(activePanel).toHaveTextContent("chat");
  });

  test("loads panel from localStorage if available", () => {
    localStorage.setItem("workspace_active_panel", "progress");
    render(<TestComponent />);
    const activePanel = screen.getByTestId("active-panel");
    expect(activePanel).toHaveTextContent("progress");
  });

  test("ignores invalid panel names in localStorage", () => {
    localStorage.setItem("workspace_active_panel", "invalid-panel-123");
    render(<TestComponent />);
    const activePanel = screen.getByTestId("active-panel");
    expect(activePanel).toHaveTextContent("chat"); // Falls back to default
  });

  test("persists panel state to localStorage when changed", async () => {
    render(<TestComponent />);
    const setProgressBtn = screen.getByText("Set Progress");

    fireEvent.click(setProgressBtn);

    await waitFor(() => {
      expect(localStorage.getItem("workspace_active_panel")).toBe("progress");
    });
  });

  test("updates active panel when setActivePanel is called", async () => {
    render(<TestComponent />);
    const activePanel = screen.getByTestId("active-panel");
    const setProgressBtn = screen.getByText("Set Progress");

    expect(activePanel).toHaveTextContent("chat");

    fireEvent.click(setProgressBtn);

    await waitFor(() => {
      expect(activePanel).toHaveTextContent("progress");
    });
  });

  test("navigateTo works as alias for setActivePanel", async () => {
    render(<TestComponent />);
    const activePanel = screen.getByTestId("active-panel");
    const navigateLessonsBtn = screen.getByText("Navigate Lessons");

    fireEvent.click(navigateLessonsBtn);

    await waitFor(() => {
      expect(activePanel).toHaveTextContent("lessons");
    });
  });

  test("getPanelState returns correct active state", async () => {
    render(<TestComponent />);
    const isChatDisplay = screen.getByTestId("is-chat");

    expect(isChatDisplay).toHaveTextContent("active");

    const setProgressBtn = screen.getByText("Set Progress");
    fireEvent.click(setProgressBtn);

    await waitFor(() => {
      expect(isChatDisplay).toHaveTextContent("inactive");
    });
  });
});

describe("getWorkspacePanelMeta", () => {
  test("returns correct metadata for chat panel", () => {
    const meta = getWorkspacePanelMeta("chat");
    expect(meta).toHaveProperty("name", "chat");
    expect(meta).toHaveProperty("title", "Chat");
    expect(meta).toHaveProperty("icon");
    expect(meta).toHaveProperty("description");
  });

  test("returns different roleHub title for teachers", () => {
    const studentMeta = getWorkspacePanelMeta("roleHub", "student");
    const teacherMeta = getWorkspacePanelMeta("roleHub", "teacher");

    expect(studentMeta.title).toBe("Role Hub");
    expect(teacherMeta.title).toBe("Teacher Hub");
  });

  test("returns different roleHub title for parents", () => {
    const parentMeta = getWorkspacePanelMeta("roleHub", "parent");
    expect(parentMeta.title).toBe("Family Hub");
  });

  test("returns default for unknown panel", () => {
    const meta = getWorkspacePanelMeta("unknown-panel");
    expect(meta).toHaveProperty("name", "chat"); // Falls back to chat
  });

  test("normalizes role names (handles 'user' role)", () => {
    const meta = getWorkspacePanelMeta("progress", "user");
    expect(meta).toHaveProperty("name", "progress");
  });
});

describe("getAvailablePanels", () => {
  test("returns basic panels for student role", () => {
    const panels = getAvailablePanels("student");
    expect(panels).toContain("chat");
    expect(panels).toContain("progress");
    expect(panels).toContain("lessons");
    expect(panels).toContain("quizzes");
    expect(panels).toContain("flashcards");
    expect(panels).toContain("notes");
    expect(panels).not.toContain("roleHub");
    expect(panels).not.toContain("admin");
  });

  test("includes roleHub and assignments for teacher role", () => {
    const panels = getAvailablePanels("teacher");
    expect(panels).toContain("roleHub");
    expect(panels).toContain("assignments");
    expect(panels).toContain("billing");
  });

  test("includes roleHub and assignments for parent role", () => {
    const panels = getAvailablePanels("parent");
    expect(panels).toContain("roleHub");
    expect(panels).toContain("assignments");
    expect(panels).toContain("billing");
  });

  test("includes admin panel for admin role", () => {
    const panels = getAvailablePanels("admin");
    expect(panels).toContain("admin");
    expect(panels).toContain("roleHub");
    expect(panels).toContain("assignments");
    expect(panels).toContain("billing");
  });

  test("handles default role when undefined", () => {
    const panels = getAvailablePanels();
    expect(Array.isArray(panels)).toBe(true);
    expect(panels.length).toBeGreaterThan(0);
  });

  test("normalizes 'user' role to 'student' panels", () => {
    const userPanels = getAvailablePanels("user");
    const studentPanels = getAvailablePanels("student");
    expect(userPanels).toEqual(studentPanels);
  });
});
