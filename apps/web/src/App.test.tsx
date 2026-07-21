import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { checkHealth } from "./api/health";
import App from "./App";

vi.mock("./api/health", async () => {
  const actual = await vi.importActual<typeof import("./api/health")>(
    "./api/health",
  );

  return {
    ...actual,
    checkHealth: vi.fn(),
  };
});

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts checking the API connection when the application loads", () => {
    vi.mocked(checkHealth).mockReturnValue(new Promise(() => undefined));

    render(<App />);

    expect(screen.getByText("Checking API connection")).toBeInTheDocument();
    expect(checkHealth).toHaveBeenCalledTimes(1);
  });

  it("shows a connected state after a valid health response", async () => {
    vi.mocked(checkHealth).mockResolvedValue({ status: "ok" });

    render(<App />);

    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(
      screen.getByText("The API process is responding."),
    ).toBeInTheDocument();
  });

  it("shows an actionable unavailable state without transport details", async () => {
    vi.mocked(checkHealth).mockRejectedValue(new Error("offline at 127.0.0.1"));

    render(<App />);

    expect(await screen.findByText("API unavailable")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Check again" }),
    ).toBeEnabled();
    expect(screen.queryByText("offline at 127.0.0.1")).not.toBeInTheDocument();
  });

  it("presents the truthful semiconductor Agent workbench shell", () => {
    vi.mocked(checkHealth).mockReturnValue(new Promise(() => undefined));

    render(<App />);

    expect(screen.getByText("Recent conversations")).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Analysis context" })).toBeInTheDocument();
    expect(screen.getAllByText("Synthetic Demo").length).toBeGreaterThan(0);
    expect(screen.queryByText("Analysis workspace")).not.toBeInTheDocument();
    expect(screen.queryByText("Production Data")).not.toBeInTheDocument();
    expect(screen.queryByText("Knowledge Base")).not.toBeInTheDocument();
    expect(screen.queryByText("Evaluations")).not.toBeInTheDocument();
  });
});
