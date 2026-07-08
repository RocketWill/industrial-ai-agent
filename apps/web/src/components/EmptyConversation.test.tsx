import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import EmptyConversation from "./EmptyConversation";

describe("EmptyConversation", () => {
  it("offers prompt suggestions that populate the draft", async () => {
    const onPromptSelect = vi.fn();
    const user = userEvent.setup();
    render(<EmptyConversation onPromptSelect={onPromptSelect} />);
    expect(screen.getByText("What would you like to inspect?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Analyze yield changes in the last shift" }));
    expect(onPromptSelect).toHaveBeenCalledWith("Analyze yield changes in the last shift");
  });
});
