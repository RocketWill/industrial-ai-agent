import { describe, expect, it, beforeEach, vi } from "vitest";
import {
  cacheDocument,
  clearDocumentCache,
  deleteDocument,
  getCachedDocument,
  invalidateDocumentCache,
  listDocuments,
  readDocument,
  uploadDocument,
  type DocumentMetadata,
  type FullDocument,
} from "./documents";

const builtInDocument: DocumentMetadata = {
  document_id: "aoi-alarm-guide",
  title: "AOI Wafer Inspector Alarm Guide",
  document_type: "alarm_guide",
  source: "built_in",
  filename: "aoi-wafer-inspector-alarm-guide.md",
  relative_path: "data/synthetic/documents/aoi-wafer-inspector-alarm-guide.md",
  size_bytes: 128,
  status: "ready",
  deletable: false,
  synthetic_demo: true,
};

const uploadedDocument: DocumentMetadata = {
  document_id: "uploaded-local-guide",
  title: "Local Guide",
  document_type: "uploaded_document",
  source: "local_upload",
  filename: "Local Guide.md",
  relative_path: "uploads/uploaded-local-guide.md",
  size_bytes: 96,
  status: "ready",
  deletable: true,
  synthetic_demo: false,
};

const fullDocument: FullDocument = {
  ...uploadedDocument,
  markdown: "# Local Guide\n\n## Recovery\n\nCheck the signal window.\n",
};

function response(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response;
}

describe("document API client", () => {
  beforeEach(() => {
    clearDocumentCache();
  });

  it("lists and validates document metadata", async () => {
    const request = vi.fn().mockResolvedValue(response([builtInDocument]));

    await expect(listDocuments(request)).resolves.toEqual([builtInDocument]);
    expect(request).toHaveBeenCalledWith("/api/documents", {
      headers: { Accept: "application/json" },
    });
  });

  it("uploads one Markdown file as multipart form data", async () => {
    const file = new File(["# Local Guide\n\n## Recovery\n\nCheck it."], "Local Guide.md", {
      type: "text/markdown",
    });
    const request = vi.fn().mockResolvedValue(response(uploadedDocument, 201));

    await expect(uploadDocument(file, request)).resolves.toEqual(uploadedDocument);

    const [, init] = request.mock.calls[0];
    expect(init?.method).toBe("POST");
    expect(init?.headers).toEqual({ Accept: "application/json" });
    expect(init?.body).toBeInstanceOf(FormData);
    expect((init?.body as FormData).get("file")).toBe(file);
    expect([...((init?.body as FormData).keys())]).toEqual(["file"]);
  });

  it("deletes a document only after receiving 204", async () => {
    const request = vi.fn().mockResolvedValue(response(null, 204));

    await expect(deleteDocument("uploaded-local-guide", request)).resolves.toBeUndefined();
    expect(request).toHaveBeenCalledWith("/api/documents/uploaded-local-guide", {
      method: "DELETE",
      headers: { Accept: "application/json" },
    });

    await expect(deleteDocument("uploaded-local-guide", vi.fn().mockResolvedValue(response(null, 200))))
      .rejects.toMatchObject({ status: 200 });
  });

  it("preserves HTTP status for UI error mapping", async () => {
    const file = new File(["# Local Guide"], "Local Guide.md", { type: "text/markdown" });

    await expect(listDocuments(vi.fn().mockResolvedValue(response({}, 503))))
      .rejects.toMatchObject({ status: 503 });
    await expect(uploadDocument(file, vi.fn().mockResolvedValue(response({}, 409))))
      .rejects.toMatchObject({ status: 409 });
    await expect(deleteDocument("aoi-alarm-guide", vi.fn().mockResolvedValue(response({}, 403))))
      .rejects.toMatchObject({ status: 403 });
    await expect(readDocument("missing", vi.fn().mockResolvedValue(response({}, 404))))
      .rejects.toMatchObject({ status: 404 });
  });

  it("retains built-ins when local upload state is unavailable", async () => {
    const request = vi.fn().mockResolvedValue(response({
      detail: "Local uploaded-document storage is unavailable",
      documents: [builtInDocument],
    }, 503));

    await expect(listDocuments(request)).rejects.toMatchObject({
      status: 503,
      documents: [builtInDocument],
    });
  });

  it("reads metadata and Markdown for a local upload", async () => {
    const request = vi.fn().mockResolvedValue(response(fullDocument));

    await expect(readDocument("uploaded-local-guide", request)).resolves.toEqual(fullDocument);
    expect(request).toHaveBeenCalledWith("/api/documents/uploaded-local-guide", {
      headers: { Accept: "application/json" },
    });
  });

  it("rejects malformed payloads without inventing metadata", async () => {
    await expect(listDocuments(vi.fn().mockResolvedValue(response([{}]))))
      .rejects.toMatchObject({ status: null });
    await expect(readDocument("broken", vi.fn().mockResolvedValue(response({ ...uploadedDocument }))))
      .rejects.toMatchObject({ status: null });
  });

  it("provides an app-owned cache seam that can invalidate deleted documents", () => {
    cacheDocument(fullDocument);
    expect(getCachedDocument(fullDocument.document_id)).toEqual(fullDocument);

    invalidateDocumentCache(fullDocument.document_id);

    expect(getCachedDocument(fullDocument.document_id)).toBeUndefined();
  });
});
