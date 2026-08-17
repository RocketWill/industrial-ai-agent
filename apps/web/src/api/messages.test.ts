import { describe, expect, it } from "vitest";
import { buildMessagesUrl, listMessages, sendMessage, streamMessage } from "./messages";

const id = "11111111-1111-1111-8111-111111111111";
const message = { id, conversation_id: id, role: "user" as const, content: "Check status", created_at: "2026-07-30T00:00:00Z", suggested_actions: [] };
const assistant = { ...message, id: "22222222-2222-1222-8222-222222222222", role: "assistant" as const, content: "The status is stable." };
const productionSummary = { equipment_id: "AOI-WAFER-01", lot_id: null, start: "2026-01-15T13:00:00Z", end: "2026-01-15T17:00:00Z", inspected_wafers: 10, passed_wafers: 9, failed_wafers: 1, yield_rate: 0.9, defect_counts: [], alarm_events: [], limitations: [] };
const equipmentStatus = { equipment_id: "AOI-WAFER-01", observed_at: "2026-01-15T17:00:00Z", status: "running", effective_start: "2026-01-15T16:00:00Z", effective_end: "2026-01-15T18:00:00Z", source_event_id: "state-003", reason_code: "SYNTHETIC-SCHEDULED-RUN", limitations: [] };
const defectDistribution = { equipment_id: "AOI-WAFER-01", lot_id: "LOT-DEMO-001", start: "2026-01-15T13:00:00Z", end: "2026-01-15T17:00:00Z", failed_wafers: 1, classified_defect_count: 1, unclassified_failed_wafers: 0, items: [{ category: "scratch", count: 1, share: 1, rank: 1 }], limitations: [] };
const documentSearch = { query: "OPTICAL-SIGNAL-LOW", sources: [{ source_id: "guide:001", source: "built_in", title: "Alarm Guide", section: "OPTICAL-SIGNAL-LOW", relative_path: "data/synthetic/documents/guide.md", excerpt: "Check the lens.", score: 0.72 }], limitations: [] };
const combined = { manufacturing_kind: "production", manufacturing: { status: "succeeded", result: productionSummary, error_code: null }, documents: { status: "not_run", result: null, error_code: null }, document_query: "OPTICAL-SIGNAL-LOW", answer_status: "succeeded" };
const snapshots = {
  production_summary: { status: "available", schema_version: 1, kind: "production_summary", production_summary: productionSummary },
  equipment_status: { status: "available", schema_version: 1, kind: "equipment_status", equipment_status: equipmentStatus },
  defect_distribution: { status: "available", schema_version: 1, kind: "defect_distribution", defect_distribution: defectDistribution },
  document_search: { status: "available", schema_version: 1, kind: "document_search", document_search: documentSearch },
  combined: { status: "available", schema_version: 1, kind: "combined", ...combined },
} as const;
const suggestedActions = [
  { id: "production_evidence_first", label: "Production evidence", message: "Show the production evidence first." },
  { id: "document_evidence_first", label: "Document evidence", message: "Search the documents first." },
];

describe("messages API", () => {
  it("builds message URLs", () => {
    expect(buildMessagesUrl(undefined, id)).toBe(`/api/conversations/${id}/messages`);
    expect(buildMessagesUrl("https://api.example.test/", id)).toBe(`https://api.example.test/conversations/${id}/messages`);
  });

  it("loads validated history", async () => {
    const fetchImplementation = async () => new Response(JSON.stringify([message]), { status: 200 });
    await expect(listMessages(id, fetchImplementation)).resolves.toEqual([message]);
  });

  it("accepts history without an evidence snapshot", async () => {
    await expect(listMessages(id, async () => new Response(JSON.stringify([assistant]), { status: 200 }))).resolves.toEqual([assistant]);
  });

  it.each(Object.entries(snapshots))("accepts %s historical evidence snapshot", async (_kind, evidence_snapshot) => {
    const historicalAssistant = { ...assistant, evidence_snapshot };
    await expect(listMessages(id, async () => new Response(JSON.stringify([historicalAssistant]), { status: 200 }))).resolves.toEqual([historicalAssistant]);
  });

  it("accepts unavailable historical evidence", async () => {
    const historicalAssistant = { ...assistant, evidence_snapshot: { status: "unavailable", code: "invalid_snapshot" } };
    await expect(listMessages(id, async () => new Response(JSON.stringify([historicalAssistant]), { status: 200 }))).resolves.toEqual([historicalAssistant]);
  });

  it.each([
    { ...snapshots.production_summary, kind: "unknown" },
    { ...snapshots.production_summary, schema_version: 2 },
    { ...snapshots.production_summary, equipment_status: equipmentStatus },
  ])("rejects invalid historical evidence snapshot", async (evidence_snapshot) => {
    const historicalAssistant = { ...assistant, evidence_snapshot };
    await expect(listMessages(id, async () => new Response(JSON.stringify([historicalAssistant]), { status: 200 }))).rejects.toThrow("Message request failed");
  });

  it("rejects a user-owned evidence snapshot", async () => {
    await expect(listMessages(id, async () => new Response(JSON.stringify([{ ...message, evidence_snapshot: snapshots.production_summary }]), { status: 200 }))).rejects.toThrow("Message request failed");
  });

  it("accepts the canonical guided routing actions on assistant messages", async () => {
    const guided = { ...assistant, suggested_actions: suggestedActions };
    const fetchImplementation = async () => new Response(JSON.stringify([guided]), { status: 200 });

    await expect(listMessages(id, fetchImplementation)).resolves.toEqual([guided]);
  });

  it("rejects altered or user-owned guided routing actions", async () => {
    const altered = { ...assistant, suggested_actions: [{ ...suggestedActions[0], message: "Run everything." }] };
    const userOwned = { ...message, suggested_actions: suggestedActions };

    await expect(listMessages(id, async () => new Response(JSON.stringify([altered]), { status: 200 }))).rejects.toThrow("Message request failed");
    await expect(listMessages(id, async () => new Response(JSON.stringify([userOwned]), { status: 200 }))).rejects.toThrow("Message request failed");
  });

  it("sends trimmed content and validates the exchange", async () => {
    const requests: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const fetchImplementation = async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ input, init });
      return new Response(JSON.stringify({ user_message: message, assistant_message: assistant }), { status: 201 });
    };
    await expect(sendMessage(id, "  Check status  ", fetchImplementation)).resolves.toEqual({ user_message: message, assistant_message: assistant });
    expect(requests[0]).toEqual({ input: `/api/conversations/${id}/messages`, init: { method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json" }, body: JSON.stringify({ content: "Check status" }) } });
  });

  it.each(Object.entries(snapshots))("accepts %s evidence on an assistant exchange", async (_kind, evidence_snapshot) => {
    const exchange = { user_message: message, assistant_message: { ...assistant, evidence_snapshot } };
    await expect(sendMessage(id, "Check status", async () => new Response(JSON.stringify(exchange), { status: 201 }))).resolves.toEqual(exchange);
  });

  it("accepts unavailable evidence on an assistant exchange", async () => {
    const exchange = { user_message: message, assistant_message: { ...assistant, evidence_snapshot: { status: "unavailable", code: "unsupported_snapshot_version" } } };
    await expect(sendMessage(id, "Check status", async () => new Response(JSON.stringify(exchange), { status: 201 }))).resolves.toEqual(exchange);
  });


  it("validates safe routing progress events", async () => {
    const body = [
      'event: routing_started\ndata: {"label":"Understanding request"}\n\n',
      'event: routing_retry\ndata: {"label":"Retrying request classification","retry_count":1}\n\n',
      'event: routing_fallback_used\ndata: {"label":"Using safe fallback","reason_code":"ambiguous_request"}\n\n',
      'event: routing_decided\ndata: {"label":"Generating response","route":"general","reason_code":"ambiguous_request","retry_count":1}\n\n',
    ].join("");
    const fetchImplementation = async () => new Response(body, {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    });
    const events = [];
    for await (const event of streamMessage(
      id,
      "Analyze this",
      new AbortController().signal,
      fetchImplementation,
    )) events.push(event);

    expect(events.map((event) => event.type)).toEqual([
      "routing_started",
      "routing_retry",
      "routing_fallback_used",
      "routing_decided",
    ]);
  });

  it("validates path-aware combined evidence events", async () => {
    const result = {
      equipment_id: "AOI-WAFER-01", lot_id: null,
      start: "2026-01-15T13:00:00Z", end: "2026-01-15T17:00:00Z",
      inspected_wafers: 300, passed_wafers: 257, failed_wafers: 43,
      yield_rate: 257 / 300, defect_counts: [], alarm_events: [], limitations: [],
    };
    const body = `event: combined_tool_result\ndata: ${JSON.stringify({ path: "manufacturing", manufacturing_kind: "production", status: "succeeded", result, error_code: null })}\n\nevent: combined_evidence_completed\ndata: {"answer_status":"succeeded"}\n\n`;
    const events = [];
    for await (const event of streamMessage(id, "Analyze", new AbortController().signal, async () => new Response(body, { status: 200 }))) events.push(event);

    expect(events).toEqual([
      { type: "combined_tool_result", path: "manufacturing", manufacturing_kind: "production", outcome: { status: "succeeded", result, error_code: null } },
      { type: "combined_evidence_completed", answer_status: "succeeded" },
    ]);
  });

  it("rejects routing events outside the public route contract", async () => {
    const fetchImplementation = async () => new Response(
      'event: routing_decided\ndata: {"label":"Unknown","route":"invented","reason_code":"general_request","retry_count":0}\n\n',
      { status: 200, headers: { "Content-Type": "text/event-stream" } },
    );

    const consume = async () => {
      const iterator = streamMessage(
        id,
        "Analyze this",
        new AbortController().signal,
        fetchImplementation,
      );
      await iterator.next();
    };

    await expect(consume()).rejects.toBeInstanceOf(Error);
  });
});
