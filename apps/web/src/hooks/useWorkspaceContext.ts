import { useCallback, useEffect, useRef, useState } from "react";
import { getWorkspaceContext, updateWorkspaceContext, type WorkspaceContext, type WorkspaceContextUpdate } from "../api/context";
import { listSyntheticDevices, type SyntheticDevice } from "../api/devices";

export type WorkspaceContextState = { context: WorkspaceContext | null; devices: SyntheticDevice[]; devicesLoading: boolean; devicesError: string | null; isLoading: boolean; isSaving: boolean; error: string | null; reload: () => Promise<void>; save: (update: WorkspaceContextUpdate) => Promise<boolean> };

export function useWorkspaceContext(conversationId: string | null): WorkspaceContextState {
  const [context, setContext] = useState<WorkspaceContext | null>(null);
  const [isLoading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setSaving] = useState(false);
  const [devices, setDevices] = useState<SyntheticDevice[]>([]);
  const [devicesLoading, setDevicesLoading] = useState(false);
  const [devicesError, setDevicesError] = useState<string | null>(null);
  const sequence = useRef(0);
  const reload = useCallback(async () => {
    if (!conversationId) { setContext(null); setError(null); return; }
    const token = ++sequence.current;
    setLoading(true); setError(null);
    try { const next = await getWorkspaceContext(conversationId); if (token === sequence.current) setContext(next); }
    catch { if (token === sequence.current) setError("Unable to load workspace context"); }
    finally { if (token === sequence.current) setLoading(false); }
  }, [conversationId]);
  useEffect(() => { void reload(); if (!conversationId) return; setDevicesLoading(true); void listSyntheticDevices().then(setDevices).catch(() => setDevicesError("Unable to load synthetic devices")).finally(() => setDevicesLoading(false)); }, [conversationId, reload]);
  const save = useCallback(async (update: WorkspaceContextUpdate) => {
    if (!conversationId) return false;
    setSaving(true); setError(null);
    try { const next = await updateWorkspaceContext(conversationId, update); setContext(next); return true; }
    catch { setError("Unable to save workspace context"); return false; }
    finally { setSaving(false); }
  }, [conversationId]);
  return { context, devices, devicesLoading, devicesError, isLoading, isSaving, error, reload, save };
}
