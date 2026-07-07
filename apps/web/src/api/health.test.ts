import { describe, expect, it } from "vitest";

import {
  buildHealthUrl,
  checkHealth,
  type FetchImplementation,
} from "./health";

describe("buildHealthUrl", () => {
  it("uses the development proxy when no browser API base URL is configured", () => {
    expect(buildHealthUrl()).toBe("/api/health");
  });

  it("normalizes a configured browser API base URL", () => {
    expect(buildHealthUrl("https://api.example.test/")).toBe(
      "https://api.example.test/health",
    );
  });
});

describe("checkHealth", () => {
  it("accepts the documented health response", async () => {
    const requests: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const fetchImplementation: FetchImplementation = async (input, init) => {
      requests.push({ input, init });
      return new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    await expect(checkHealth(fetchImplementation)).resolves.toEqual({
      status: "ok",
    });
    expect(requests).toEqual([
      {
        input: "/api/health",
        init: { headers: { Accept: "application/json" } },
      },
    ]);
  });

  it.each([
    new Response(null, { status: 503 }),
    new Response("not-json", { status: 200 }),
    new Response(JSON.stringify({ status: "degraded" }), { status: 200 }),
  ])("maps an unusable response to the public health error", async (response) => {
    const fetchImplementation: FetchImplementation = async () => response;

    await expect(checkHealth(fetchImplementation)).rejects.toEqual(
      expect.objectContaining({
        name: "HealthCheckError",
        message: "API health check failed",
      }),
    );
  });

  it("maps a transport failure to the public health error", async () => {
    const fetchImplementation: FetchImplementation = async () => {
      throw new TypeError("offline");
    };

    await expect(checkHealth(fetchImplementation)).rejects.toEqual(
      expect.objectContaining({
        name: "HealthCheckError",
        message: "API health check failed",
      }),
    );
  });

  it("preserves the underlying failure without exposing it in the public message", async () => {
    const cause = new TypeError("offline");
    const fetchImplementation: FetchImplementation = async () => {
      throw cause;
    };

    await expect(checkHealth(fetchImplementation)).rejects.toMatchObject({
      cause,
      message: "API health check failed",
    });
  });
});
