import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Message, MessageExchange } from "../api/messages";
import { useMessages } from "./useMessages";

const id = "11111111-1111-1111-8111-111111111111";
const make = (role: "user" | "assistant", content: string): Message => ({ id, conversation_id: id, role, content, created_at: "2026-07-30T00:00:00Z", suggested_actions: [] });
const production = { equipment_id: "AOI-WAFER-01", lot_id: null, start: "2026-01-15T13:00:00Z", end: "2026-01-15T17:00:00Z", inspected_wafers: 1, passed_wafers: 1, failed_wafers: 0, yield_rate: 1, defect_counts: [], alarm_events: [], limitations: [] };
const snapshot = { status: "available" as const, schema_version: 1 as const, kind: "production_summary" as const, production_summary: production };
const exchange: MessageExchange = { user_message: make("user", "Question"), assistant_message: { ...make("assistant", "Answer"), evidence_snapshot: snapshot } };

describe("useMessages", () => {
  it("loads history and appends a successful exchange", async () => {
    const api = { listMessages: vi.fn().mockResolvedValue([]), sendMessage: vi.fn().mockResolvedValue(exchange) };
    const { result } = renderHook(() => useMessages(id, api));
    await waitFor(() => expect(api.listMessages).toHaveBeenCalledWith(id));
    act(() => result.current.setDraft(" Question "));
    await act(async () => { await result.current.send(); });
    expect(result.current.messages).toEqual([exchange.user_message, exchange.assistant_message]);
    expect(result.current.draft).toBe("");
    expect(result.current.evidence).toBeNull();
    expect(result.current.combinedEvidence).toBeNull();
  });

  it("keeps historical evidence on its owning assistant message", async () => {
    const history = [exchange.user_message, exchange.assistant_message];
    const api = { listMessages: vi.fn().mockResolvedValue(history), sendMessage: vi.fn() };
    const { result } = renderHook(() => useMessages(id, api));
    await waitFor(() => expect(result.current.messages).toEqual(history));
    expect(result.current.messages[1].evidence_snapshot).toEqual(snapshot);
    expect(result.current.evidence).toBeNull();
    expect(result.current.combinedEvidence).toBeNull();
  });

  it("does not request without a selected conversation and preserves failed drafts", async () => {
    const api = { listMessages: vi.fn().mockResolvedValue([]), sendMessage: vi.fn().mockRejectedValue(new Error("offline")) };
    const { result } = renderHook(() => useMessages(null, api));
    expect(api.listMessages).not.toHaveBeenCalled();
    act(() => result.current.setDraft("Question"));
    const selected = renderHook(() => useMessages(id, api));
    await waitFor(() => expect(api.listMessages).toHaveBeenCalledWith(id));
    act(() => selected.result.current.setDraft("Question"));
    await act(async () => { expect(await selected.result.current.send()).toBe(false); });
    expect(selected.result.current.draft).toBe("Question");
    expect(selected.result.current.error).toBe("Unable to send message");
  });

  it("uses SSE for production queries when streaming is available", async () => {
    let release!: () => void;
    const pause = new Promise<void>((resolve) => { release = resolve; });
    const api = {
      listMessages: vi.fn().mockResolvedValue([]),
      sendMessage: vi.fn().mockResolvedValue(exchange),
      streamMessage: vi.fn(async function* () {
        yield { type: "message_started" as const, user_message: exchange.user_message };
        yield { type: "routing_started" as const, label: "Understanding request" };
        yield { type: "routing_decided" as const, label: "Selecting production summary", route: "production_summary" as const, reason_code: "production_request" as const, retry_count: 0 };
        yield { type: "tool_call_started" as const, name: "get_production_summary", arguments: {} };
        yield { type: "tool_result" as const, evidence: { production_summary: production, tool_error: null } };
        await pause;
        yield { type: "token" as const, text: "Answer" };
        yield { type: "message_completed" as const, assistant_message: exchange.assistant_message };
      }),
    };
    const { result } = renderHook(() => useMessages(id, api));
    await waitFor(() => expect(api.listMessages).toHaveBeenCalledWith(id));
    act(() => result.current.setDraft("What is the production yield?"));
    let request!: Promise<boolean>;
    act(() => { request = result.current.send(); });
    await waitFor(() => expect(result.current.evidence?.production_summary).toEqual(production));
    release();
    await act(async () => { await request; });

    expect(api.sendMessage).not.toHaveBeenCalled();
    expect(api.streamMessage).toHaveBeenCalled();
    expect(result.current.messages).toEqual([exchange.user_message, exchange.assistant_message]);
    expect(result.current.runState.phase).toBe("success");
    expect(result.current.messages[1].evidence_snapshot).toEqual(snapshot);
    expect(result.current.evidence).toBeNull();
  });

  it("keeps both combined evidence paths in the current exchange", async () => {
    const documents = { query: "guide", sources: [], limitations: ["no_relevant_sources"] };
    const api = {
      listMessages: vi.fn().mockResolvedValue([]), sendMessage: vi.fn(),
      streamMessage: vi.fn(async function* () {
        yield { type: "message_started" as const, user_message: exchange.user_message };
        yield { type: "combined_tool_result" as const, path: "manufacturing" as const, manufacturing_kind: "production" as const, outcome: { status: "succeeded" as const, result: production, error_code: null } };
        yield { type: "combined_tool_result" as const, path: "documents" as const, manufacturing_kind: "production" as const, outcome: { status: "empty" as const, result: documents, error_code: null } };
        yield { type: "combined_evidence_completed" as const, answer_status: "succeeded" as const };
        yield { type: "token" as const, text: "Answer" };
        yield { type: "message_completed" as const, assistant_message: { ...exchange.assistant_message, evidence_snapshot: { status: "available" as const, schema_version: 1 as const, kind: "combined" as const, manufacturing_kind: "production" as const, manufacturing: { status: "succeeded" as const, result: production, error_code: null }, documents: { status: "empty" as const, result: { query: "guide", sources: [], limitations: ["no_relevant_sources"] }, error_code: null }, document_query: "guide", answer_status: "succeeded" as const } } };
      }),
    };
    const { result } = renderHook(() => useMessages(id, api));
    await waitFor(() => expect(api.listMessages).toHaveBeenCalled());
    await act(async () => { await result.current.send("Compare production and guide"); });

    expect(result.current.combinedEvidence).toBeNull();
    const completedSnapshot = result.current.messages[1].evidence_snapshot;
    expect(completedSnapshot).not.toBeNull();
    if (!completedSnapshot || completedSnapshot.status !== "available") throw new Error("expected available evidence snapshot");
    expect(completedSnapshot.kind).toBe("combined");
  });

  it("shows routing retry and clarification progress", async () => {
    const api = {
      listMessages: vi.fn().mockResolvedValue([]),
      sendMessage: vi.fn(),
      streamMessage: vi.fn(async function* () {
        yield { type: "message_started" as const, user_message: exchange.user_message };
        yield { type: "routing_started" as const, label: "Understanding request" };
        yield { type: "routing_retry" as const, label: "Retrying request classification", retry_count: 1 };
        yield { type: "routing_decided" as const, label: "Clarification required", route: "clarification" as const, reason_code: "clarification_required" as const, retry_count: 1 };
        yield { type: "clarification_required" as const, label: "Clarification required", reason_code: "clarification_required" as const };
        yield { type: "token" as const, text: "Which equipment?" };
        yield { type: "message_completed" as const, assistant_message: exchange.assistant_message };
      }),
    };
    const { result } = renderHook(() => useMessages(id, api));
    await waitFor(() => expect(api.listMessages).toHaveBeenCalled());
    await act(async () => { await result.current.send("Analyze the run"); });
    expect(result.current.runState.phase).toBe("success");
    expect(result.current.messages).toEqual([exchange.user_message, exchange.assistant_message]);
  });

  it("clears previous production evidence for a new general question", async () => {
    const api = {
      listMessages: vi.fn().mockResolvedValue([]),
      sendMessage: vi.fn(),
      streamMessage: vi.fn(async function* (_id, content) {
        yield { type: "message_started" as const, user_message: exchange.user_message };
        if (content.includes("production")) yield { type: "tool_result" as const, evidence: { production_summary: production, tool_error: null } };
        yield { type: "token" as const, text: "Answer" };
        yield { type: "message_completed" as const, assistant_message: exchange.assistant_message };
      }),
    };
    const { result } = renderHook(() => useMessages(id, api));
    await waitFor(() => expect(api.listMessages).toHaveBeenCalled());
    act(() => result.current.setDraft("What is the production yield?"));
    await act(async () => { await result.current.send(); });
    expect(result.current.evidence).toBeNull();
    act(() => result.current.setDraft("hello"));
    await act(async () => { await result.current.send(); });
    expect(result.current.evidence).toBeNull();
  });

  it("marks the active assistant bubble as cancelled without clearing the draft", async () => {
    const api = {
      listMessages: vi.fn().mockResolvedValue([]),
      sendMessage: vi.fn(),
      streamMessage: vi.fn(async function* (_id: string, _content: string, signal: AbortSignal) {
        yield { type: "message_started" as const, user_message: exchange.user_message };
        await new Promise((_, reject) => signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true }));
      }),
    };
    const { result } = renderHook(() => useMessages(id, api));
    await waitFor(() => expect(api.listMessages).toHaveBeenCalled());
    act(() => result.current.setDraft("Question"));
    let request!: Promise<boolean>;
    act(() => { request = result.current.send(); });
    await waitFor(() => expect(result.current.isStreaming).toBe(true));
    act(() => result.current.cancelStreaming());
    await act(async () => { await request; });

    expect(result.current.runState.phase).toBe("cancelled");
    expect(result.current.messages[result.current.messages.length - 1]?.content).toBe("Generation stopped.");
    expect(result.current.draft).toBe("Question");
  });
});
