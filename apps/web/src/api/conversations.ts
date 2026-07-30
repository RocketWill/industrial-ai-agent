export type Conversation = {
  id: string;
  title: string;
  created_at: string;
};

export type ConversationFetch = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

export class ConversationApiError extends Error {
  readonly cause: unknown;

  constructor(cause: unknown) {
    super("Conversation request failed");
    this.name = "ConversationApiError";
    this.cause = cause;
  }
}

export function buildConversationsUrl(baseUrl?: string): string {
  if (!baseUrl?.trim()) return "/api/conversations";
  return `${baseUrl.replace(/\/+$/, "")}/conversations`;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isConversation(value: unknown): value is Conversation {
  return typeof value === "object" && value !== null &&
    typeof (value as Conversation).id === "string" && UUID_PATTERN.test((value as Conversation).id) &&
    typeof (value as Conversation).title === "string" && (value as Conversation).title.trim().length >= 1 && (value as Conversation).title.trim().length <= 200 &&
    typeof (value as Conversation).created_at === "string" && !Number.isNaN(Date.parse((value as Conversation).created_at));
}

async function requestJson<T>(fetchImplementation: ConversationFetch, input: RequestInfo | URL, init?: RequestInit, validate?: (value: unknown) => value is T): Promise<T> {
  try {
    const response = await fetchImplementation(input, init);
    if (!response.ok) throw new Error("unsuccessful response");
    const payload: unknown = await response.json();
    if (!validate || !validate(payload)) throw new Error("invalid response");
    return payload;
  } catch (error) {
    throw error instanceof ConversationApiError ? error : new ConversationApiError(error);
  }
}

export function listConversations(fetchImplementation: ConversationFetch = fetch): Promise<Conversation[]> {
  return requestJson(fetchImplementation, buildConversationsUrl(import.meta.env.VITE_API_BASE_URL), { headers: { Accept: "application/json" } }, (value): value is Conversation[] => Array.isArray(value) && value.every(isConversation));
}

export function createConversation(title = "New conversation", fetchImplementation: ConversationFetch = fetch): Promise<Conversation> {
  const trimmedTitle = title.trim() || "New conversation";
  return requestJson(fetchImplementation, buildConversationsUrl(import.meta.env.VITE_API_BASE_URL), { method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json" }, body: JSON.stringify({ title: trimmedTitle }) }, isConversation);
}

export async function deleteConversation(conversationId: string, fetchImplementation: ConversationFetch = fetch): Promise<void> {
  try {
    const response = await fetchImplementation(`${buildConversationsUrl(import.meta.env.VITE_API_BASE_URL)}/${conversationId}`, { method: "DELETE", headers: { Accept: "application/json" } });
    if (response.status !== 204) throw new Error("unsuccessful response");
  } catch (error) {
    throw error instanceof ConversationApiError ? error : new ConversationApiError(error);
  }
}
