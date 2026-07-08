import type { ConversationFetch } from "./conversations";

export type Message = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type MessageExchange = { user_message: Message; assistant_message: Message };
export type MessageStreamEvent =
  | { type: "message_started"; user_message: Message }
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
  return typeof value === "object" && value !== null && isMessage((value as MessageExchange).user_message) && isMessage((value as MessageExchange).assistant_message);
}
function parseStreamEvent(event: string, data: string): MessageStreamEvent {
  const value: unknown = JSON.parse(data);
  if (event === "message_started" && typeof value === "object" && value !== null && isMessage((value as { user_message: unknown }).user_message)) return { type: event, user_message: (value as { user_message: Message }).user_message };
  if (event === "token" && typeof value === "object" && value !== null && typeof (value as { text: unknown }).text === "string") return { type: event, text: (value as { text: string }).text };
  if (event === "message_completed" && typeof value === "object" && value !== null && isMessage((value as { assistant_message: unknown }).assistant_message)) return { type: event, assistant_message: (value as { assistant_message: Message }).assistant_message };
  if (event === "error" && typeof value === "object" && value !== null && typeof (value as { code: unknown }).code === "string" && typeof (value as { message: unknown }).message === "string") return { type: event, code: (value as { code: string }).code, message: (value as { message: string }).message };
  throw new Error("invalid streaming event");
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
