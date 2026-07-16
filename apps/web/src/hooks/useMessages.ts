import { useCallback, useEffect, useRef, useState } from "react";
import * as messageApi from "../api/messages";
import type { Message, MessageExchange, MessageStreamEvent } from "../api/messages";

export type MessageApi = {
  listMessages: (conversationId: string) => Promise<Message[]>;
  sendMessage: (conversationId: string, content: string) => Promise<MessageExchange>;
  streamMessage?: (conversationId: string, content: string, signal: AbortSignal) => AsyncGenerator<MessageStreamEvent>;
};
export type MessageState = {
  messages: Message[]; isLoading: boolean; isSending: boolean; isStreaming: boolean; error: string | null; draft: string;
  setDraft: (value: string) => void; reload: () => Promise<void>; send: () => Promise<boolean>; cancelStreaming: () => void;
};

export function isProductionQuery(content: string): boolean {
  const normalized = content.toLowerCase();
  return ["yield", "defect", "alarm", "production", "inspection"].some((term) => normalized.includes(term));
}

const defaultApi: MessageApi = { listMessages: (id) => messageApi.listMessages(id), sendMessage: (id, content) => messageApi.sendMessage(id, content), streamMessage: (id, content, signal) => messageApi.streamMessage(id, content, signal) };

export function useMessages(conversationId: string | null, api: MessageApi = defaultApi): MessageState {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setLoading] = useState(false);
  const [isSending, setSending] = useState(false);
  const [isStreaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const sequence = useRef(0);
  const busy = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const activeConversation = useRef<string | null>(conversationId);
  useEffect(() => { activeConversation.current = conversationId; controller.current?.abort(); controller.current = null; setStreaming(false); setSending(false); busy.current = false; }, [conversationId]);
  const reload = useCallback(async () => {
    const id = conversationId; if (!id || busy.current) return;
    const token = ++sequence.current; busy.current = true; setLoading(true); setError(null); setMessages([]);
    try { const next = await api.listMessages(id); if (token === sequence.current) setMessages(next); }
    catch { if (token === sequence.current) setError("Unable to load messages"); }
    finally { if (token === sequence.current) setLoading(false); busy.current = false; }
  }, [api, conversationId]);
  useEffect(() => { setMessages([]); setError(null); if (conversationId) void reload(); }, [conversationId, reload]);
  const send = useCallback(async () => {
    const id = conversationId; const content = draft.trim();
    if (!id || !content || busy.current) return false;
    busy.current = true; setSending(true); setError(null);
    try {
      if (!api.streamMessage || isProductionQuery(content)) {
        const exchange = await api.sendMessage(id, content); setMessages((current) => [...current, exchange.user_message, exchange.assistant_message]); setDraft(""); return true;
      }
      const abortController = new AbortController(); controller.current = abortController; setStreaming(true);
      let assistantIndex = -1;
      for await (const event of api.streamMessage(id, content, abortController.signal)) {
        if (activeConversation.current !== id) break;
        if (event.type === "message_started") {
          const placeholder: Message = { id: "00000000-0000-1000-8000-000000000000", conversation_id: id, role: "assistant", content: "", created_at: new Date().toISOString() };
          setMessages((current) => { assistantIndex = current.length + 1; return [...current, event.user_message, placeholder]; });
        } else if (event.type === "token") {
          setMessages((current) => current.map((message, index) => index === assistantIndex ? { ...message, content: message.content + event.text } : message));
        } else if (event.type === "message_completed") {
          setMessages((current) => current.map((message, index) => index === assistantIndex ? event.assistant_message : message)); setDraft("");
        } else if (event.type === "error") { throw new Error(event.message); }
      }
      return true;
    }
    catch { setError("Unable to send message"); return false; }
    finally { controller.current = null; busy.current = false; setSending(false); setStreaming(false); }
  }, [api, conversationId, draft]);
  const cancelStreaming = useCallback(() => { controller.current?.abort(); }, []);
  return { messages, isLoading, isSending, isStreaming, error, draft, setDraft, reload, send, cancelStreaming };
}
