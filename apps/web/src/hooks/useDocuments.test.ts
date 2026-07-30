import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  cacheDocument,
  clearDocumentCache,
  getCachedDocument,
  DocumentApiError,
  type DocumentMetadata,
} from "../api/documents";
import { useDocuments, type DocumentApi } from "./useDocuments";

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

const fullDocument = {
  ...uploadedDocument,
  markdown: "# Local Guide\n\n## Recovery\n\nCheck it.\n",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("useDocuments", () => {
  beforeEach(() => {
    clearDocumentCache();
  });

  it("loads the list, exposes indexing during refresh, and ends ready", async () => {
    const refresh = deferred<DocumentMetadata[]>();
    const api: DocumentApi = {
      listDocuments: vi.fn()
        .mockResolvedValueOnce([builtInDocument])
        .mockReturnValueOnce(refresh.promise),
      uploadDocument: vi.fn().mockResolvedValue(uploadedDocument),
      deleteDocument: vi.fn(),
    };
    const { result } = renderHook(() => useDocuments(api));

    await waitFor(() => expect(result.current.documents).toEqual([builtInDocument]));
    expect(result.current.isLoading).toBe(false);

    let uploadRequest!: Promise<boolean>;
    act(() => {
      uploadRequest = result.current.upload(new File(["content"], "Local Guide.md"));
    });
    await waitFor(() => expect(result.current.mutationState).toBe("indexing"));
    expect(api.uploadDocument).toHaveBeenCalledTimes(1);
    expect(api.listDocuments).toHaveBeenCalledTimes(2);

    refresh.resolve([builtInDocument, uploadedDocument]);
    await act(async () => {
      await expect(uploadRequest).resolves.toBe(true);
    });

    expect(result.current.documents).toEqual([builtInDocument, uploadedDocument]);
    expect(result.current.mutationState).toBe("ready");
    expect(result.current.mutationError).toBeNull();
  });

  it("prevents overlapping mutations and allows a failed mutation to retry", async () => {
    const uploadRequest = deferred<DocumentMetadata>();
    const uploadDocument = vi.fn()
      .mockReturnValueOnce(uploadRequest.promise)
      .mockRejectedValueOnce(new DocumentApiError(503));
    const api: DocumentApi = {
      listDocuments: vi.fn().mockResolvedValue([builtInDocument]),
      uploadDocument,
      deleteDocument: vi.fn(),
    };
    const { result } = renderHook(() => useDocuments(api));
    await waitFor(() => expect(result.current.documents).toEqual([builtInDocument]));

    let firstUpload!: Promise<boolean>;
    act(() => {
      firstUpload = result.current.upload(new File(["content"], "Local Guide.md"));
    });
    await waitFor(() => expect(result.current.mutationState).toBe("uploading"));
    await act(async () => {
      await expect(result.current.upload(new File(["other"], "Other.md"))).resolves.toBe(false);
      await expect(result.current.remove("aoi-alarm-guide")).resolves.toBe(false);
    });
    expect(api.uploadDocument).toHaveBeenCalledTimes(1);
    expect(api.deleteDocument).not.toHaveBeenCalled();

    uploadRequest.resolve(uploadedDocument);
    await act(async () => {
      await expect(firstUpload).resolves.toBe(true);
    });
    expect(result.current.mutationState).toBe("ready");

    await act(async () => {
      await expect(result.current.upload(new File(["retry"], "Retry.md"))).resolves.toBe(false);
    });
    expect(result.current.mutationState).toBe("failed");
    expect(result.current.mutationError).toMatchObject({ status: 503 });

    uploadDocument.mockResolvedValueOnce(uploadedDocument);
    await act(async () => {
      await expect(result.current.upload(new File(["retry"], "Retry.md"))).resolves.toBe(true);
    });
    expect(result.current.mutationState).toBe("ready");
  });

  it("invalidates a deleted document cache before refreshing the list", async () => {
    cacheDocument(fullDocument);
    const refresh = deferred<DocumentMetadata[]>();
    const api: DocumentApi = {
      listDocuments: vi.fn().mockResolvedValueOnce([builtInDocument, uploadedDocument]).mockReturnValueOnce(refresh.promise),
      uploadDocument: vi.fn(),
      deleteDocument: vi.fn().mockResolvedValue(undefined),
    };
    const { result } = renderHook(() => useDocuments(api));
    await waitFor(() => expect(result.current.documents).toHaveLength(2));

    let deleteRequest!: Promise<boolean>;
    act(() => {
      deleteRequest = result.current.remove(uploadedDocument.document_id);
    });
    await waitFor(() => expect(result.current.mutationState).toBe("indexing"));
    expect(getCachedDocument(uploadedDocument.document_id)).toBeUndefined();

    refresh.resolve([builtInDocument]);
    await act(async () => {
      await expect(deleteRequest).resolves.toBe(true);
    });
    expect(result.current.documents).toEqual([builtInDocument]);
    expect(result.current.mutationState).toBe("ready");
  });

  it("preserves API status on mutation failure and can reload later", async () => {
    const api: DocumentApi = {
      listDocuments: vi.fn().mockResolvedValueOnce([builtInDocument]).mockRejectedValueOnce(new DocumentApiError(503)),
      uploadDocument: vi.fn().mockRejectedValue(new DocumentApiError(409)),
      deleteDocument: vi.fn(),
    };
    const { result } = renderHook(() => useDocuments(api));
    await waitFor(() => expect(result.current.documents).toEqual([builtInDocument]));

    await act(async () => {
      await expect(result.current.upload(new File(["duplicate"], "Duplicate.md"))).resolves.toBe(false);
    });
    expect(result.current.mutationError).toMatchObject({ status: 409 });

    await act(async () => {
      await result.current.reload();
    });
    expect(result.current.loadError).toMatchObject({ status: 503 });
  });
});
