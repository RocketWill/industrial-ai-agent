import { Button, Descriptions, Progress, Tag, Typography } from "antd";
import { CopyOutlined } from "@ant-design/icons";
import { lazy, Suspense } from "react";
import type { Message, ProductionEvidence } from "../api/messages";
import { normalizeAssistantContent } from "../utils/normalizeAssistantContent";

const XMarkdown = lazy(() => import("@ant-design/x-markdown").then((module) => ({ default: module.XMarkdown })));

type Props = {
  message: Message;
  isStreaming?: boolean;
  evidence?: ProductionEvidence | null;
  runLabel?: string | null;
};

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
        column={2}
        className="evidence-summary"
        items={[
          { key: "equipment", label: "Equipment", children: summary.equipment_id },
          { key: "lot", label: "Lot", children: summary.lot_id ?? "All lots" },
          { key: "range", label: "Time range", span: 2, children: `${displayTime(summary.start)} - ${displayTime(summary.end)}` },
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

export default function MessageItem({
  message,
  isStreaming = false,
  evidence = null,
  runLabel = null,
}: Props) {
  const isUser = message.role === "user";
  const content = isUser
    ? message.content
    : normalizeAssistantContent(message.content);

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
        {!isUser && !isStreaming && evidence?.production_summary && (
          <ProductionEvidenceCard evidence={evidence} />
        )}
        {!isUser && !isStreaming && evidence?.equipment_status && (
          <EquipmentStatusCard evidence={evidence} />
        )}
        {!isUser && !isStreaming && evidence?.defect_distribution && (
          <DefectDistributionCard evidence={evidence} />
        )}
      </div>
    </article>
  );
}
