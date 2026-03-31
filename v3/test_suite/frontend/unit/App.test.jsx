import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import App from "../../../frontend/src/App";

vi.mock("../../../frontend/src/components/ChatPanel", () => ({
  default: () => <div>Workspace Ready</div>,
}));

vi.mock("../../../frontend/src/components/Login", () => ({
  default: () => <div>Login Screen</div>,
}));

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: vi.fn().mockResolvedValue({ detail: "Unauthorized" }),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders app title", async () => {
    render(<App />);
    expect(screen.getByText(/Brain Teaser/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Login Screen")).toBeInTheDocument();
    });
  });

  it("renders workspace after successful session bootstrap", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({
        authenticated: true,
        username: "student",
        role: "student",
      }),
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Workspace Ready")).toBeInTheDocument();
    });
    expect(localStorage.getItem("username")).toBe("student");
    expect(localStorage.getItem("role")).toBe("student");
  });
});
