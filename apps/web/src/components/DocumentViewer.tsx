import { Alert, Button, Drawer, Spin, Tag, Typography } from "antd";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { RegistryDocument } from "../api/documents";
import { readDocument } from "../api/documents";
import type { DocumentCitation } from "../utils/documentCitation";

const XMarkdown = lazy(() => import("@ant-design/x-markdown").then((module) => ({ default: module.XMarkdown })));
const documentCache = new Map<string, RegistryDocument>();

function slug(value: string): string {
  return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .match(/[a-z0-9]+/g)?.join("-") ?? "";
}

export default function DocumentViewer({ citation, open, onClose }: {
  citation: DocumentCitation | null;
  open: boolean;
  onClose: () => void;
}) {
  const [document, setDocument] = useState<RegistryDocument | null>(null);
  const [error, setError] = useState(false);
  const [missingSection, setMissingSection] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!open || !citation) return;
    const cached = documentCache.get(citation.documentId);
    if (cached) { setDocument(cached); setError(false); return; }
    let active = true;
    setDocument(null); setError(false);
    void readDocument(citation.documentId).then((value) => {
      if (!active) return;
      documentCache.set(citation.documentId, value); setDocument(value);
    }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [open, citation, attempt]);

  useEffect(() => {
    if (!document || !citation || !contentRef.current) return;
    const root = contentRef.current;
    const positionSection = () => {
      const headings = root.querySelectorAll<HTMLElement>("h2, h3");
      if (!headings.length && citation.sectionSlug !== "overview") return false;
      let h2 = "";
      let target: HTMLElement | null = citation.sectionSlug === "overview" ? root : null;
      root.querySelectorAll<HTMLElement>(".document-section-target").forEach((item) => item.classList.remove("document-section-target"));
      headings.forEach((heading) => {
        if (heading.tagName === "H2") h2 = heading.textContent ?? "";
        const path = heading.tagName === "H3" ? `${h2} ${heading.textContent ?? ""}` : heading.textContent ?? "";
        heading.id = `document-section-${slug(path)}`;
        if (slug(path) === citation.sectionSlug) target = heading;
      });
      setMissingSection(!target);
      (target ?? root).scrollIntoView({ block: "start" });
      target?.classList.add("document-section-target");
      return true;
    };
    if (positionSection()) return;
    const observer = new MutationObserver(() => {
      if (positionSection()) observer.disconnect();
    });
    observer.observe(root, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [document, citation]);

  return (
    <Drawer title={document?.title ?? "Document source"} placement="right" open={open} onClose={onClose}
      size="min(720px, 100vw)" destroyOnHidden classNames={{ body: "document-viewer-body" }}>
      {!document && !error && <div className="document-viewer-state"><Spin /><span>Loading document…</span></div>}
      {error && <Alert type="error" showIcon message="Document unavailable" description="The document could not be loaded."
        action={<Button onClick={() => setAttempt((value) => value + 1)}>Retry</Button>} />}
      {document && <>
        <div className="document-viewer-meta"><Tag color="blue">Synthetic Demo</Tag><Typography.Text type="secondary">{document.relative_path}</Typography.Text></div>
        {missingSection && <Alert type="warning" showIcon message="Referenced section could not be located" />}
        <div ref={contentRef} className="document-viewer-content">
          <Suspense fallback={<Spin />}><XMarkdown content={document.markdown} escapeRawHtml openLinksInNewTab
            components={{ img: () => <Typography.Text type="secondary">[Remote image omitted]</Typography.Text> }} /></Suspense>
        </div>
      </>}
    </Drawer>
  );
}
