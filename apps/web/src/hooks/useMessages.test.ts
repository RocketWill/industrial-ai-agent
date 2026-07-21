import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Message, MessageExchange } from "../api/messages";
import { useMessages } from "./useMessages";

const id = "11111111-1111-1111-8111-111111111111";
const make = (role: "user" | "assistant", content: string): Message => ({ id, conversation_id: id, role, content, created_at: "2026-07-30T00:00:00Z" });
const exchange: MessageExchange = { user_message: make("user", "Question"), assistant_message: make("assistant", "Answer"), evidence: null };

describe("useMessages", () => {
  it("loads history and appends a successful exchange", async () => {
    const api = { listMessages: vi.fn().mockResolvedValue([]), sendMessage: vi.fn().mockResolvedValue(exchange) };
    const { result } = renderHook(() => useMessages(id, api));
    await waitFor(() => expect(api.listMessages).toHaveBeenCalledWith(id));
    act(() => result.current.setDraft(" Question "));
    await act(async () => { await result.current.send(); });
    expect(result.current.messages).toEqual([exchange.user_message, exchange.assistant_message]);
    expect(result.current.draft).toBe("");
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
    const api = {
      listMessages: vi.fn().mockResolvedValue([]),
      sendMessage: vi.fn().mockResolvedValue(exchange),
      streamMessage: vi.fn(async function* () {
        yield { type: "message_started" as const, user_message: exchange.user_message };
        yield { type: "tool_call_started" as const, name: "get_production_summary", arguments: {} };
        yield { type: "tool_result" as const, evidence: { production_summary: null, tool_error: { code: "NO_DATA", message: "No data" } } };
        yield { type: "token" as const, text: "Answer" };
        yield { type: "message_completed" as const, assistant_message: exchange.assistant_message };
      }),
    };
    const { result } = renderHook(() => useMessages(id, api));
    await waitFor(() => expect(api.listMessages).toHaveBeenCalledWith(id));
    act(() => result.current.setDraft("What is the production yield?"));
    await act(async () => { await result.current.send(); });

    expect(api.sendMessage).not.toHaveBeenCalled();
    expect(api.streamMessage).toHaveBeenCalled();
    expect(result.current.messages).toEqual([exchange.user_message, exchange.assistant_message]);
    expect(result.current.runState.phase).toBe("success");
    expect(result.current.evidence?.tool_error?.code).toBe("NO_DATA");
  });

  it("clears previous production evidence for a new general question", async () => {
    const api = {
      listMessages: vi.fn().mockResolvedValue([]),
      sendMessage: vi.fn(),
      streamMessage: vi.fn(async function* (_id, content) {
        yield { type: "message_started" as const, user_message: exchange.user_message };
        if (content.includes("production")) yield { type: "tool_result" as const, evidence: { production_summary: null, tool_error: { code: "NO_DATA", message: "No data" } } };
        yield { type: "token" as const, text: "Answer" };
        yield { type: "message_completed" as const, assistant_message: exchange.assistant_message };
      }),
    };
    const { result } = renderHook(() => useMessages(id, api));
    await waitFor(() => expect(api.listMessages).toHaveBeenCalled());
    act(() => result.current.setDraft("What is the production yield?"));
    await act(async () => { await result.current.send(); });
    expect(result.current.evidence?.tool_error?.code).toBe("NO_DATA");
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
