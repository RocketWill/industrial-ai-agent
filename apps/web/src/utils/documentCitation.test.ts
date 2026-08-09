import { describe, expect, it } from "vitest";
import { parseCitation } from "./documentCitation";

describe("parseCitation", () => {
  it("parses stable section-local citations", () => {
    expect(parseCitation("aoi-alarm-guide:optical-signal-low:001")).toEqual({
      documentId: "aoi-alarm-guide",
      sectionSlug: "optical-signal-low",
    });
  });

  it("rejects legacy and malformed citations", () => {
    expect(parseCitation("aoi-alarm-guide:002")).toBeNull();
    expect(parseCitation("../../private:section:one")).toBeNull();
  });
});
