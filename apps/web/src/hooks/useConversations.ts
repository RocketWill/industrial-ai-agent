import { useCallback, useEffect, useRef, useState } from "react";
import * as conversationApi from "../api/conversations";
import type { Conversation } from "../api/conversations";

export type ConversationApi = {
  listConversations: () => Promise<Conversation[]>;
  createConversation: (title?: string) => Promise<Conversation>;
  deleteConversation: (id: string) => Promise<void>;
};

export type ConversationState = {
  conversations: Conversation[];
  selectedConversationId: string | null;
  isLoading: boolean;
  isMutating: boolean;
  error: string | null;
  selectConversation: (id: string) => void;
  createConversation: (title?: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  reload: () => Promise<void>;
};

export function useConversations(api: ConversationApi = conversationApi): ConversationState {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversationId, setSelected] = useState<string | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [isMutating, setMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);
  const reload = useCallback(async () => {
    if (busy.current) return;
    busy.current = true; setLoading(true); setError(null);
    try {
      const items = await api.listConversations();
      setConversations(items);
      setSelected((current) => current && items.some((item) => item.id === current) ? current : items[0]?.id ?? null);
    } catch { setError("Unable to load conversations"); } finally { busy.current = false; setLoading(false); }
  }, [api]);
  useEffect(() => { void reload(); }, [reload]);
  const create = useCallback(async (title?: string) => {
    if (busy.current) return; busy.current = true; setMutating(true); setError(null);
    try { const item = await api.createConversation(title); setConversations((items) => [item, ...items]); setSelected(item.id); }
    catch { setError("Unable to create conversation"); } finally { busy.current = false; setMutating(false); }
  }, [api]);
  const remove = useCallback(async (id: string) => {
    if (busy.current) return; busy.current = true; setMutating(true); setError(null);
    try { await api.deleteConversation(id); setConversations((items) => { const next = items.filter((item) => item.id !== id); setSelected((current) => current === id ? next[0]?.id ?? null : current); return next; }); }
    catch { setError("Unable to delete conversation"); } finally { busy.current = false; setMutating(false); }
  }, [api]);
  return { conversations, selectedConversationId, isLoading, isMutating, error, selectConversation: setSelected, createConversation: create, deleteConversation: remove, reload };
}
