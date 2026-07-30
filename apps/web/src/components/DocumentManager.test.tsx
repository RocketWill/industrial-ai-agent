import userEvent from "@testing-library/user-event";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  DocumentApiError,
  type DocumentMetadata,
} from "../api/documents";
import * as documentApi from "../api/documents";
import DocumentManager from "./DocumentManager";

vi.mock("../api/documents", async () => {
  const actual = await vi.importActual<typeof import("../api/documents")>(
    "../api/documents",
  );

  return {
    ...actual,
    listDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
  };
});

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

const localDocument: DocumentMetadata = {
  document_id: "uploaded-local-guide",
  title: "Local Guide",
  document_type: "uploaded_document",
  source: "local_upload",
  filename: "Local Guide.md",
  relative_path: "uploads/uploaded-local-guide.md",
  size_bytes: 1536,
  status: "ready",
  deletable: true,
  synthetic_demo: false,
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

function validFile(name = "local-guide.md") {
  return new File(["# Local Guide\n\n## Recovery\n\nCheck it."], name, {
    type: "text/markdown",
  });
}

describe("DocumentManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(documentApi.listDocuments).mockResolvedValue([
      builtInDocument,
      localDocument,
    ]);
    vi.mocked(documentApi.uploadDocument).mockResolvedValue(localDocument);
    vi.mocked(documentApi.deleteDocument).mockResolvedValue(undefined);
  });

  it("explains the local/LLM boundary and separates protected and local provenance", async () => {
    render(<DocumentManager />);

    expect(await screen.findByText("Local document safety")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Documents are stored on local disk. Retrieved content may be sent to the configured LLM.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(builtInDocument.title)).toBeInTheDocument();
    expect(screen.getByText(localDocument.title)).toBeInTheDocument();
    expect(screen.getByText("Synthetic Demo")).toBeInTheDocument();
    expect(screen.getByText("Local Upload")).toBeInTheDocument();
    expect(screen.getByText(localDocument.filename)).toBeInTheDocument();
    expect(screen.getByText("1.5 KB")).toBeInTheDocument();
    expect(screen.getAllByText("Ready").length).toBeGreaterThanOrEqual(2);
    expect(
      screen.getByRole("button", { name: `Delete ${localDocument.title}` }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: `Delete ${builtInDocument.title}` }),
    ).not.toBeInTheDocument();
  });

  it("shows an explicit empty state when there are no local uploads", async () => {
    vi.mocked(documentApi.listDocuments).mockResolvedValue([builtInDocument]);

    render(<DocumentManager />);

    expect(await screen.findByText("No local Markdown uploads yet.")).toBeInTheDocument();
    expect(screen.getByText(builtInDocument.title)).toBeInTheDocument();
  });

  it.each([
    [
      "notes.txt",
      "Only Markdown (.md) files are supported. Choose one .md file.",
    ],
    [
      "large.md",
      "Markdown files must be 1 MiB or smaller. Choose a smaller file.",
    ],
  ])("rejects %s during client preflight without an API mutation", async (filename, errorText) => {
    const user = userEvent.setup();
    render(<DocumentManager />);
    await screen.findByText(localDocument.title);
    const input = await screen.findByLabelText("Select Markdown file");
    const file = filename === "large.md"
      ? new File([new Uint8Array(1024 * 1024 + 1)], filename)
      : validFile(filename);

    await user.upload(input, file);

    expect(await screen.findByText(errorText)).toBeInTheDocument();
    expect(documentApi.uploadDocument).not.toHaveBeenCalled();
  });

  it("shows Uploading and Indexing, disables concurrent actions, and ends Ready after refresh", async () => {
    const uploadRequest = deferred<DocumentMetadata>();
    const refresh = deferred<DocumentMetadata[]>();
    vi.mocked(documentApi.uploadDocument).mockReturnValue(uploadRequest.promise);
    vi.mocked(documentApi.listDocuments)
      .mockResolvedValueOnce([builtInDocument])
      .mockReturnValueOnce(refresh.promise);
    const user = userEvent.setup();

    render(<DocumentManager />);
    await screen.findByText(builtInDocument.title);
    const input = await screen.findByLabelText("Select Markdown file");
    await user.upload(input, validFile());

    expect(await screen.findByText("Uploading")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload Markdown" })).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: `Delete ${builtInDocument.title}` }),
    ).not.toBeInTheDocument();

    await act(async () => {
      uploadRequest.resolve(localDocument);
    });
    expect(await screen.findByText("Indexing")).toBeInTheDocument();

    await act(async () => {
      refresh.resolve([builtInDocument, localDocument]);
    });
    expect((await screen.findAllByText("Ready")).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(localDocument.title)).toBeInTheDocument();
  });

  it.each([
    [409, "A document with this name already exists. Choose a different filename and try again."],
    [413, "This Markdown file is larger than 1 MiB. Choose a smaller file and try again."],
    [422, "The server rejected this Markdown structure. Confirm the file is UTF-8, has one H1 title, and at least one H2/H3 section."],
    [503, "Document storage or indexing is temporarily unavailable. Retry when the backend is ready."],
  ])("maps a %s upload failure to safe actionable feedback with retry", async (status, errorText) => {
    vi.mocked(documentApi.uploadDocument).mockRejectedValue(new DocumentApiError(status));
    const user = userEvent.setup();

    render(<DocumentManager />);
    await screen.findByText(localDocument.title);
    const input = await screen.findByLabelText("Select Markdown file");
    await user.upload(input, validFile());

    expect(await screen.findByText(errorText)).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry upload" })).toBeInTheDocument();
  });

  it("retries a failed upload through the same application boundary", async () => {
    vi.mocked(documentApi.uploadDocument)
      .mockRejectedValueOnce(new DocumentApiError(503))
      .mockResolvedValueOnce(localDocument);
    vi.mocked(documentApi.listDocuments)
      .mockResolvedValueOnce([builtInDocument])
      .mockResolvedValueOnce([builtInDocument, localDocument]);
    const user = userEvent.setup();

    render(<DocumentManager />);
    await screen.findByText(builtInDocument.title);
    const input = await screen.findByLabelText("Select Markdown file");
    await user.upload(input, validFile());
    await screen.findByText("Retry upload");

    await user.click(screen.getByRole("button", { name: "Retry upload" }));

    await waitFor(() => expect(documentApi.uploadDocument).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(localDocument.title)).toBeInTheDocument();
  });

  it("retries a temporarily unavailable document list", async () => {
    vi.mocked(documentApi.listDocuments)
      .mockRejectedValueOnce(new DocumentApiError(503))
      .mockResolvedValueOnce([builtInDocument]);
    const user = userEvent.setup();

    render(<DocumentManager />);

    expect(await screen.findByText("Documents are temporarily unavailable. Retry the list when the backend is ready.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry document list" }));

    expect(await screen.findByText(builtInDocument.title)).toBeInTheDocument();
  });

  it("keeps built-ins visible when local upload state is unavailable", async () => {
    vi.mocked(documentApi.listDocuments).mockRejectedValueOnce(
      new DocumentApiError(503, "Document list request failed", null, [builtInDocument]),
    );

    render(<DocumentManager />);

    expect(await screen.findByText(builtInDocument.title)).toBeInTheDocument();
    expect(screen.getByText("Local uploads are unavailable. Built-in documents remain active.")).toBeInTheDocument();
  });

  it("names the delete confirmation, refreshes after deletion, and protects built-ins", async () => {
    const refresh = deferred<DocumentMetadata[]>();
    vi.mocked(documentApi.listDocuments)
      .mockResolvedValueOnce([builtInDocument, localDocument])
      .mockReturnValueOnce(refresh.promise);
    const user = userEvent.setup();

    render(<DocumentManager />);
    await screen.findByText(localDocument.title);
    await user.click(
      screen.getByRole("button", { name: `Delete ${localDocument.title}` }),
    );

    expect(screen.getByRole("dialog")).toHaveTextContent(
      `Delete ${localDocument.title}?`,
    );
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "Remove this local document from the retrieval corpus?",
    );

    await user.click(screen.getByRole("button", { name: "Delete document" }));
    expect(documentApi.deleteDocument).toHaveBeenCalledWith(localDocument.document_id);
    expect(screen.getByRole("button", { name: "Delete document" })).toBeDisabled();

    await act(async () => {
      refresh.resolve([builtInDocument]);
    });
    await waitFor(() => expect(screen.queryByText(localDocument.title)).not.toBeInTheDocument());
    expect(screen.getByText(builtInDocument.title)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: `Delete ${builtInDocument.title}` }),
    ).not.toBeInTheDocument();
  });
});
