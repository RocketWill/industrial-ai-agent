export type HealthResponse = {
  status: "ok";
};

export type FetchImplementation = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

export class HealthCheckError extends Error {
  readonly cause: unknown;

  constructor(cause: unknown) {
    super("API health check failed");
    this.name = "HealthCheckError";
    this.cause = cause;
  }
}

export function buildHealthUrl(baseUrl?: string): string {
  if (!baseUrl?.trim()) {
    return "/api/health";
  }

  return `${baseUrl.replace(/\/+$/, "")}/health`;
}

function isHealthResponse(value: unknown): value is HealthResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    value.status === "ok"
  );
}

export async function checkHealth(
  fetchImplementation: FetchImplementation = fetch,
): Promise<HealthResponse> {
  try {
    const response = await fetchImplementation(
      buildHealthUrl(import.meta.env.VITE_API_BASE_URL),
      { headers: { Accept: "application/json" } },
    );

    if (!response.ok) {
      throw new Error("Health endpoint returned an unsuccessful response");
    }

    const payload: unknown = await response.json();
    if (!isHealthResponse(payload)) {
      throw new Error("Health endpoint returned an invalid response");
    }

    return payload;
  } catch (error) {
    if (error instanceof HealthCheckError) {
      throw error;
    }
    throw new HealthCheckError(error);
  }
}
