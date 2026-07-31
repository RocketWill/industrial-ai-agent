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
});
