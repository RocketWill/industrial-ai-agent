import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Message } from "../api/messages";
import type { MessageState } from "../hooks/useMessages";
import { useMessages } from "../hooks/useMessages";
import ConversationWorkspace from "./ConversationWorkspace";

vi.mock("../hooks/useMessages", () => ({ useMessages: vi.fn() }));

const conversationId = "11111111-1111-1111-8111-111111111111";
const messages: Message[] = [
  { id: "21111111-1111-1111-8111-111111111111", conversation_id: conversationId, role: "user", content: "Question", created_at: "2026-08-02T00:00:00Z", suggested_actions: [] },
  { id: "31111111-1111-1111-8111-111111111111", conversation_id: conversationId, role: "assistant", content: "Answer", created_at: "2026-08-02T00:00:01Z", suggested_actions: [] },
];

const state = (overrides: Partial<MessageState> = {}): MessageState => ({
  messages,
  evidence: null,
  combinedEvidence: null,
  workingNotes: null,
  runState: { phase: "idle", label: null },
  isLoading: false,
  isSending: false,
  isStreaming: false,
  error: null,
  draft: "",
  setDraft: vi.fn(),
  reload: vi.fn(),
  send: vi.fn().mockResolvedValue(true),
  cancelStreaming: vi.fn(),
  setWorkingNotesOpen: vi.fn(),
  ...overrides,
});

describe("ConversationWorkspace scrolling", () => {
  let currentState: MessageState;
  let scrollTo: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    currentState = state();
    vi.mocked(useMessages).mockImplementation(() => currentState);
    scrollTo = vi.fn(function (this: HTMLElement, options?: ScrollToOptions) {
      if (typeof options?.top === "number") this.scrollTop = options.top;
    });
    Object.defineProperty(HTMLElement.prototype, "scrollTo", { configurable: true, value: scrollTo });
  });

  it("renders the composer without an invalid textarea height", async () => {
    const consoleError = vi.spyOn(console, "error");

    render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    await waitFor(() => expect(screen.getByPlaceholderText("Ask about this synthetic analysis")).toBeInTheDocument());
    expect(consoleError).not.toHaveBeenCalledWith(
      expect.stringContaining("`NaN` is an invalid value for the `%s` css style property."),
      "height",
      expect.anything(),
    );
  });

  it("positions loaded history at the latest message once without smooth-scroll feedback", async () => {
    render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    await waitFor(() => expect(scrollTo).toHaveBeenCalledTimes(1));
    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 0, behavior: "auto" }));
  });

  it("retains manual reading position during streaming and resumes from jump to latest", async () => {
    const view = render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);
    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    scrollTo.mockClear();

    const scrollRegion = view.container.querySelector<HTMLElement>(".message-scroll-region");
    expect(scrollRegion).not.toBeNull();
    Object.defineProperties(scrollRegion!, {
      scrollHeight: { configurable: true, value: 1200 },
      clientHeight: { configurable: true, value: 500 },
      scrollTop: { configurable: true, writable: true, value: -240 },
    });
    fireEvent.scroll(scrollRegion!);
    expect(screen.getByRole("button", { name: "Jump to latest message" })).toBeInTheDocument();

    currentState = state({
      messages: [messages[0], { ...messages[1], content: "Answer with another token" }],
      isStreaming: true,
      runState: { phase: "generating", label: "Generating response" },
    });
    view.rerender(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);
    expect(scrollTo).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Jump to latest message" }));
    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 0, behavior: "auto" }));
  });

  it("follows streaming tokens while the reader remains at the latest message", async () => {
    const view = render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);
    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    scrollTo.mockClear();

    currentState = state({
      messages: [messages[0], { ...messages[1], content: "Answer with another token" }],
      isStreaming: true,
      runState: { phase: "generating", label: "Generating response" },
    });
    view.rerender(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    await waitFor(() => expect(scrollTo).toHaveBeenCalledTimes(1));
    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 0, behavior: "auto" }));
  });

  it("submits the first message without trying to scroll an unmounted list", async () => {
    currentState = state({ messages: [], draft: "First question" });
    render(<ConversationWorkspace conversationId={conversationId} conversationTitle="New analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "arrow-up" }));

    expect(scrollTo).not.toHaveBeenCalled();
    expect(currentState.send).toHaveBeenCalledWith("First question");
  });

  it("defers the first streaming scroll until the message list has mounted", async () => {
    currentState = state({ messages: [] });
    const view = render(<ConversationWorkspace conversationId={conversationId} conversationTitle="New analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    currentState = state({
      messages: [messages[0], { ...messages[1], id: "00000000-0000-1000-8000-000000000000", content: "" }],
      isStreaming: true,
      runState: { phase: "generating", label: "Generating response" },
    });
    view.rerender(<ConversationWorkspace conversationId={conversationId} conversationTitle="New analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    expect(scrollTo).not.toHaveBeenCalled();
    await waitFor(() => expect(scrollTo).toHaveBeenCalledTimes(1));
  });

  it("repositions once when the selected conversation changes", async () => {
    const view = render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);
    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    scrollTo.mockClear();

    view.rerender(<ConversationWorkspace conversationId="41111111-1111-1111-8111-111111111111" conversationTitle="Other analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    await waitFor(() => expect(scrollTo).toHaveBeenCalledTimes(1));
    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 0, behavior: "auto" }));
  });

  it("keeps the completed assistant accent static and excludes user bubbles", () => {
    const { container } = render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);
    expect(container.querySelectorAll(".assistant-bubble-content")).toHaveLength(1);
    expect(container.querySelector(".assistant-bubble-streaming")).toBeNull();
    expect(container.querySelector(".user-bubble-content")).toBeNull();
  });

  it("shows working notes only on the latest assistant message after streaming completes", () => {
    currentState = state({
      messages: [
        messages[0],
        { ...messages[1], content: "Earlier answer" },
        { ...messages[1], id: "51111111-1111-1111-8111-111111111111", content: "Latest answer" },
      ],
      isStreaming: false,
      workingNotes: { content: "Inspect the latest result", status: "complete", open: false },
    });

    render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    expect(screen.getAllByText("Model working notes")).toHaveLength(1);
    expect(screen.getByText("Inspect the latest result")).toBeInTheDocument();
  });

  it("forwards working-notes disclosure changes to the message state", async () => {
    const setWorkingNotesOpen = vi.fn();
    currentState = state({
      workingNotes: { content: "Inspect the latest result", status: "active", open: true },
      setWorkingNotesOpen,
    });

    render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    fireEvent.click(screen.getByText("Model working notes"));
    await waitFor(() => expect(setWorkingNotesOpen).toHaveBeenCalledWith(false));
  });

  it("renders no working-notes disclosure when the state is empty", () => {
    currentState = state({ workingNotes: null });

    render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    expect(screen.queryByText("Model working notes")).not.toBeInTheDocument();
  });

  it("renders historical evidence from a reloaded assistant message without conversation evidence state", async () => {
    const historicalProduction = {
      equipment_id: "AOI-WAFER-01",
      lot_id: null,
      start: "2026-01-15T13:00:00Z",
      end: "2026-01-15T17:00:00Z",
      inspected_wafers: 300,
      passed_wafers: 257,
      failed_wafers: 43,
      yield_rate: 257 / 300,
      defect_counts: [],
      alarm_events: [],
      limitations: [],
    };
    const assistant = {
      ...messages[1],
      content: "Reloaded answer",
      evidence_snapshot: {
        status: "available" as const,
        schema_version: 1 as const,
        kind: "production_summary" as const,
        production_summary: historicalProduction,
      },
    };
    currentState = state({ messages: [messages[0], assistant] });
    const view = render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    expect(await screen.findByText("Reloaded answer")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Historical evidence" })).toBeInTheDocument();
    expect(screen.getByText("Historical snapshot")).toBeInTheDocument();
    expect(screen.getByText("Production summary")).toBeInTheDocument();

    currentState = state({
      messages: [{ ...messages[0] }, { ...assistant, evidence_snapshot: { status: "unavailable", code: "invalid_snapshot" } }],
    });
    view.rerender(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    expect(await screen.findByText("Reloaded answer")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Historical evidence unavailable" })).toBeInTheDocument();
    expect(screen.getByText("invalid_snapshot")).toBeInTheDocument();
  });

  it("adds the animated frame only to the active streaming assistant bubble", () => {
    const view = render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);
    currentState = state({
      messages: [
        messages[0],
        {
          ...messages[1],
          id: "00000000-0000-1000-8000-000000000000",
          content: "Partial answer",
        },
      ],
      isStreaming: true,
      runState: { phase: "generating", label: "Generating response" },
    });

    view.rerender(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);
    const assistantBubble = view.container.querySelector(".assistant-bubble-content");
    expect(assistantBubble).toHaveClass("assistant-bubble-streaming");
    expect(assistantBubble?.querySelector(".assistant-beam-host")).toBeInTheDocument();
  });

  it("removes the animated frame from a failed assistant run", () => {
    currentState = state({
      messages: [
        messages[0],
        {
          ...messages[1],
          id: "00000000-0000-1000-8000-000000000000",
          content: "Generation failed.",
        },
      ],
      isStreaming: false,
      runState: { phase: "failed", label: "Generation failed" },
    });

    const { container } = render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);
    expect(container.querySelector(".assistant-bubble-content")).not.toHaveClass("assistant-bubble-streaming");
  });

  it("offers a keyboard-accessible Documents action without a selected conversation", async () => {
    const user = userEvent.setup();
    const onOpenDocuments = vi.fn();

    render(
      <ConversationWorkspace
        conversationId={null}
        conversationTitle={null}
        onOpenNavigation={vi.fn()}
        onOpenContext={vi.fn()}
        onOpenDocuments={onOpenDocuments}
      />,
    );

    const documentsTrigger = screen.getByRole("button", { name: "Documents" });
    documentsTrigger.focus();
    await user.keyboard("{Enter}");

    expect(onOpenDocuments).toHaveBeenCalledTimes(1);
  });

  it("offers persisted routing choices only on the latest unresolved assistant message", async () => {
    const user = userEvent.setup();
    const guided: Message = {
      ...messages[1],
      suggested_actions: [
        { id: "production_evidence_first" as const, label: "Production evidence", message: "Show the production evidence first." },
        { id: "document_evidence_first" as const, label: "Document evidence", message: "Search the documents first." },
      ],
    };
    currentState = state({ messages: [messages[0], guided] });
    render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    const productionChoice = screen.getByRole("button", { name: "Production evidence" });
    productionChoice.focus();
    await user.keyboard("{Enter}");

    expect(currentState.send).toHaveBeenCalledTimes(1);
    expect(currentState.send).toHaveBeenCalledWith("Show the production evidence first.");
  });

  it("hides routing choices after a later user message", () => {
    const guided: Message = {
      ...messages[1],
      suggested_actions: [
        { id: "production_evidence_first" as const, label: "Production evidence", message: "Show the production evidence first." },
      ],
    };
    currentState = state({ messages: [messages[0], guided, { ...messages[0], id: "41111111-1111-1111-8111-111111111111", content: "Follow-up" }] });
    render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    expect(screen.queryByText("Production evidence")).not.toBeInTheDocument();
  });

  it("disables routing choices while another send is active", () => {
    const guided: Message = {
      ...messages[1],
      suggested_actions: [
        { id: "production_evidence_first" as const, label: "Production evidence", message: "Show the production evidence first." },
      ],
    };
    currentState = state({ messages: [messages[0], guided], isSending: true });
    render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Production evidence" })).toBeDisabled();
  });

  it("keeps the visible streaming cancel control usable", async () => {
    const cancelStreaming = vi.fn();
    currentState = state({ isSending: true, isStreaming: true, cancelStreaming });
    render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    const cancelButton = screen.getByRole("button", { name: /stop|cancel/i });
    expect(cancelButton).toBeEnabled();
    await userEvent.click(cancelButton);

    expect(cancelStreaming).toHaveBeenCalledTimes(1);
  });
});
