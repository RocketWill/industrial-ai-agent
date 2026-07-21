import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Message } from "../api/messages";
import type { MessageState } from "../hooks/useMessages";
import { useMessages } from "../hooks/useMessages";
import ConversationWorkspace from "./ConversationWorkspace";

vi.mock("../hooks/useMessages", () => ({ useMessages: vi.fn() }));

const conversationId = "11111111-1111-1111-8111-111111111111";
const messages: Message[] = [
  { id: "21111111-1111-1111-8111-111111111111", conversation_id: conversationId, role: "user", content: "Question", created_at: "2026-08-02T00:00:00Z" },
  { id: "31111111-1111-1111-8111-111111111111", conversation_id: conversationId, role: "assistant", content: "Answer", created_at: "2026-08-02T00:00:01Z" },
];

const state = (overrides: Partial<MessageState> = {}): MessageState => ({
  messages,
  evidence: null,
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

  it("positions loaded history at the latest message once without smooth-scroll feedback", async () => {
    render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    expect(scrollTo).toHaveBeenCalledTimes(1);
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

    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 0, behavior: "auto" }));
  });

  it("repositions once when the selected conversation changes", async () => {
    const view = render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);
    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    scrollTo.mockClear();

    view.rerender(<ConversationWorkspace conversationId="41111111-1111-1111-8111-111111111111" conversationTitle="Other analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);

    await waitFor(() => expect(scrollTo).toHaveBeenCalledTimes(1));
    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 0, behavior: "auto" }));
  });

  it("marks every assistant bubble with the semantic rainbow class", () => {
    const { container } = render(<ConversationWorkspace conversationId={conversationId} conversationTitle="Analysis" onOpenNavigation={vi.fn()} onOpenContext={vi.fn()} />);
    expect(container.querySelectorAll(".assistant-bubble-content")).toHaveLength(1);
    expect(container.querySelector(".user-bubble-content")).toBeNull();
  });
});
