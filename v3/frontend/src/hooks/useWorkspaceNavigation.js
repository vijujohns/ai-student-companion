import { useCallback, useEffect, useState } from "react";

/**
 * Hook for managing workspace navigation state
 * Handles active panel state, persistence, and navigation actions
 */
export function useWorkspaceNavigation(defaultPanel = "chat") {
  const [activePanel, setActivePanel] = useState(() => {
    // Load from localStorage if available
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("workspace_active_panel");
      if (stored && isValidPanel(stored)) {
        return stored;
      }
    }
    return defaultPanel;
  });

  // Persist to localStorage whenever active panel changes
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("workspace_active_panel", activePanel);
    }
  }, [activePanel]);

  const setPanel = useCallback((panelName) => {
    if (isValidPanel(panelName)) {
      setActivePanel(panelName);
    }
  }, []);

  const getPanelState = useCallback(() => {
    return {
      activePanel,
      isActive: (name) => activePanel === name,
    };
  }, [activePanel]);

  return {
    activePanel,
    setActivePanel: setPanel,
    getPanelState,
    navigateTo: setPanel,
  };
}

/**
 * Validate panel name against allowed panels
 */
function isValidPanel(panelName) {
  const validPanels = [
    "chat",
    "progress",
    "roleHub",
    "lessons",
    "quizzes",
    "flashcards",
    "assessments",
    "assignments",
    "notes",
    "billing",
    "admin",
  ];
  return validPanels.includes(String(panelName || "").toLowerCase());
}

/**
 * Get metadata for a workspace panel
 */
export function getWorkspacePanelMeta(panelName, userRole = "student") {
  const normalizedRole = String(userRole || "student").toLowerCase() === "user"
    ? "student"
    : String(userRole || "student").toLowerCase();

  const panels = {
    chat: {
      name: "chat",
      title: "Chat",
      icon: "message-square",
      description: "Ask AI tutor for help",
    },
    progress: {
      name: "progress",
      title: "Progress",
      icon: "bar-chart-2",
      description: "View learning progress and mastery",
    },
    roleHub: {
      name: "roleHub",
      title: normalizedRole === "teacher"
        ? "Teacher Hub"
        : normalizedRole === "parent"
          ? "Family Hub"
          : "Role Hub",
      icon: "users",
      description: "Manage linked learners and assignments",
    },
    lessons: {
      name: "lessons",
      title: "Lessons",
      icon: "book-open",
      description: "Browse and learn lessons",
    },
    quizzes: {
      name: "quizzes",
      title: "Quizzes",
      icon: "help-circle",
      description: "Take quizzes to test knowledge",
    },
    flashcards: {
      name: "flashcards",
      title: "Flashcards",
      icon: "layers",
      description: "Study with flashcards",
    },
    assessments: {
      name: "assessments",
      title: "Assessments",
      icon: "award",
      description: "View assessments and scores",
    },
    assignments: {
      name: "assignments",
      title: "Assignments",
      icon: "clipboard",
      description: "View and manage assignments",
    },
    notes: {
      name: "notes",
      title: "Notes",
      icon: "file-text",
      description: "Read and manage notes",
    },
    billing: {
      name: "billing",
      title: "Billing",
      icon: "credit-card",
      description: "Manage subscription and billing",
    },
    admin: {
      name: "admin",
      title: "Admin",
      icon: "shield",
      description: "Admin controls and settings",
    },
  };

  return panels[panelName] || panels.chat;
}

/**
 * Get list of available panels for a user role
 */
export function getAvailablePanels(userRole = "student") {
  const normalizedRole = String(userRole || "student").toLowerCase() === "user"
    ? "student"
    : String(userRole || "student").toLowerCase();

  const basePanels = ["chat", "progress", "lessons", "quizzes", "flashcards", "notes"];

  if (normalizedRole === "teacher" || normalizedRole === "parent") {
    basePanels.push("roleHub", "assignments");
  }

  if (normalizedRole === "admin") {
    basePanels.push("admin", "roleHub", "assignments", "billing");
  }

  if (normalizedRole !== "student") {
    basePanels.push("billing");
  }

  return basePanels;
}
