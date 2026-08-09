import { describe, expect, it, vi } from "vitest";
import { readDocument } from "./documents";

const payload = {
  document_id: "aoi-alarm-guide",
  title: "AOI Wafer Inspector Alarm Guide",
  document_type: "alarm_guide",
  relative_path: "data/synthetic/documents/aoi-wafer-inspector-alarm-guide.md",
  markdown: "# AOI Wafer Inspector Alarm Guide\n",
  synthetic_demo: true,
};

describe("readDocument", () => {
  it("reads and validates a registry document", async () => {
    const request = vi.fn().mockResolvedValue({ ok: true, json: async () => payload });
    await expect(readDocument("aoi-alarm-guide", request)).resolves.toEqual(payload);
    expect(request).toHaveBeenCalledWith("/api/documents/aoi-alarm-guide", expect.any(Object));
  });

  it("rejects unsuccessful and malformed responses", async () => {
    await expect(readDocument("missing", vi.fn().mockResolvedValue({ ok: false, status: 404 })))
      .rejects.toEqual(expect.objectContaining({ status: 404 }));
    await expect(readDocument("broken", vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })))
      .rejects.toEqual(expect.objectContaining({ status: null }));
  });
});
