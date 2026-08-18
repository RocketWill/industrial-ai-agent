import { Button, Descriptions, Progress, Tag, Typography } from "antd";
import { CopyOutlined } from "@ant-design/icons";
import { Prompts } from "@ant-design/x";
import { lazy, Suspense, useState } from "react";
import type { CombinedEvidence, CombinedEvidencePath, EvidenceSnapshot, Message, ProductionEvidence } from "../api/messages";
import type { WorkingNotesState } from "../hooks/useMessages";
import { normalizeAssistantContent } from "../utils/normalizeAssistantContent";
import DocumentViewer from "./DocumentViewer";
import { parseCitation, type DocumentCitation } from "../utils/documentCitation";

const XMarkdown = lazy(() => import("@ant-design/x-markdown").then((module) => ({ default: module.XMarkdown })));

export const PRODUCTION_SUMMARY_COLUMNS = { xs: 1, sm: 2 } as const;

type Props = {
  message: Message;
  isStreaming?: boolean;
  evidence?: ProductionEvidence | null;
  combinedEvidence?: CombinedEvidence | null;
  runLabel?: string | null;
  showSuggestedActions?: boolean;
  suggestedActionsDisabled?: boolean;
  onSuggestedAction?: (message: string) => void;
  workingNotes?: WorkingNotesState | null;
  onWorkingNotesOpenChange?: (open: boolean) => void;
};

function PathState({ label, path }: { label: string; path: CombinedEvidencePath }) {
  if (path.status === "loading") return <section className="evidence-card evidence-path-state" role="status" aria-live="polite" aria-label={`${label} loading`}><Typography.Text strong>{label}</Typography.Text><Typography.Text type="secondary">Retrieving evidence…</Typography.Text></section>;
  if (path.status === "failed") return <section className="evidence-card evidence-path-state" role="alert" aria-label={`${label} unavailable`}><Typography.Text strong>{label}</Typography.Text><Typography.Text type="secondary">Evidence could not be retrieved.</Typography.Text></section>;
  if (path.status === "not_run") return <section className="evidence-card evidence-path-state" role="status" aria-label={`${label} pending`}><Typography.Text strong>{label}</Typography.Text><Typography.Text type="secondary">Waiting to run.</Typography.Text></section>;
  return null;
}

function CombinedEvidencePanels({ combined }: { combined: CombinedEvidence }) {
  const manufacturing: ProductionEvidence = {
    production_summary: combined.manufacturing_kind === "production" ? combined.manufacturing.result : null,
    equipment_status: combined.manufacturing_kind === "equipment_status" ? combined.manufacturing.result : null,
    defect_distribution: combined.manufacturing_kind === "defect_distribution" ? combined.manufacturing.result : null,
    document_search: null,
    tool_error: null,
  };
  const documents: ProductionEvidence = { production_summary: null, document_search: combined.documents.result, tool_error: null };
  return <div className="combined-evidence" role="region" aria-label="Combined evidence">
    <PathState label="Manufacturing evidence" path={combined.manufacturing} />
    {combined.manufacturing_kind === "production" && <ProductionEvidenceCard evidence={manufacturing} />}
    {combined.manufacturing_kind === "equipment_status" && <EquipmentStatusCard evidence={manufacturing} />}
    {combined.manufacturing_kind === "defect_distribution" && <DefectDistributionCard evidence={manufacturing} />}
    <PathState label="Document evidence" path={combined.documents} />
    {combined.documents.result && <DocumentSourcesCard evidence={documents} />}
  </div>;
}

function displayTime(value: string): string {
  return new Date(value).toLocaleString();
}

function ThinkingIndicator({ label }: { label: string }) {
  const showLabel = label !== "Generating response";

  return (
    <div className="thinking-status" role="status" aria-live="polite" aria-label={label}>
      <span className="thinking-dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      {showLabel && <span className="thinking-label">{label}</span>}
    </div>
  );
}

function ProductionEvidenceCard({ evidence }: { evidence: ProductionEvidence }) {
  const summary = evidence.production_summary;
  if (!summary) return null;

  return (
    <section className="evidence-card" aria-label="Production evidence">
      <div className="evidence-heading">
        <Typography.Text strong>Production summary</Typography.Text>
        <div className="evidence-tags">
          <Tag color="cyan">Deterministic</Tag>
          <Tag> Synthetic Demo </Tag>
        </div>
      </div>
      <Descriptions
        size="small"
        column={PRODUCTION_SUMMARY_COLUMNS}
        className="evidence-summary"
        items={[
          { key: "equipment", label: "Equipment", children: summary.equipment_id },
          { key: "lot", label: "Lot", children: summary.lot_id ?? "All lots" },
          { key: "range", label: "Time range", span: { xs: 1, sm: 2 }, children: `${displayTime(summary.start)} - ${displayTime(summary.end)}` },
          { key: "yield", label: "Yield", children: summary.yield_rate === null ? "No data" : `${(summary.yield_rate * 100).toFixed(2)}%` },
          { key: "inspected", label: "Inspected", children: summary.inspected_wafers },
          { key: "passed", label: "Passed", children: summary.passed_wafers },
          { key: "failed", label: "Failed", children: summary.failed_wafers },
        ]}
      />
      <div className="evidence-details">
        <section className="evidence-detail-section" aria-labelledby="defect-counts">
          <Typography.Title level={5} id="defect-counts">
            Defect counts
          </Typography.Title>
          {summary.defect_counts.length === 0 ? (
            <Typography.Text type="secondary">
              No defect counts returned.
            </Typography.Text>
          ) : (
            <dl className="evidence-detail-list">
              {summary.defect_counts.map((defect) => (
                <div key={defect.category}>
                  <dt>{defect.category}</dt>
                  <dd>{defect.count}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>
        <section className="evidence-detail-section" aria-labelledby="alarm-events">
          <Typography.Title level={5} id="alarm-events">
            Alarm events
          </Typography.Title>
          {summary.alarm_events.length === 0 ? (
            <Typography.Text type="secondary">
              No alarm events returned.
            </Typography.Text>
          ) : (
            <ul className="evidence-alarm-list">
              {summary.alarm_events.map((alarm) => (
                <li key={alarm.event_id}>
                  <Typography.Text strong>{alarm.code}</Typography.Text>
                  <Typography.Text type="secondary">
                    {displayTime(alarm.started_at)} - {displayTime(alarm.ended_at)}
                  </Typography.Text>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      {summary.limitations.length > 0 && (
        <Typography.Text className="evidence-limitations" type="secondary">
          {summary.limitations.join(" ")}
        </Typography.Text>
      )}
    </section>
  );
}

function EquipmentStatusCard({ evidence }: { evidence: ProductionEvidence }) {
  const status = evidence.equipment_status;
  if (!status) return null;

  return (
    <section className="evidence-card equipment-status-card" aria-label="Equipment status evidence">
      <div className="evidence-heading">
        <Typography.Text strong>Equipment status</Typography.Text>
        <div className="evidence-tags">
          <Tag color="cyan">Deterministic</Tag>
          <Tag>Synthetic Demo</Tag>
        </div>
      </div>
      <Descriptions
        size="small"
        column={2}
        className="evidence-summary"
        items={[
          { key: "equipment", label: "Equipment", children: status.equipment_id },
          { key: "status", label: "Recorded state", children: <Tag>{status.status}</Tag> },
          { key: "observed", label: "Observed at", span: 2, children: displayTime(status.observed_at) },
          { key: "effective-start", label: "Effective start", children: status.effective_start ? displayTime(status.effective_start) : "Unavailable" },
          { key: "effective-end", label: "Effective end", children: status.effective_end ? displayTime(status.effective_end) : "Unavailable" },
          { key: "reason", label: "Reason code", span: 2, children: status.reason_code ?? "Not recorded" },
        ]}
      />
      {status.limitations.length > 0 && (
        <Typography.Text className="evidence-limitations" type="secondary">
          {status.limitations.join(" ")}
        </Typography.Text>
      )}
    </section>
  );
}

function DefectDistributionCard({ evidence }: { evidence: ProductionEvidence }) {
  const distribution = evidence.defect_distribution;
  if (!distribution) return null;

  return (
    <section className="evidence-card defect-distribution-card" aria-label="Defect distribution evidence">
      <div className="evidence-heading">
        <Typography.Text strong>Defect distribution</Typography.Text>
        <div className="evidence-tags">
          <Tag color="cyan">Deterministic</Tag>
          <Tag>Synthetic Demo</Tag>
        </div>
      </div>
      <Descriptions
        size="small"
        column={2}
        className="evidence-summary"
        items={[
          { key: "equipment", label: "Equipment", children: distribution.equipment_id },
          { key: "lot", label: "Lot", children: distribution.lot_id ?? "All lots" },
          { key: "range", label: "Time range", span: 2, children: `${displayTime(distribution.start)} - ${displayTime(distribution.end)}` },
          { key: "failed", label: "Failed wafers", children: distribution.failed_wafers },
          { key: "classified", label: "Classified defects", children: distribution.classified_defect_count },
          { key: "unclassified", label: "Unclassified failures", span: 2, children: distribution.unclassified_failed_wafers },
        ]}
      />
      <div className="defect-distribution-list">
        {distribution.items.length === 0 ? (
          <Typography.Text type="secondary">No classified defects returned.</Typography.Text>
        ) : distribution.items.map((item) => {
          const percent = item.share === null ? 0 : item.share * 100;
          return (
            <div className="defect-distribution-item" key={item.category}>
              <div className="defect-distribution-label">
                <Typography.Text>{item.category}</Typography.Text>
                <div>
                  <Tag className="defect-rank-tag">Rank {item.rank}</Tag>
                  <Typography.Text className="defect-distribution-value">
                    {item.count} · {item.share === null ? "No share" : `${percent.toFixed(1)}%`}
                  </Typography.Text>
                </div>
              </div>
              <Progress percent={percent} showInfo={false} size="small" strokeColor="#37c6d0" />
            </div>
          );
        })}
      </div>
      {distribution.limitations.length > 0 && (
        <Typography.Text className="evidence-limitations" type="secondary">
          {distribution.limitations.join(" ")}
        </Typography.Text>
      )}
    </section>
  );
}

function DocumentSourcesCard({ evidence }: { evidence: ProductionEvidence }) {
  const search = evidence.document_search;
  const [citation, setCitation] = useState<DocumentCitation | null>(null);
  if (!search) return null;
  const hasBuiltInSource = search.sources.some((source) => source.source === "built_in");
  const hasLocalSource = search.sources.some((source) => source.source === "local_upload");

  return (
    <section className="evidence-card document-sources-card" aria-label="Retrieved document sources">
      <div className="evidence-heading">
        <Typography.Text strong>Sources</Typography.Text>
        <div className="evidence-tags">
          <Tag color="blue">Retrieved</Tag>
          {hasBuiltInSource && <Tag>Synthetic Demo</Tag>}
          {hasLocalSource && <Tag color="cyan">Local Upload</Tag>}
        </div>
      </div>
      {search.sources.length === 0 ? (
        <Typography.Text type="secondary">No relevant sources returned.</Typography.Text>
      ) : (
        <ol className="document-source-list">
          {search.sources.map((source) => (
            <li key={source.source_id}>
              <div className="document-source-heading">
                <Typography.Text strong>{source.title}</Typography.Text>
                <Typography.Text className="document-source-score" type="secondary">
                  {(source.score * 100).toFixed(1)}% match
                </Typography.Text>
              </div>
              <Typography.Text className="document-source-section">
                {source.section}
              </Typography.Text>
              <Typography.Paragraph className="document-source-excerpt">
                {source.excerpt}
              </Typography.Paragraph>
              <Typography.Text className="document-source-path" type="secondary">
                {source.relative_path} · {source.source_id}
              </Typography.Text>
              {parseCitation(source.source_id) && (
                <Button size="small" variant="link" onClick={() => setCitation(parseCitation(source.source_id))}>
                  View document
                </Button>
              )}
            </li>
          ))}
        </ol>
      )}
      {search.limitations.length > 0 && (
        <Typography.Text className="evidence-limitations" type="secondary">
          {search.limitations.join(" ")}
        </Typography.Text>
      )}
      <DocumentViewer citation={citation} open={citation !== null} onClose={() => setCitation(null)} />
    </section>
  );
}

function HistoricalEvidence({ snapshot, createdAt }: { snapshot: EvidenceSnapshot; createdAt: string }) {
  if (snapshot.status === "unavailable") {
    return (
      <section className="evidence-card evidence-path-state" role="status" aria-label="Historical evidence unavailable">
        <Typography.Text strong>Historical evidence unavailable</Typography.Text>
        <Typography.Text type="secondary">{snapshot.code}</Typography.Text>
      </section>
    );
  }

  const evidence: ProductionEvidence = {
    production_summary: snapshot.kind === "production_summary" ? snapshot.production_summary : null,
    equipment_status: snapshot.kind === "equipment_status" ? snapshot.equipment_status : null,
    defect_distribution: snapshot.kind === "defect_distribution" ? snapshot.defect_distribution : null,
    document_search: snapshot.kind === "document_search" ? snapshot.document_search : null,
    tool_error: null,
  };

  return (
    <section className="historical-evidence" role="region" aria-label="Historical evidence">
      <header className="evidence-heading">
        <Typography.Text strong>Historical snapshot</Typography.Text>
        <Typography.Text type="secondary">{displayTime(createdAt)}</Typography.Text>
      </header>
      {snapshot.kind === "combined" ? (
        <CombinedEvidencePanels combined={snapshot} />
      ) : snapshot.kind === "production_summary" ? (
        <ProductionEvidenceCard evidence={evidence} />
      ) : snapshot.kind === "equipment_status" ? (
        <EquipmentStatusCard evidence={evidence} />
      ) : snapshot.kind === "defect_distribution" ? (
        <DefectDistributionCard evidence={evidence} />
      ) : (
        <DocumentSourcesCard evidence={evidence} />
      )}
    </section>
  );
}

export default function MessageItem({
  message,
  isStreaming = false,
  evidence = null,
  combinedEvidence = null,
  runLabel = null,
  showSuggestedActions = false,
  suggestedActionsDisabled = false,
  onSuggestedAction = () => undefined,
  workingNotes = null,
  onWorkingNotesOpenChange,
}: Props) {
  const isUser = message.role === "user";
  const content = isUser
    ? message.content
    : normalizeAssistantContent(message.content);
  const workingNotesStatus = workingNotes?.status === "truncated"
    ? "Truncated"
    : workingNotes?.status === "interrupted"
      ? "Interrupted"
      : null;

  return (
    <article
      className={`chat-message ${message.role}`}
      aria-label={`${isUser ? "You" : "Industrial AI Agent"} message`}
    >
      <div className="message-content">
        <div className="message-heading">
          <Typography.Text strong>
            {isUser ? "You" : "Industrial AI Agent"}
          </Typography.Text>
          <Typography.Text type="secondary" className="message-time">
            {displayTime(message.created_at)}
          </Typography.Text>
        </div>
        {isUser ? (
          <Typography.Paragraph className="message-body user-message-body">
            {content}
          </Typography.Paragraph>
        ) : content ? (
          <Suspense fallback={<Typography.Paragraph className="message-body">{content}</Typography.Paragraph>}>
            <XMarkdown
              rootClassName="message-body assistant-markdown"
              content={content}
              escapeRawHtml
              openLinksInNewTab
              streaming={isStreaming ? { hasNextChunk: true, tail: true, enableAnimation: false } : undefined}
            />
          </Suspense>
        ) : (
          <ThinkingIndicator label={runLabel ?? "Generating response"} />
        )}
        {!isUser && workingNotes && (
          <details
            className="working-notes-disclosure"
            aria-label="Model working notes"
            data-status={workingNotes.status}
            open={workingNotes.open}
            onToggle={(event) => onWorkingNotesOpenChange?.(event.currentTarget.open)}
          >
            <summary>
              Model working notes
              {workingNotesStatus && <span className="working-notes-status">{workingNotesStatus}</span>}
            </summary>
            <div className="working-notes-body">{workingNotes.content}</div>
          </details>
        )}
        {!isStreaming && content && (
          <Button
            className="message-copy"
            variant="text"
            size="small"
            icon={<CopyOutlined />}
            aria-label="Copy message"
            onClick={() => void navigator.clipboard?.writeText(content)}
          >
            Copy
          </Button>
        )}
        {!isUser && showSuggestedActions && message.suggested_actions.length > 0 && (
          <Prompts
            rootClassName="routing-choice-prompts"
            title="Choose what to inspect first"
            items={message.suggested_actions.map((action) => ({
              key: action.id,
              label: (
                <Button
                  className="routing-choice-button"
                  disabled={suggestedActionsDisabled}
                  onClick={() => onSuggestedAction(action.message)}
                >
                  {action.label}
                </Button>
              ),
              description: action.message,
              disabled: suggestedActionsDisabled,
            }))}
            wrap
            fadeIn={false}
          />
        )}
        {!isUser && !isStreaming && evidence?.production_summary && (
          <ProductionEvidenceCard evidence={evidence} />
        )}
        {!isUser && !isStreaming && evidence?.equipment_status && (
          <EquipmentStatusCard evidence={evidence} />
        )}
        {!isUser && !isStreaming && evidence?.defect_distribution && (
          <DefectDistributionCard evidence={evidence} />
        )}
        {!isUser && !isStreaming && evidence?.document_search && (
          <DocumentSourcesCard evidence={evidence} />
        )}
        {!isUser && combinedEvidence && <CombinedEvidencePanels combined={combinedEvidence} />}
        {!isUser && !isStreaming && message.evidence_snapshot && (
          <HistoricalEvidence snapshot={message.evidence_snapshot} createdAt={message.created_at} />
        )}
      </div>
    </article>
  );
}
