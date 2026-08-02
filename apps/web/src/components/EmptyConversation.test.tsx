import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import EmptyConversation from "./EmptyConversation";

describe("EmptyConversation", () => {
  it("offers prompt suggestions that populate the draft", async () => {
    const onPromptSelect = vi.fn();
    const user = userEvent.setup();
    render(<EmptyConversation onPromptSelect={onPromptSelect} />);
    expect(screen.getByText("Start an analysis")).toBeInTheDocument();
    await user.click(screen.getByText("What is the production yield?"));
    expect(onPromptSelect).toHaveBeenCalledWith("What is the production yield?");
  });
});
