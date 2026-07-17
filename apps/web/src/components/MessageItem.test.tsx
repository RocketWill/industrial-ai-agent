import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Message } from "../api/messages";
import MessageItem from "./MessageItem";

const message: Message = {
  id: "11111111-1111-1111-8111-111111111111",
  conversation_id: "11111111-1111-1111-8111-111111111111",
  role: "assistant",
  content: "<think>private</think>Visible answer",
  created_at: "2026-07-30T00:00:00Z",
};

describe("MessageItem", () => {
  it("does not render internal reasoning text", () => {
    render(<MessageItem message={message} />);
    expect(screen.getByText("Visible answer")).toBeInTheDocument();
    expect(screen.queryByText("private")).not.toBeInTheDocument();
  });

  it("shows a streaming placeholder without exposing partial reasoning", () => {
    render(<MessageItem message={{ ...message, content: "<think>partial" }} isStreaming />);
    expect(screen.getByText("Generating response…")).toBeInTheDocument();
    expect(screen.queryByText("partial")).not.toBeInTheDocument();
  });

  it("renders deterministic production evidence", () => {
    render(<MessageItem message={message} evidence={{ production_summary: { equipment_id: "AOI-WAFER-01", lot_id: null, start: "2026-01-15T13:00:00Z", end: "2026-01-15T17:00:00Z", inspected_wafers: 300, passed_wafers: 257, failed_wafers: 43, yield_rate: 257 / 300, defect_counts: [], alarm_events: [], limitations: [] }, tool_error: null }} />);
    expect(screen.getByText("Production summary")).toBeInTheDocument();
    expect(screen.getByText("85.67%")).toBeInTheDocument();
    expect(screen.getByText("Deterministic")).toBeInTheDocument();
  });

  it("renders production defects, alarms, and explicit empty states", () => {
    const summary = {
      equipment_id: "AOI-WAFER-01", lot_id: "LOT-DEMO-001", start: "2026-01-15T13:00:00Z", end: "2026-01-15T17:00:00Z",
      inspected_wafers: 400, passed_wafers: 370, failed_wafers: 30, yield_rate: 0.925,
      defect_counts: [{ category: "edge-chip", count: 19 }],
      alarm_events: [{ event_id: "alarm-001", code: "OPTICAL-SIGNAL-LOW", started_at: "2026-01-15T15:00:00Z", ended_at: "2026-01-15T16:00:00Z" }],
      limitations: [],
    };
    const { rerender } = render(<MessageItem message={message} evidence={{ production_summary: summary, tool_error: null }} />);

    expect(screen.getByRole("heading", { name: "Defect counts" })).toBeInTheDocument();
    expect(screen.getByText("edge-chip")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Alarm events" })).toBeInTheDocument();
    expect(screen.getByText("OPTICAL-SIGNAL-LOW")).toBeInTheDocument();
    expect(screen.getByText("Synthetic Demo")).toBeInTheDocument();

    rerender(<MessageItem message={message} evidence={{ production_summary: { ...summary, defect_counts: [], alarm_events: [] }, tool_error: null }} />);
    expect(screen.getByText("No defect counts returned.")).toBeInTheDocument();
    expect(screen.getByText("No alarm events returned.")).toBeInTheDocument();
  });
});
