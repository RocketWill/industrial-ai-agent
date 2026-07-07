import type { ConversationFetch } from "./conversations";

export type Message = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type MessageExchange = { user_message: Message; assistant_message: Message };

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
