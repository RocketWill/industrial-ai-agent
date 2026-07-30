import { describe, expect, it } from "vitest";
import { buildMessagesUrl, listMessages, sendMessage } from "./messages";

const id = "11111111-1111-1111-8111-111111111111";
const message = { id, conversation_id: id, role: "user" as const, content: "Check status", created_at: "2026-07-30T00:00:00Z" };
const assistant = { ...message, id: "22222222-2222-1222-8222-222222222222", role: "assistant" as const, content: "The status is stable." };

describe("messages API", () => {
  it("builds message URLs", () => {
    expect(buildMessagesUrl(undefined, id)).toBe(`/api/conversations/${id}/messages`);
    expect(buildMessagesUrl("https://api.example.test/", id)).toBe(`https://api.example.test/conversations/${id}/messages`);
  });

  it("loads validated history", async () => {
    const fetchImplementation = async () => new Response(JSON.stringify([message]), { status: 200 });
    await expect(listMessages(id, fetchImplementation)).resolves.toEqual([message]);
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
});
