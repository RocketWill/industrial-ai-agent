import { describe, expect, it } from "vitest";
import { buildContextUrl, getWorkspaceContext } from "./context";

const id = "11111111-1111-1111-8111-111111111111";
const context = { environment: "synthetic", device: null, lot: null, time_range: null, data_source: "synthetic_demo" } as const;

describe("workspace context API", () => {
  it("builds conversation context URLs", () => {
    expect(buildContextUrl(id, "https://example.test/api/")).toBe(`https://example.test/api/conversations/${id}/context`);
  });

  it("loads and validates default context", async () => {
    const result = await getWorkspaceContext(id, async () => new Response(JSON.stringify(context), { status: 200 }));
    expect(result).toEqual(context);
  });

  it("rejects invalid context responses", async () => {
    await expect(getWorkspaceContext(id, async () => new Response(JSON.stringify({ ...context, data_source: "production" }), { status: 200 }))).rejects.toThrow("Message request failed");
  });
});
