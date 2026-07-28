import type { FetchImplementation } from "./health";

export type RegistryDocument = {
  document_id: string;
  title: string;
  document_type: "alarm_guide" | "operator_sop" | "maintenance_guide";
  relative_path: string;
  markdown: string;
  synthetic_demo: true;
};

export class DocumentReadError extends Error {
  constructor(readonly status: number | null) {
    super("Document could not be loaded");
    this.name = "DocumentReadError";
  }
}

function isRegistryDocument(value: unknown): value is RegistryDocument {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  return typeof item.document_id === "string" && typeof item.title === "string" &&
    ["alarm_guide", "operator_sop", "maintenance_guide"].includes(String(item.document_type)) &&
    typeof item.relative_path === "string" && typeof item.markdown === "string" && item.synthetic_demo === true;
}

export async function readDocument(
  documentId: string,
  fetchImplementation: FetchImplementation = fetch,
): Promise<RegistryDocument> {
  try {
    const response = await fetchImplementation(`/api/documents/${encodeURIComponent(documentId)}`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new DocumentReadError(response.status);
    const payload: unknown = await response.json();
    if (!isRegistryDocument(payload)) throw new DocumentReadError(null);
    return payload;
  } catch (error) {
    if (error instanceof DocumentReadError) throw error;
    throw new DocumentReadError(null);
  }
}
