import { describe, expect, it } from "vitest";
import { normalizeAssistantContent } from "./normalizeAssistantContent";

describe("normalizeAssistantContent", () => {
  it("removes complete and case-insensitive think blocks", () => {
    expect(normalizeAssistantContent("Before <think>secret</think> After")).toBe("Before  After");
    expect(normalizeAssistantContent("<THINK>secret</THINK>Answer")).toBe("Answer");
  });

  it("suppresses incomplete streaming wrappers", () => {
    expect(normalizeAssistantContent("<think>partial reasoning")).toBe("");
    expect(normalizeAssistantContent("Answer</think>")).toBe("Answer");
  });

  it("preserves ordinary text and removes multiple blocks", () => {
    expect(normalizeAssistantContent("<think>a</think>One <think>b</think> Two")).toBe("One  Two");
    expect(normalizeAssistantContent("  Answer  ")).toBe("Answer");
  });
});
