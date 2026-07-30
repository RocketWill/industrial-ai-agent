import { describe, expect, it } from "vitest";
import {
  buildConversationsUrl,
  listConversations,
} from "./conversations";

const conversation = {
  id: "11111111-1111-1111-8111-111111111111",
  title: "Yield investigation",
  created_at: "2026-07-30T00:00:00Z",
};

describe("conversations API", () => {
  it("builds the proxied and configured URLs", () => {
    expect(buildConversationsUrl()).toBe("/api/conversations");
    expect(buildConversationsUrl("https://api.example.test/")).toBe(
      "https://api.example.test/conversations",
    );
  });

  it("loads and validates conversations", async () => {
    const fetchImplementation = async () =>
      new Response(JSON.stringify([conversation]), { status: 200 });

    await expect(listConversations(fetchImplementation)).resolves.toEqual([
      conversation,
    ]);
  });
});
