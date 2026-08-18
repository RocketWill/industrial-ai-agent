import { useCallback, useEffect, useRef, useState } from "react";
import * as messageApi from "../api/messages";
import type { CombinedEvidence, CombinedEvidencePath, Message, MessageExchange, MessageStreamEvent, ProductionEvidence } from "../api/messages";

export type MessageApi = {
  listMessages: (conversationId: string) => Promise<Message[]>;
  sendMessage: (conversationId: string, content: string) => Promise<MessageExchange>;
  streamMessage?: (conversationId: string, content: string, signal: AbortSignal) => AsyncGenerator<MessageStreamEvent>;
};
export type MessageState = {
  messages: Message[]; evidence: ProductionEvidence | null; combinedEvidence: CombinedEvidence | null; runState: AssistantRunState; isLoading: boolean; isSending: boolean; isStreaming: boolean; error: string | null; draft: string;
  workingNotes: WorkingNotesState | null; setWorkingNotesOpen: (open: boolean) => void;
  setDraft: (value: string) => void; reload: () => Promise<void>; send: (contentOverride?: string) => Promise<boolean>; cancelStreaming: () => void;
};

export type AssistantRunPhase = "idle" | "routing" | "routing_retry" | "generating" | "calling_tool" | "evidence_received" | "clarification" | "success" | "cancelled" | "failed";
export type AssistantRunState = { phase: AssistantRunPhase; label: string | null };
export type WorkingNotesStatus = "active" | "complete" | "truncated" | "interrupted";
export type WorkingNotesState = { content: string; status: WorkingNotesStatus; open: boolean };

const idleRun: AssistantRunState = { phase: "idle", label: null };
const placeholderId = "00000000-0000-1000-8000-000000000000";

export function isProductionQuery(content: string): boolean {
  const normalized = content.toLowerCase();
  return ["yield", "defect", "alarm", "production", "inspection"].some((term) => normalized.includes(term));
}

const defaultApi: MessageApi = { listMessages: (id) => messageApi.listMessages(id), sendMessage: (id, content) => messageApi.sendMessage(id, content), streamMessage: (id, content, signal) => messageApi.streamMessage(id, content, signal) };

export function useMessages(conversationId: string | null, api: MessageApi = defaultApi): MessageState {
  const [messages, setMessages] = useState<Message[]>([]);
  const [evidence, setEvidence] = useState<ProductionEvidence | null>(null);
  const [combinedEvidence, setCombinedEvidence] = useState<CombinedEvidence | null>(null);
  const [runState, setRunState] = useState<AssistantRunState>(idleRun);
  const [isLoading, setLoading] = useState(false);
  const [isSending, setSending] = useState(false);
  const [isStreaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [workingNotes, setWorkingNotes] = useState<WorkingNotesState | null>(null);
  const sequence = useRef(0);
  const busy = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const activeConversation = useRef<string | null>(conversationId);
  useEffect(() => { activeConversation.current = conversationId; controller.current?.abort(); controller.current = null; setRunState(idleRun); setStreaming(false); setSending(false); busy.current = false; }, [conversationId]);
  const reload = useCallback(async () => {
    const id = conversationId; if (!id || busy.current) return;
    const token = ++sequence.current; busy.current = true; setLoading(true); setError(null); setMessages([]); setEvidence(null); setCombinedEvidence(null); setWorkingNotes(null);
    try { const next = await api.listMessages(id); if (token === sequence.current) setMessages(next); }
    catch { if (token === sequence.current) setError("Unable to load messages"); }
    finally { if (token === sequence.current) setLoading(false); busy.current = false; }
  }, [api, conversationId]);
  useEffect(() => { setMessages([]); setEvidence(null); setCombinedEvidence(null); setWorkingNotes(null); setRunState(idleRun); setError(null); if (conversationId) void reload(); }, [conversationId, reload]);
  const setWorkingNotesOpen = useCallback((open: boolean) => {
    setWorkingNotes((current) => current ? { ...current, open } : current);
  }, []);
  const send = useCallback(async (contentOverride?: string) => {
    const id = conversationId; const content = (contentOverride ?? draft).trim();
    if (!id || !content || busy.current) return false;
    busy.current = true; setSending(true); setError(null); setEvidence(null); setCombinedEvidence(null); setWorkingNotes(null); setRunState({ phase: "generating", label: "Generating response" });
    try {
      if (!api.streamMessage) {
        const exchange = await api.sendMessage(id, content); setMessages((current) => [...current, exchange.user_message, exchange.assistant_message]); setRunState({ phase: "success", label: null }); setDraft(""); return true;
      }
      const abortController = new AbortController(); controller.current = abortController; setStreaming(true);
      const placeholder: Message = { id: placeholderId, conversation_id: id, role: "assistant", content: "", created_at: new Date().toISOString(), suggested_actions: [] };
      setMessages((current) => [...current, placeholder]);
      for await (const event of api.streamMessage(id, content, abortController.signal)) {
        if (activeConversation.current !== id) break;
        if (event.type === "message_started") {
          setMessages((current) => {
            const next = [...current];
            const placeholderIndex = next.findIndex((message) => message.id === placeholder.id);
            next.splice(placeholderIndex < 0 ? next.length : placeholderIndex, 0, event.user_message);
            return next;
          });
        } else if (event.type === "routing_started") {
          setRunState({ phase: "routing", label: event.label });
        } else if (event.type === "routing_retry" || event.type === "routing_fallback_used") {
          setRunState({ phase: "routing_retry", label: event.label });
        } else if (event.type === "routing_decided") {
          setRunState({ phase: "generating", label: event.label });
        } else if (event.type === "clarification_required") {
          setRunState({ phase: "clarification", label: event.label });
        } else if (event.type === "reasoning_delta") {
          if (event.content) {
            setWorkingNotes((current) => current
              ? { ...current, content: current.content + event.content }
              : { content: event.content, status: "active", open: true });
          }
        } else if (event.type === "reasoning_truncated") {
          setWorkingNotes((current) => current ? { ...current, status: "truncated" } : current);
        } else if (event.type === "token") {
          if (event.text) {
            setWorkingNotes((current) => current
              ? { ...current, status: current.status === "active" ? "complete" : current.status, open: false }
              : current);
          }
          setMessages((current) => current.map((message) => message.id === placeholder.id ? { ...message, content: message.content + event.text } : message));
        } else if (event.type === "tool_call_started") {
          setRunState({ phase: "calling_tool", label: `Calling ${event.name}` });
          if (event.path === "manufacturing") {
            const manufacturingKind = event.name === "get_equipment_status" ? "equipment_status" : event.name === "get_defect_distribution" ? "defect_distribution" : "production";
            const loading: CombinedEvidencePath = { status: "loading", result: null, error_code: null };
            const notRun: CombinedEvidencePath = { status: "not_run", result: null, error_code: null };
            setCombinedEvidence({ manufacturing_kind: manufacturingKind, manufacturing: loading, documents: notRun, document_query: "", answer_status: "fallback" } as CombinedEvidence);
          }
          if (event.path === "documents" && typeof event.arguments.query === "string") {
            setCombinedEvidence((current) => current ? { ...current, documents: { status: "loading", result: null, error_code: null }, document_query: event.arguments.query as string } as CombinedEvidence : current);
          }
        } else if (event.type === "tool_result") {
          setEvidence(event.evidence);
          setRunState({ phase: "evidence_received", label: "Evidence received" });
        } else if (event.type === "combined_tool_result") {
          const notRun: CombinedEvidencePath = { status: "not_run", result: null, error_code: null };
          setCombinedEvidence((current) => ({
            manufacturing_kind: event.manufacturing_kind,
            manufacturing: event.path === "manufacturing" ? event.outcome : current?.manufacturing ?? notRun,
            documents: event.path === "documents" ? event.outcome : current?.documents ?? notRun,
            document_query: current?.document_query ?? "",
            answer_status: current?.answer_status ?? "fallback",
          } as CombinedEvidence));
          setRunState({ phase: "evidence_received", label: `${event.path === "manufacturing" ? "Manufacturing" : "Document"} evidence received` });
        } else if (event.type === "combined_evidence_completed") {
          setCombinedEvidence((current) => current ? { ...current, answer_status: event.answer_status } : current);
        } else if (event.type === "message_completed") {
          setMessages((current) => current.map((message) => message.id === placeholder.id ? event.assistant_message : message)); setWorkingNotes((current) => current && current.status === "active" ? { ...current, status: "complete" } : current); setEvidence(null); setCombinedEvidence(null); setRunState({ phase: "success", label: null }); setDraft("");
        } else if (event.type === "error") { throw new Error(event.message); }
      }
      return true;
    }
    catch {
      setWorkingNotes((current) => current ? { ...current, status: "interrupted" } : current);
      if (controller.current?.signal.aborted) {
        setMessages((current) => current.map((message) => message.id === placeholderId ? { ...message, content: "Generation stopped." } : message));
        setRunState({ phase: "cancelled", label: "Generation stopped" });
      } else {
        setMessages((current) => current.map((message) => message.id === placeholderId ? { ...message, content: "Response unavailable." } : message));
        setRunState({ phase: "failed", label: "Response unavailable" });
        setError("Unable to send message");
      }
      return false;
    }
    finally { controller.current = null; busy.current = false; setSending(false); setStreaming(false); }
  }, [api, conversationId, draft]);
  const cancelStreaming = useCallback(() => {
    setWorkingNotes((current) => current ? { ...current, status: "interrupted" } : current);
    setMessages((current) => current.map((message) => message.id === placeholderId ? { ...message, content: "Generation stopped." } : message));
    setRunState({ phase: "cancelled", label: "Generation stopped" });
    controller.current?.abort();
  }, []);
  return { messages, evidence, combinedEvidence, runState, isLoading, isSending, isStreaming, error, draft, workingNotes, setWorkingNotesOpen, setDraft, reload, send, cancelStreaming };
}
