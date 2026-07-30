import { useCallback, useEffect, useRef, useState } from "react";
import * as documentApi from "../api/documents";
import {
  DocumentApiError,
  invalidateDocumentCache,
  type DocumentMetadata,
} from "../api/documents";

export type DocumentApi = {
  listDocuments: () => Promise<DocumentMetadata[]>;
  uploadDocument: (file: File) => Promise<DocumentMetadata>;
  deleteDocument: (documentId: string) => Promise<void>;
};

export type DocumentMutationState = "idle" | "uploading" | "indexing" | "ready" | "failed";

export type DocumentState = {
  documents: DocumentMetadata[];
  isLoading: boolean;
  loadError: DocumentApiError | null;
  mutationState: DocumentMutationState;
  mutationError: DocumentApiError | null;
  reload: () => Promise<void>;
  upload: (file: File) => Promise<boolean>;
  remove: (documentId: string) => Promise<boolean>;
};

const defaultApi: DocumentApi = {
  listDocuments: () => documentApi.listDocuments(),
  uploadDocument: (file) => documentApi.uploadDocument(file),
  deleteDocument: (documentId) => documentApi.deleteDocument(documentId),
};

function asDocumentApiError(error: unknown): DocumentApiError {
  return error instanceof DocumentApiError
    ? error
    : new DocumentApiError(null, "Document request failed", error);
}

export function useDocuments(api: DocumentApi = defaultApi): DocumentState {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [isLoading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<DocumentApiError | null>(null);
  const [mutationState, setMutationState] = useState<DocumentMutationState>("idle");
  const [mutationError, setMutationError] = useState<DocumentApiError | null>(null);
  const isMounted = useRef(true);
  const loadBusy = useRef(false);
  const mutationBusy = useRef(false);
  const revision = useRef(0);

  useEffect(() => () => {
    isMounted.current = false;
  }, []);

  const reload = useCallback(async () => {
    if (loadBusy.current || mutationBusy.current) return;
    loadBusy.current = true;
    const token = ++revision.current;
    setLoading(true);
    setLoadError(null);
    try {
      const next = await api.listDocuments();
      if (isMounted.current && token === revision.current) setDocuments(next);
    } catch (error) {
      if (isMounted.current && token === revision.current) {
        const documentError = asDocumentApiError(error);
        if (documentError.documents.length > 0) setDocuments(documentError.documents);
        setLoadError(documentError);
      }
    } finally {
      if (isMounted.current && token === revision.current) setLoading(false);
      loadBusy.current = false;
    }
  }, [api]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const mutate = useCallback(async (
    action: () => Promise<unknown>,
    documentId?: string,
  ): Promise<boolean> => {
    if (loadBusy.current || mutationBusy.current) return false;
    mutationBusy.current = true;
    const token = ++revision.current;
    setMutationState("uploading");
    setMutationError(null);
    setLoadError(null);
    try {
      await action();
      if (!isMounted.current) return false;
      if (documentId) invalidateDocumentCache(documentId);
      setMutationState("indexing");
      const next = await api.listDocuments();
      if (isMounted.current && token === revision.current) {
        setDocuments(next);
        setMutationState("ready");
      }
      return true;
    } catch (error) {
      if (isMounted.current && token === revision.current) {
        setMutationState("failed");
        setMutationError(asDocumentApiError(error));
      }
      return false;
    } finally {
      mutationBusy.current = false;
    }
  }, [api]);

  const upload = useCallback((file: File) => (
    mutate(() => api.uploadDocument(file))
  ), [api, mutate]);

  const remove = useCallback((documentId: string) => (
    mutate(() => api.deleteDocument(documentId), documentId)
  ), [api, mutate]);

  return {
    documents,
    isLoading,
    loadError,
    mutationState,
    mutationError,
    reload,
    upload,
    remove,
  };
}
