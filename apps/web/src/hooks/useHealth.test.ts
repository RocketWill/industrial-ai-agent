import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { HealthResponse } from "../api/health";
import { useHealth } from "./useHealth";

describe("useHealth", () => {
  it("does not start another request while the initial health check is pending", async () => {
    const pendingResponse = new Promise<HealthResponse>(() => undefined);
    const check = vi.fn().mockReturnValue(pendingResponse);
    const { result } = renderHook(() => useHealth(check));

    await waitFor(() => {
      expect(check).toHaveBeenCalledTimes(1);
    });

    act(() => {
      void result.current.checkAgain();
      void result.current.checkAgain();
    });

    expect(check).toHaveBeenCalledTimes(1);
  });
});
