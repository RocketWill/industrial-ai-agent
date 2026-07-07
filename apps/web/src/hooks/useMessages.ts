import { useCallback, useEffect, useRef, useState } from "react";
import * as messageApi from "../api/messages";
import type { Message, MessageExchange } from "../api/messages";

export type MessageApi = {
  listMessages: (conversationId: string) => Promise<Message[]>;
  sendMessage: (conversationId: string, content: string) => Promise<MessageExchange>;
};
export type MessageState = {
  messages: Message[]; isLoading: boolean; isSending: boolean; error: string | null; draft: string;
  setDraft: (value: string) => void; reload: () => Promise<void>; send: () => Promise<boolean>;
};

const defaultApi: MessageApi = { listMessages: (id) => messageApi.listMessages(id), sendMessage: (id, content) => messageApi.sendMessage(id, content) };

export function useMessages(conversationId: string | null, api: MessageApi = defaultApi): MessageState {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setLoading] = useState(false);
  const [isSending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const sequence = useRef(0);
  const busy = useRef(false);
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
    try { const exchange = await api.sendMessage(id, content); setMessages((current) => [...current, exchange.user_message, exchange.assistant_message]); setDraft(""); return true; }
    catch { setError("Unable to send message"); return false; }
    finally { busy.current = false; setSending(false); }
  }, [api, conversationId, draft]);
  return { messages, isLoading, isSending, error, draft, setDraft, reload, send };
}
