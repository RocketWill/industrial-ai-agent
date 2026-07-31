import { describe, expect, it } from "vitest";
import { listSyntheticDevices } from "./devices";

describe("synthetic devices API", () => {
  it("validates the catalog response", async () => {
    const result = await listSyntheticDevices(async () => new Response(JSON.stringify([{ id: "AOI-WAFER-01", name: "AOI Wafer Inspector 01", category: "inspection", data_source: "synthetic_demo" }]), { status: 200 }));
    expect(result[0].id).toBe("AOI-WAFER-01");
  });

  it("rejects malformed catalog entries", async () => {
    await expect(listSyntheticDevices(async () => new Response(JSON.stringify([{ id: "unknown" }]), { status: 200 }))).rejects.toThrow("Message request failed");
  });
});
