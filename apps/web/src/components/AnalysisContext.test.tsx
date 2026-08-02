import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { WorkspaceContextState } from "../hooks/useWorkspaceContext";
import AnalysisContext from "./AnalysisContext";

const state: WorkspaceContextState = {
  context: { environment: "synthetic", device: "AOI-WAFER-01", lot: "LOT-DEMO-001", time_range: "Last 4 hours", data_source: "synthetic_demo" },
  devices: [{ id: "AOI-WAFER-01", name: "AOI Wafer Inspector 01", category: "inspection", data_source: "synthetic_demo" }],
  devicesLoading: false,
  devicesError: null,
  isLoading: false,
  isSaving: false,
  error: null,
  reload: vi.fn(),
  save: vi.fn().mockResolvedValue(true),
};

describe("AnalysisContext", () => {
  it("edits only supported context presets and saves a dirty draft", async () => {
    const user = userEvent.setup();
    render(<AnalysisContext state={state} disabled={false} />);

    expect(screen.queryByText("Custom")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save context" })).toBeDisabled();

    const lot = screen.getByPlaceholderText("Optional lot identifier");
    await user.clear(lot);
    await user.type(lot, "LOT-NEW-002");
    expect(screen.getByRole("button", { name: "Save context" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Save context" }));

    expect(state.save).toHaveBeenCalledWith({ device: "AOI-WAFER-01", lot: "LOT-NEW-002", time_range: "Last 4 hours" });
  });

  it("rejects lot identifiers longer than 200 characters", async () => {
    const user = userEvent.setup();
    render(<AnalysisContext state={{ ...state, save: vi.fn() }} disabled={false} />);
    const lot = screen.getByPlaceholderText("Optional lot identifier");
    await user.clear(lot);
    await user.type(lot, "L".repeat(201));
    await user.click(screen.getByRole("button", { name: "Save context" }));
    expect(screen.getByText("Lot must be 200 characters or fewer.")).toBeInTheDocument();
  });
});
