import { useCallback, useEffect, useRef, useState } from "react";

import { checkHealth, type HealthResponse } from "../api/health";

export type HealthStatus = "checking" | "connected" | "unavailable";

export type UseHealthResult = {
  status: HealthStatus;
  checkAgain: () => Promise<void>;
};

type HealthCheck = () => Promise<HealthResponse>;

export function useHealth(check: HealthCheck = checkHealth): UseHealthResult {
  const [status, setStatus] = useState<HealthStatus>("checking");
  const checkRef = useRef(check);
  const inFlight = useRef(false);
  const isMounted = useRef(true);

  checkRef.current = check;

  const checkAgain = useCallback(async () => {
    if (inFlight.current) {
      return;
    }

    inFlight.current = true;
    if (isMounted.current) {
      setStatus("checking");
    }

    try {
      await checkRef.current();
      if (isMounted.current) {
        setStatus("connected");
      }
    } catch {
      if (isMounted.current) {
        setStatus("unavailable");
      }
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    void checkAgain();

    return () => {
      isMounted.current = false;
    };
  }, [checkAgain]);

  return { status, checkAgain };
}
