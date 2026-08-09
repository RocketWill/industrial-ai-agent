import type { FetchImplementation } from "./health";

export type DocumentType = "alarm_guide" | "operator_sop" | "maintenance_guide" | "uploaded_document";
export type DocumentSource = "built_in" | "local_upload";
export type DocumentStatus = "ready";

export type DocumentMetadata = {
  document_id: string;
  title: string;
  document_type: DocumentType;
  source: DocumentSource;
  filename: string;
  relative_path: string;
  size_bytes: number;
  status: DocumentStatus;
  deletable: boolean;
  synthetic_demo: boolean;
};

export type FullDocument = DocumentMetadata & {
  markdown: string;
};

/** Backwards-compatible name for the full document used by the source viewer. */
export type RegistryDocument = FullDocument;

export class DocumentApiError extends Error {
  readonly cause: unknown;

  constructor(readonly status: number | null, message = "Document request failed", cause: unknown = null, readonly documents: DocumentMetadata[] = []) {
    super(message);
    this.name = "DocumentApiError";
    this.cause = cause;
  }
}

export class DocumentReadError extends DocumentApiError {
  constructor(status: number | null, cause: unknown = null) {
    super(status, "Document could not be loaded", cause);
    this.name = "DocumentReadError";
  }
}

function isDocumentMetadata(value: unknown): value is DocumentMetadata {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  return typeof item.document_id === "string" &&
    typeof item.title === "string" &&
    ["alarm_guide", "operator_sop", "maintenance_guide", "uploaded_document"].includes(String(item.document_type)) &&
    ["built_in", "local_upload"].includes(String(item.source)) &&
    typeof item.filename === "string" &&
    typeof item.relative_path === "string" &&
    typeof item.size_bytes === "number" && Number.isInteger(item.size_bytes) && item.size_bytes >= 0 &&
    item.status === "ready" &&
    typeof item.deletable === "boolean" &&
    typeof item.synthetic_demo === "boolean";
}

function isFullDocument(value: unknown): value is FullDocument {
  return isDocumentMetadata(value) && typeof (value as { markdown?: unknown }).markdown === "string";
}

export function buildDocumentsUrl(baseUrl?: string): string {
  const base = baseUrl?.trim() ? baseUrl.replace(/\/+$/, "") : "/api";
  return `${base}/documents`;
}

async function requestJson<T>(
  fetchImplementation: FetchImplementation,
  input: RequestInfo | URL,
  init: RequestInit,
  validate: (value: unknown) => value is T,
  errorFactory: (status: number | null, cause?: unknown) => DocumentApiError,
): Promise<T> {
  try {
    const response = await fetchImplementation(input, init);
    if (!response.ok) throw errorFactory(response.status);
    const payload: unknown = await response.json();
    if (!validate(payload)) throw errorFactory(null);
    return payload;
  } catch (error) {
    if (error instanceof DocumentApiError) throw error;
    throw errorFactory(null, error);
  }
}

export function listDocuments(
  fetchImplementation: FetchImplementation = fetch,
): Promise<DocumentMetadata[]> {
  return (async () => {
    try {
      const response = await fetchImplementation(
        buildDocumentsUrl(import.meta.env.VITE_API_BASE_URL),
        { headers: { Accept: "application/json" } },
      );
      const payload: unknown = await response.json();
      if (response.ok) {
        if (!Array.isArray(payload) || !payload.every(isDocumentMetadata)) throw new DocumentApiError(null, "Document list request failed");
        return payload;
      }
      const unavailableDocuments = typeof payload === "object" && payload !== null && Array.isArray((payload as { documents?: unknown }).documents)
        && (payload as { documents: unknown[] }).documents.every(isDocumentMetadata)
        ? (payload as { documents: DocumentMetadata[] }).documents
        : [];
      throw new DocumentApiError(response.status, "Document list request failed", null, unavailableDocuments);
    } catch (error) {
      if (error instanceof DocumentApiError) throw error;
      throw new DocumentApiError(null, "Document list request failed", error);
    }
  })();
}

export function uploadDocument(
  file: File,
  fetchImplementation: FetchImplementation = fetch,
): Promise<DocumentMetadata> {
  const body = new FormData();
  body.append("file", file);
  return requestJson(
    fetchImplementation,
    buildDocumentsUrl(import.meta.env.VITE_API_BASE_URL),
    { method: "POST", headers: { Accept: "application/json" }, body },
    isDocumentMetadata,
    (status, cause) => new DocumentApiError(status, "Document upload request failed", cause),
  );
}

export async function deleteDocument(
  documentId: string,
  fetchImplementation: FetchImplementation = fetch,
): Promise<void> {
  try {
    const response = await fetchImplementation(
      `${buildDocumentsUrl(import.meta.env.VITE_API_BASE_URL)}/${encodeURIComponent(documentId)}`,
      { method: "DELETE", headers: { Accept: "application/json" } },
    );
    if (response.status !== 204) throw new DocumentApiError(response.status, "Document delete request failed");
    invalidateDocumentCache(documentId);
  } catch (error) {
    if (error instanceof DocumentApiError) throw error;
    throw new DocumentApiError(null, "Document delete request failed", error);
  }
}

export async function readDocument(
  documentId: string,
  fetchImplementation: FetchImplementation = fetch,
): Promise<FullDocument> {
  return requestJson(
    fetchImplementation,
    `${buildDocumentsUrl(import.meta.env.VITE_API_BASE_URL)}/${encodeURIComponent(documentId)}`,
    { headers: { Accept: "application/json" } },
    isFullDocument,
    (status, cause) => new DocumentReadError(status, cause),
  );
}

const documentCache = new Map<string, FullDocument>();

export function getCachedDocument(documentId: string): FullDocument | undefined {
  return documentCache.get(documentId);
}

export function cacheDocument(document: FullDocument): void {
  documentCache.set(document.document_id, document);
}

export function invalidateDocumentCache(documentId: string): void {
  documentCache.delete(documentId);
}

export function clearDocumentCache(): void {
  documentCache.clear();
}
