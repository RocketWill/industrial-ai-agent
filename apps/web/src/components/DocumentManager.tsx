import { DeleteOutlined, UploadOutlined } from "@ant-design/icons";
import { Alert, Button, Modal, Spin, Tag, Typography, Upload } from "antd";
import { useMemo, useState } from "react";

import { DocumentApiError, type DocumentMetadata } from "../api/documents";
import { useDocuments } from "../hooks/useDocuments";

const MAX_UPLOAD_BYTES = 1024 * 1024;

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  return `${(value / 1024).toFixed(value % 1024 === 0 ? 0 : 1)} KB`;
}

function mutationMessage(error: DocumentApiError | null): string {
  switch (error?.status) {
    case 409:
      return "A document with this name already exists. Choose a different filename and try again.";
    case 413:
      return "This Markdown file is larger than 1 MiB. Choose a smaller file and try again.";
    case 422:
      return "The server rejected this Markdown structure. Confirm the file is UTF-8, has one H1 title, and at least one H2/H3 section.";
    case 503:
      return "Document storage or indexing is temporarily unavailable. Retry when the backend is ready.";
    default:
      return "The document operation failed. Check the backend and try again.";
  }
}

function sourceLabel(document: DocumentMetadata): string {
  return document.source === "built_in" ? "Synthetic Demo" : "Local Upload";
}

export default function DocumentManager() {
  const state = useDocuments();
  const [preflightError, setPreflightError] = useState<string | null>(null);
  const [lastFile, setLastFile] = useState<File | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DocumentMetadata | null>(null);
  const mutationPending = state.mutationState === "uploading" || state.mutationState === "indexing";
  const localCount = useMemo(
    () => state.documents.filter((document) => document.source === "local_upload").length,
    [state.documents],
  );

  const submitFile = async (file: File) => {
    setPreflightError(null);
    setLastFile(file);
    await state.upload(file);
  };

  const acceptFile = (file: File) => {
    if (!file.name.toLowerCase().endsWith(".md")) {
      setPreflightError("Only Markdown (.md) files are supported. Choose one .md file.");
      return Upload.LIST_IGNORE;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setPreflightError("Markdown files must be 1 MiB or smaller. Choose a smaller file.");
      return Upload.LIST_IGNORE;
    }
    void submitFile(file);
    return false;
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const succeeded = await state.remove(deleteTarget.document_id);
    if (succeeded) setDeleteTarget(null);
  };

  return (
    <section className="document-manager" aria-label="Document management">
      <div className="document-manager-identity" aria-hidden="true" />
      <Alert
        type="warning"
        showIcon
        title="Local document safety"
        description="Documents are stored on local disk. Retrieved content may be sent to the configured LLM."
      />

      <div className="document-upload-panel">
        <div>
          <Typography.Title level={4}>Add Markdown</Typography.Title>
          <Typography.Text type="secondary">One UTF-8 .md file, up to 1 MiB.</Typography.Text>
        </div>
        <label className="visually-hidden" htmlFor="document-upload-input">Select Markdown file</label>
        <Upload
          id="document-upload-input"
          accept=".md,text/markdown,text/plain"
          maxCount={1}
          multiple={false}
          showUploadList={false}
          disabled={state.isLoading || mutationPending}
          beforeUpload={acceptFile}
        >
          <Button aria-label="Upload Markdown" icon={<UploadOutlined />} disabled={state.isLoading || mutationPending}>Upload Markdown</Button>
        </Upload>
      </div>

      {preflightError && <Alert type="error" showIcon title={preflightError} />}
      {state.mutationState !== "idle" && (
        <div className="document-operation-status" aria-live="polite">
          {mutationPending && <Spin size="small" />}
          <Typography.Text>{state.mutationState[0].toUpperCase() + state.mutationState.slice(1)}</Typography.Text>
          {state.mutationState === "failed" && lastFile && (
            <Button size="small" onClick={() => void submitFile(lastFile)}>Retry upload</Button>
          )}
        </div>
      )}
      {state.mutationError && <Alert type="error" showIcon title={mutationMessage(state.mutationError)} />}
      {state.loadError && state.documents.length > 0 && (
        <Alert type="error" showIcon title="Local uploads are unavailable. Built-in documents remain active." action={<Button size="small" onClick={() => void state.reload()}>Retry document list</Button>} />
      )}

      {state.loadError && state.documents.length === 0 ? (
        <Alert
          type="error"
          showIcon
          title="Documents are temporarily unavailable. Retry the list when the backend is ready."
          action={<Button size="small" onClick={() => void state.reload()}>Retry document list</Button>}
        />
      ) : state.isLoading ? (
        <div className="document-manager-loading"><Spin /><span>Loading documents…</span></div>
      ) : (
        <>
          <div className="document-list-heading">
            <Typography.Title level={4}>Active corpus</Typography.Title>
            <Typography.Text type="secondary">{state.documents.length} documents</Typography.Text>
          </div>
          {state.documents.length === 0 ? (
            <Typography.Text type="secondary">No documents available.</Typography.Text>
          ) : (
            <ul className="managed-document-list">
              {state.documents.map((document) => (
                <li key={document.document_id} className="managed-document-item">
                  <div className="managed-document-copy">
                    <div className="managed-document-title"><Typography.Text strong>{document.title}</Typography.Text><Tag color={document.source === "built_in" ? "blue" : "cyan"}>{sourceLabel(document)}</Tag><Tag>Ready</Tag></div>
                    <Typography.Text type="secondary" className="managed-document-meta">{document.filename}<span>{formatBytes(document.size_bytes)}</span></Typography.Text>
                  </div>
                  {document.deletable && (
                  <Button
                    color="danger"
                    variant="text"
                    icon={<DeleteOutlined />}
                    aria-label={`Delete ${document.title}`}
                    disabled={mutationPending}
                    onClick={() => setDeleteTarget(document)}
                  />
                  )}
                </li>
              ))}
            </ul>
          )}
          {localCount === 0 && <div className="document-empty-local"><span className="document-empty-mark" aria-hidden="true" /><Typography.Text>No local Markdown uploads yet.</Typography.Text></div>}
        </>
      )}

      <Modal
        open={deleteTarget !== null}
        title={`Delete ${deleteTarget?.title ?? "document"}?`}
        onCancel={() => setDeleteTarget(null)}
        onOk={() => void confirmDelete()}
        okText="Delete document"
        okButtonProps={{ color: "danger", variant: "solid", "aria-label": "Delete document", disabled: mutationPending }}
        confirmLoading={mutationPending}
        destroyOnHidden
      >
        <Typography.Paragraph>Remove this local document from the retrieval corpus?</Typography.Paragraph>
        <Typography.Text type="secondary">Existing conversation source cards remain, but the document cannot be reopened after deletion.</Typography.Text>
      </Modal>
    </section>
  );
}
