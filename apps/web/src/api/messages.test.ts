import { describe, expect, it } from "vitest";
import { buildMessagesUrl, listMessages, sendMessage } from "./messages";

const id = "11111111-1111-1111-8111-111111111111";
const message = { id, conversation_id: id, role: "user" as const, content: "Check status", created_at: "2026-07-30T00:00:00Z" };
const assistant = { ...message, id: "22222222-2222-1222-8222-222222222222", role: "assistant" as const, content: "The status is stable." };

describe("messages API", () => {
  it("builds message URLs", () => {
    expect(buildMessagesUrl(undefined, id)).toBe(`/api/conversations/${id}/messages`);
    expect(buildMessagesUrl("https://api.example.test/", id)).toBe(`https://api.example.test/conversations/${id}/messages`);
  });

  it("loads validated history", async () => {
    const fetchImplementation = async () => new Response(JSON.stringify([message]), { status: 200 });
    await expect(listMessages(id, fetchImplementation)).resolves.toEqual([message]);
  });

  it("sends trimmed content and validates the exchange", async () => {
    const requests: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const fetchImplementation = async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ input, init });
      return new Response(JSON.stringify({ user_message: message, assistant_message: assistant, evidence: null }), { status: 201 });
    };
    await expect(sendMessage(id, "  Check status  ", fetchImplementation)).resolves.toEqual({ user_message: message, assistant_message: assistant, evidence: null });
    expect(requests[0]).toEqual({ input: `/api/conversations/${id}/messages`, init: { method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json" }, body: JSON.stringify({ content: "Check status" }) } });
  });

  it("accepts deterministic equipment-status evidence", async () => {
    const evidence = {
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
    };
    const fetchImplementation = async () => new Response(
      JSON.stringify({ user_message: message, assistant_message: assistant, evidence }),
      { status: 201 },
    );

    await expect(sendMessage(id, "Check status", fetchImplementation)).resolves.toEqual({
      user_message: message,
      assistant_message: assistant,
      evidence,
    });
  });

  it("accepts deterministic defect-distribution evidence", async () => {
    const evidence = {
      production_summary: null,
      equipment_status: null,
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
    };
    const fetchImplementation = async () => new Response(
      JSON.stringify({ user_message: message, assistant_message: assistant, evidence }),
      { status: 201 },
    );

    await expect(sendMessage(id, "Show defect distribution", fetchImplementation)).resolves.toEqual({
      user_message: message,
      assistant_message: assistant,
      evidence,
    });
  });

  it("accepts retrieved document-source evidence", async () => {
    const evidence = {
      production_summary: null,
      document_search: {
        query: "OPTICAL-SIGNAL-LOW operator check",
        sources: [{
          source_id: "aoi-alarm-guide:002",
          title: "AOI Wafer Inspector Alarm Guide",
          section: "OPTICAL-SIGNAL-LOW",
          relative_path: "data/synthetic/documents/aoi-wafer-inspector-alarm-guide.md",
          excerpt: "Check the optical lens cover.",
          score: 0.72,
        }],
        limitations: [],
      },
      tool_error: null,
    };
    const fetchImplementation = async () => new Response(
      JSON.stringify({ user_message: message, assistant_message: assistant, evidence }),
      { status: 201 },
    );

    await expect(sendMessage(id, "Check the manual", fetchImplementation)).resolves.toEqual({
      user_message: message,
      assistant_message: assistant,
      evidence,
    });
  });
});
