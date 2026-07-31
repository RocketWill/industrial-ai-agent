import type { ConversationFetch } from "./conversations";

export type Message = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};
export type ProductionEvidence = {
  production_summary: {
    equipment_id: string; lot_id: string | null; start: string; end: string;
    inspected_wafers: number; passed_wafers: number; failed_wafers: number;
    yield_rate: number | null; defect_counts: { category: string; count: number }[];
    alarm_events: { event_id: string; code: string; started_at: string; ended_at: string }[];
    limitations: string[];
  } | null;
  equipment_status?: {
    equipment_id: string; observed_at: string;
    status: "running" | "idle" | "warning" | "down" | "maintenance" | "unknown";
    effective_start: string | null; effective_end: string | null;
    source_event_id: string | null; reason_code: string | null;
    limitations: string[];
  } | null;
  defect_distribution?: {
    equipment_id: string; lot_id: string | null; start: string; end: string;
    failed_wafers: number; classified_defect_count: number;
    unclassified_failed_wafers: number;
    items: { category: string; count: number; share: number | null; rank: number }[];
    limitations: string[];
  } | null;
  document_search?: {
    query: string;
    sources: {
      source_id: string; title: string; section: string; relative_path: string;
      source: "built_in" | "local_upload"; excerpt: string; score: number;
    }[];
    limitations: string[];
  } | null;
  tool_error: { code: string; message: string } | null;
};

export type MessageExchange = { user_message: Message; assistant_message: Message; evidence: ProductionEvidence | null };
export type RouteIntent =
  | "general"
  | "production_summary"
  | "equipment_status"
  | "defect_distribution"
  | "document_search"
  | "combined"
  | "clarification"
  | "unsupported";
export type RoutingReasonCode =
  | "general_request"
  | "production_request"
  | "equipment_status_request"
  | "defect_distribution_request"
  | "document_request"
  | "combined_request"
  | "clarification_required"
  | "unsupported_capability"
  | "ambiguous_request";
export type MessageStreamEvent =
  | { type: "message_started"; user_message: Message }
  | { type: "routing_started"; label: string }
  | { type: "routing_retry"; label: string; retry_count: number }
  | { type: "routing_decided"; label: string; route: RouteIntent; reason_code: RoutingReasonCode; retry_count: number }
  | { type: "clarification_required"; label: string; reason_code: RoutingReasonCode }
  | { type: "routing_fallback_used"; label: string; reason_code: RoutingReasonCode }
  | { type: "tool_call_started"; name: string; arguments: Record<string, unknown> }
  | { type: "tool_result"; evidence: ProductionEvidence }
  | { type: "token"; text: string }
  | { type: "message_completed"; assistant_message: Message }
  | { type: "error"; code: string; message: string };

export class MessageApiError extends Error {
  readonly cause: unknown;
  constructor(cause: unknown) { super("Message request failed"); this.name = "MessageApiError"; this.cause = cause; }
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function isMessage(value: unknown): value is Message {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Message;
  return UUID.test(item.id) && UUID.test(item.conversation_id) && (item.role === "user" || item.role === "assistant") && typeof item.content === "string" && item.content.trim().length > 0 && item.content.length <= 10000 && typeof item.created_at === "string" && !Number.isNaN(Date.parse(item.created_at));
}
function isExchange(value: unknown): value is MessageExchange {
  return typeof value === "object" && value !== null && isMessage((value as MessageExchange).user_message) && isMessage((value as MessageExchange).assistant_message) && isEvidence((value as MessageExchange).evidence);
}
function isEvidence(value: unknown): value is ProductionEvidence | null {
  if (value === null) return true;
  if (typeof value !== "object") return false;
  const item = value as ProductionEvidence;
  if (item.tool_error !== null && (typeof item.tool_error !== "object" || typeof item.tool_error.code !== "string" || typeof item.tool_error.message !== "string")) return false;
  const summary = item.production_summary;
  const validSummary = summary !== null && typeof summary === "object" && typeof summary.equipment_id === "string" && (summary.lot_id === null || typeof summary.lot_id === "string") && typeof summary.start === "string" && typeof summary.end === "string" && Number.isInteger(summary.inspected_wafers) && Number.isInteger(summary.passed_wafers) && Number.isInteger(summary.failed_wafers) && (summary.yield_rate === null || typeof summary.yield_rate === "number") && Array.isArray(summary.defect_counts) && Array.isArray(summary.alarm_events) && Array.isArray(summary.limitations) && summary.limitations.every((item) => typeof item === "string");
  const status = item.equipment_status;
  const validStatus = status !== null && status !== undefined && typeof status === "object" && typeof status.equipment_id === "string" && typeof status.observed_at === "string" && ["running", "idle", "warning", "down", "maintenance", "unknown"].includes(status.status) && (status.effective_start === null || typeof status.effective_start === "string") && (status.effective_end === null || typeof status.effective_end === "string") && (status.source_event_id === null || typeof status.source_event_id === "string") && (status.reason_code === null || typeof status.reason_code === "string") && Array.isArray(status.limitations) && status.limitations.every((limitation) => typeof limitation === "string");
  const distribution = item.defect_distribution;
  const validDistribution = distribution !== null && distribution !== undefined && typeof distribution === "object" && typeof distribution.equipment_id === "string" && (distribution.lot_id === null || typeof distribution.lot_id === "string") && typeof distribution.start === "string" && typeof distribution.end === "string" && Number.isInteger(distribution.failed_wafers) && Number.isInteger(distribution.classified_defect_count) && Number.isInteger(distribution.unclassified_failed_wafers) && Array.isArray(distribution.items) && distribution.items.every((entry) => typeof entry.category === "string" && Number.isInteger(entry.count) && (entry.share === null || typeof entry.share === "number") && Number.isInteger(entry.rank)) && Array.isArray(distribution.limitations) && distribution.limitations.every((limitation) => typeof limitation === "string");
  const documentSearch = item.document_search;
  const validDocumentSearch = documentSearch !== null && documentSearch !== undefined && typeof documentSearch === "object" && typeof documentSearch.query === "string" && Array.isArray(documentSearch.sources) && documentSearch.sources.every((source) => typeof source.source_id === "string" && (source.source === "built_in" || source.source === "local_upload") && typeof source.title === "string" && typeof source.section === "string" && typeof source.relative_path === "string" && typeof source.excerpt === "string" && typeof source.score === "number" && source.score >= 0 && source.score <= 1) && Array.isArray(documentSearch.limitations) && documentSearch.limitations.every((limitation) => typeof limitation === "string");
  return validSummary || validStatus || validDistribution || validDocumentSearch || item.tool_error !== null;
}
function parseStreamEvent(event: string, data: string): MessageStreamEvent {
  const value: unknown = JSON.parse(data);
  if (event === "message_started" && typeof value === "object" && value !== null && isMessage((value as { user_message: unknown }).user_message)) return { type: event, user_message: (value as { user_message: Message }).user_message };
  if (event === "routing_started" && isRoutingPayload(value)) return { type: event, label: value.label };
  if (event === "routing_retry" && isRoutingPayload(value) && typeof value.retry_count === "number") return { type: event, label: value.label, retry_count: value.retry_count };
  if (event === "routing_decided" && isRoutingPayload(value) && isRouteIntent(value.route) && isRoutingReasonCode(value.reason_code) && typeof value.retry_count === "number") return { type: event, label: value.label, route: value.route, reason_code: value.reason_code, retry_count: value.retry_count };
  if (event === "clarification_required" && isRoutingPayload(value) && isRoutingReasonCode(value.reason_code)) return { type: event, label: value.label, reason_code: value.reason_code };
  if (event === "routing_fallback_used" && isRoutingPayload(value) && isRoutingReasonCode(value.reason_code)) return { type: event, label: value.label, reason_code: value.reason_code };
  if (event === "token" && typeof value === "object" && value !== null && typeof (value as { text: unknown }).text === "string") return { type: event, text: (value as { text: string }).text };
  if (event === "tool_call_started" && typeof value === "object" && value !== null && typeof (value as { name: unknown }).name === "string" && typeof (value as { arguments: unknown }).arguments === "object") return { type: event, name: (value as { name: string }).name, arguments: (value as { arguments: Record<string, unknown> }).arguments };
  if (event === "tool_result" && typeof value === "object" && value !== null && isEvidence(value)) return { type: event, evidence: value };
  if (event === "message_completed" && typeof value === "object" && value !== null && isMessage((value as { assistant_message: unknown }).assistant_message)) return { type: event, assistant_message: (value as { assistant_message: Message }).assistant_message };
  if (event === "error" && typeof value === "object" && value !== null && typeof (value as { code: unknown }).code === "string" && typeof (value as { message: unknown }).message === "string") return { type: event, code: (value as { code: string }).code, message: (value as { message: string }).message };
  throw new Error("invalid streaming event");
}
function isRoutingPayload(value: unknown): value is { label: string; route?: unknown; reason_code?: unknown; retry_count?: unknown } {
  return typeof value === "object" && value !== null && typeof (value as { label?: unknown }).label === "string";
}
const ROUTE_INTENTS = new Set<RouteIntent>(["general", "production_summary", "equipment_status", "defect_distribution", "document_search", "combined", "clarification", "unsupported"]);
const ROUTING_REASON_CODES = new Set<RoutingReasonCode>(["general_request", "production_request", "equipment_status_request", "defect_distribution_request", "document_request", "combined_request", "clarification_required", "unsupported_capability", "ambiguous_request"]);
function isRouteIntent(value: unknown): value is RouteIntent {
  return typeof value === "string" && ROUTE_INTENTS.has(value as RouteIntent);
}
function isRoutingReasonCode(value: unknown): value is RoutingReasonCode {
  return typeof value === "string" && ROUTING_REASON_CODES.has(value as RoutingReasonCode);
}
export function buildMessagesUrl(baseUrl: string | undefined, conversationId: string): string {
  const base = baseUrl?.trim() ? baseUrl.replace(/\/+$/, "") : "/api";
  return `${base}/conversations/${conversationId}/messages`;
}
async function request<T>(fetchImplementation: ConversationFetch, input: string, init: RequestInit, validate: (value: unknown) => value is T): Promise<T> {
  try {
    const response = await fetchImplementation(input, init);
    if (!response.ok) throw new Error("unsuccessful response");
    const payload: unknown = await response.json();
    if (!validate(payload)) throw new Error("invalid response");
    return payload;
  } catch (error) { throw new MessageApiError(error); }
}
export function listMessages(conversationId: string, fetchImplementation: ConversationFetch = fetch): Promise<Message[]> {
  return request(fetchImplementation, buildMessagesUrl(import.meta.env.VITE_API_BASE_URL, conversationId), { headers: { Accept: "application/json" } }, (value): value is Message[] => Array.isArray(value) && value.every(isMessage));
}
export function sendMessage(conversationId: string, content: string, fetchImplementation: ConversationFetch = fetch): Promise<MessageExchange> {
  const trimmed = content.trim();
  if (!trimmed) return Promise.reject(new MessageApiError(new Error("content is blank")));
  return request(fetchImplementation, buildMessagesUrl(import.meta.env.VITE_API_BASE_URL, conversationId), { method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json" }, body: JSON.stringify({ content: trimmed }) }, isExchange);
}

export async function* streamMessage(conversationId: string, content: string, signal: AbortSignal, fetchImplementation: ConversationFetch = fetch): AsyncGenerator<MessageStreamEvent> {
  const trimmed = content.trim();
  if (!trimmed) throw new MessageApiError(new Error("content is blank"));
  try {
    const response = await fetchImplementation(`${buildMessagesUrl(import.meta.env.VITE_API_BASE_URL, conversationId)}/stream`, { method: "POST", signal, headers: { Accept: "text/event-stream", "Content-Type": "application/json" }, body: JSON.stringify({ content: trimmed }) });
    if (!response.ok || !response.body) throw new Error("unsuccessful streaming response");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      while (true) {
        const chunk = await reader.read();
        buffer += decoder.decode(chunk.value, { stream: !chunk.done });
        let boundary = buffer.indexOf("\n\n");
        while (boundary >= 0) {
          const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2); boundary = buffer.indexOf("\n\n");
          const event = frame.match(/^event:\s*(.+)$/m)?.[1]; const data = frame.match(/^data:\s*(.+)$/m)?.[1];
          if (event && data) yield parseStreamEvent(event, data);
        }
        if (chunk.done) break;
      }
    } finally { reader.releaseLock(); }
  } catch (error) {
    if (error instanceof MessageApiError) throw error;
    throw new MessageApiError(error);
  }
}
