import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import App from "../../../frontend/src/App";

vi.mock("../../../frontend/src/components/ChatPanel", () => ({
  default: ({ externalTabRequest }) => (
    <div>{`Workspace Ready${externalTabRequest?.tab ? ` · ${externalTabRequest.tab}` : ""}`}</div>
  ),
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
    expect(screen.getByText(/Academy/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Login Screen")).toBeInTheDocument();
    });
  });

  it("provides a skip link and accessible main landmark", async () => {
    render(<App />);

    expect(screen.getByRole("link", { name: /skip to main content/i })).toBeInTheDocument();
    expect(screen.getByRole("main", { name: /application content/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /skip to main content/i })).toHaveAttribute("href", "#main-content");

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

  it("shows profile, billing, workspace status, logout, and tightness controls in the header account menu", async () => {
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

    expect(screen.queryByRole("group", { name: /ui tightness/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/^online$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/backend:/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /open account menu/i }));

    expect(screen.getByText(/workspace status/i)).toBeInTheDocument();
    expect(screen.getByText(/backend:/i)).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /^profile$/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /^billing$/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /^logout$/i })).toBeInTheDocument();
    expect(screen.getByText(/display density/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "90%" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "90%" }));
    expect(localStorage.getItem("ui_density")).toBe("90");

    fireEvent.click(screen.getByRole("menuitem", { name: /^billing$/i }));
    expect(await screen.findByText("Workspace Ready · billing")).toBeInTheDocument();
  });
});
