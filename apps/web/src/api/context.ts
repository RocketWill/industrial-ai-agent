import type { ConversationFetch } from "./conversations";
import { MessageApiError } from "./messages";

export type WorkspaceContext = {
  environment: "development" | "synthetic";
  device: string | null;
  lot: string | null;
  time_range: string | null;
  data_source: "synthetic_demo";
};
export type WorkspaceContextUpdate = Pick<WorkspaceContext, "device" | "lot" | "time_range">;

const isContext = (value: unknown): value is WorkspaceContext => {
  if (typeof value !== "object" || value === null) return false;
  const context = value as WorkspaceContext;
  return (context.environment === "development" || context.environment === "synthetic") &&
    (context.device === null || typeof context.device === "string") &&
    (context.lot === null || typeof context.lot === "string") &&
    (context.time_range === null || typeof context.time_range === "string") &&
    context.data_source === "synthetic_demo";
};

export function buildContextUrl(conversationId: string, baseUrl?: string): string {
  const base = baseUrl?.trim() ? baseUrl.replace(/\/+$/, "") : "/api";
  return `${base}/conversations/${conversationId}/context`;
}

export async function getWorkspaceContext(conversationId: string, fetchImplementation: ConversationFetch = fetch): Promise<WorkspaceContext> {
  try {
    const response = await fetchImplementation(buildContextUrl(conversationId, import.meta.env.VITE_API_BASE_URL), { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("unsuccessful response");
    const payload: unknown = await response.json();
    if (!isContext(payload)) throw new Error("invalid response");
    return payload;
  } catch (error) {
    throw new MessageApiError(error);
  }
}

export async function updateWorkspaceContext(conversationId: string, update: WorkspaceContextUpdate, fetchImplementation: ConversationFetch = fetch): Promise<WorkspaceContext> {
  try {
    const response = await fetchImplementation(buildContextUrl(conversationId, import.meta.env.VITE_API_BASE_URL), { method: "PATCH", headers: { Accept: "application/json", "Content-Type": "application/json" }, body: JSON.stringify(update) });
    if (!response.ok) throw new Error("unsuccessful response");
    const payload: unknown = await response.json();
    if (!isContext(payload)) throw new Error("invalid response");
    return payload;
  } catch (error) { throw new MessageApiError(error); }
}
