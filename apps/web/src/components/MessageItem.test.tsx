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

  it("renders assistant Markdown while escaping raw HTML", async () => {
    const { container } = render(
      <MessageItem
        message={{
          ...message,
          content: "**Grounded result** <script>unsafe()</script>",
        }}
      />,
    );

    expect((await screen.findByText("Grounded result")).tagName).toBe("STRONG");
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText(/<script>unsafe\(\)<\/script>/)).toBeInTheDocument();
  });

  it("shows a streaming placeholder without exposing partial reasoning", () => {
    render(<MessageItem message={{ ...message, content: "<think>partial" }} isStreaming />);
    const status = screen.getByRole("status", { name: "Generating response" });
    expect(status.querySelectorAll(".thinking-dots > span")).toHaveLength(3);
    expect(screen.queryByText("partial")).not.toBeInTheDocument();
  });

  it("keeps tool progress accessible while using the same thinking indicator", () => {
    render(<MessageItem message={{ ...message, content: "" }} isStreaming runLabel="Calling get_production_summary" />);
    const status = screen.getByRole("status", { name: "Calling get_production_summary" });
    expect(status.querySelectorAll(".thinking-dots > span")).toHaveLength(3);
  });

  it("renders deterministic production evidence", () => {
    render(<MessageItem message={message} evidence={{ production_summary: { equipment_id: "AOI-WAFER-01", lot_id: null, start: "2026-01-15T13:00:00Z", end: "2026-01-15T17:00:00Z", inspected_wafers: 300, passed_wafers: 257, failed_wafers: 43, yield_rate: 257 / 300, defect_counts: [], alarm_events: [], limitations: [] }, tool_error: null }} />);
    expect(screen.getByText("Production summary")).toBeInTheDocument();
    expect(screen.getByText("85.67%")).toBeInTheDocument();
    expect(screen.getByText("Deterministic")).toBeInTheDocument();
  });

  it("renders deterministic equipment-status evidence", () => {
    render(
      <MessageItem
        message={message}
        evidence={{
          production_summary: null,
          equipment_status: {
            equipment_id: "AOI-WAFER-01",
            observed_at: "2026-01-15T17:00:00Z",
            status: "running",
            effective_start: "2026-01-15T16:00:00Z",
            effective_end: "2026-01-15T18:00:00Z",
            source_event_id: "state-003",
            reason_code: "SYNTHETIC-SCHEDULED-RUN",
            limitations: [],
          },
          tool_error: null,
        }}
      />,
    );

    expect(screen.getByText("Equipment status")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("SYNTHETIC-SCHEDULED-RUN")).toBeInTheDocument();
    expect(screen.getByText("Deterministic")).toBeInTheDocument();
    expect(screen.getByText("Synthetic Demo")).toBeInTheDocument();
  });

  it("renders unknown equipment status with its explicit limitation", () => {
    render(
      <MessageItem
        message={message}
        evidence={{
          production_summary: null,
          equipment_status: {
            equipment_id: "AOI-WAFER-01",
            observed_at: "2026-01-15T19:00:00Z",
            status: "unknown",
            effective_start: null,
            effective_end: null,
            source_event_id: null,
            reason_code: null,
            limitations: ["no_recorded_equipment_state"],
          },
          tool_error: null,
        }}
      />,
    );

    expect(screen.getByText("unknown")).toBeInTheDocument();
    expect(screen.getByText("no_recorded_equipment_state")).toBeInTheDocument();
    expect(screen.getAllByText("Unavailable")).toHaveLength(2);
  });

  it("renders ranked defect-distribution evidence", () => {
    render(
      <MessageItem
        message={message}
        evidence={{
          production_summary: null,
          defect_distribution: {
            equipment_id: "AOI-WAFER-01",
            lot_id: "LOT-DEMO-001",
            start: "2026-01-15T13:00:00Z",
            end: "2026-01-15T17:00:00Z",
            failed_wafers: 30,
            classified_defect_count: 30,
            unclassified_failed_wafers: 0,
            items: [
              { category: "edge-chip", count: 19, share: 19 / 30, rank: 1 },
              { category: "scratch", count: 11, share: 11 / 30, rank: 2 },
            ],
            limitations: [],
          },
          tool_error: null,
        }}
      />,
    );

    expect(screen.getByText("Defect distribution")).toBeInTheDocument();
    expect(screen.getByText("edge-chip")).toBeInTheDocument();
    expect(screen.getByText(/63\.3%/)).toBeInTheDocument();
    expect(screen.getByText("Rank 1")).toBeInTheDocument();
    expect(screen.getByText("Synthetic Demo")).toBeInTheDocument();
  });

  it("renders an empty defect distribution with its limitation", () => {
    render(
      <MessageItem
        message={message}
        evidence={{
          production_summary: null,
          defect_distribution: {
            equipment_id: "AOI-WAFER-01",
            lot_id: null,
            start: "2026-01-15T18:00:00Z",
            end: "2026-01-15T19:00:00Z",
            failed_wafers: 0,
            classified_defect_count: 0,
            unclassified_failed_wafers: 0,
            items: [],
            limitations: ["no_inspection_records"],
          },
          tool_error: null,
        }}
      />,
    );

    expect(screen.getByText("No classified defects returned.")).toBeInTheDocument();
    expect(screen.getByText("no_inspection_records")).toBeInTheDocument();
  });

  it("renders retrieved fictional source evidence", () => {
    render(
      <MessageItem
        message={message}
        evidence={{
          production_summary: null,
          document_search: {
            query: "OPTICAL-SIGNAL-LOW operator check",
            sources: [{
              source_id: "aoi-alarm-guide:002",
              title: "AOI Wafer Inspector Alarm Guide",
              section: "OPTICAL-SIGNAL-LOW",
              relative_path: "data/synthetic/documents/aoi-wafer-inspector-alarm-guide.md",
              excerpt: "Check the optical lens cover and illumination connector.",
              score: 0.72,
            }],
            limitations: [],
          },
          tool_error: null,
        }}
      />,
    );

    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("AOI Wafer Inspector Alarm Guide")).toBeInTheDocument();
    expect(screen.getByText("OPTICAL-SIGNAL-LOW")).toBeInTheDocument();
    expect(screen.getByText("72.0% match")).toBeInTheDocument();
    expect(screen.getByText("Retrieved")).toBeInTheDocument();
    expect(screen.getByText("Synthetic Demo")).toBeInTheDocument();
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
