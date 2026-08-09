import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearDocumentCache,
  invalidateDocumentCache,
  DocumentReadError,
  type FullDocument,
} from "../api/documents";
import type { DocumentCitation } from "../utils/documentCitation";
import * as documentApi from "../api/documents";
import DocumentViewer from "./DocumentViewer";

const citation: DocumentCitation = {
  documentId: "uploaded-local-guide",
  sectionSlug: "recovery",
};

const document: FullDocument = {
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
  markdown: "# Local Guide\n\n## Recovery\n\nLocal upload body.\n",
};

describe("DocumentViewer", () => {
  beforeEach(() => {
    clearDocumentCache();
    vi.restoreAllMocks();
  });

  it("does not reopen a stale cached document after invalidation and treats a deleted citation as non-retryable", async () => {
    const read = vi.spyOn(documentApi, "readDocument")
      .mockResolvedValueOnce(document)
      .mockRejectedValueOnce(new DocumentReadError(404));
    const { rerender } = render(
      <DocumentViewer citation={citation} open onClose={() => undefined} />,
    );

    expect(await screen.findByText("Local upload body.")).toBeInTheDocument();
    expect(screen.getByText("Local Upload")).toBeInTheDocument();
    expect(read).toHaveBeenCalledTimes(1);

    invalidateDocumentCache(document.document_id);
    rerender(<DocumentViewer citation={citation} open={false} onClose={() => undefined} />);
    await waitFor(() => expect(screen.queryByText("Local upload body.")).not.toBeInTheDocument());
    rerender(<DocumentViewer citation={citation} open onClose={() => undefined} />);

    expect(await screen.findByText("Document no longer available")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(read).toHaveBeenCalledTimes(2);
  });
});
