import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

if (typeof globalThis.Response === "undefined") {
  class TestResponse {
    readonly ok: boolean;
    readonly status: number;
    readonly body = null;
    private readonly payload: unknown;

    constructor(payload: unknown = null, init: { status?: number } = {}) {
      this.status = init.status ?? 200;
      this.ok = this.status >= 200 && this.status < 300;
      this.payload = payload;
    }

    async json(): Promise<unknown> { return JSON.parse(String(this.payload)); }
  }
  globalThis.Response = TestResponse as unknown as typeof Response;
}

if (typeof window.matchMedia !== "function") {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
}

if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

if (typeof globalThis.IntersectionObserver === "undefined") {
  globalThis.IntersectionObserver = class IntersectionObserver {
    readonly root = null;
    readonly rootMargin = "0px";
    readonly thresholds = [0];
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() { return []; }
  } as unknown as typeof IntersectionObserver;
}

if (typeof globalThis.Notification === "undefined") {
  globalThis.Notification = class Notification {
    static permission: NotificationPermission = "denied";
    static requestPermission = async () => "denied" as NotificationPermission;
    readonly title: string;
    constructor(title: string) { this.title = title; }
    close() {}
    addEventListener() {}
    removeEventListener() {}
    dispatchEvent() { return false; }
  } as unknown as typeof Notification;
}

afterEach(() => {
  cleanup();
});
