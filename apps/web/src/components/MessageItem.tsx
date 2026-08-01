import { Avatar, Button, Descriptions, Tag, Typography } from "antd";
import { CopyOutlined, RobotOutlined, UserOutlined } from "@ant-design/icons";
import type { Message, ProductionEvidence } from "../api/messages";
import { normalizeAssistantContent } from "../utils/normalizeAssistantContent";

type Props = {
  message: Message;
  isStreaming?: boolean;
  evidence?: ProductionEvidence | null;
};

function displayTime(value: string): string {
  return new Date(value).toLocaleString();
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
      <Descriptions size="small" column={2} className="evidence-summary">
        <Descriptions.Item label="Equipment">
          {summary.equipment_id}
        </Descriptions.Item>
        <Descriptions.Item label="Lot">
          {summary.lot_id ?? "All lots"}
        </Descriptions.Item>
        <Descriptions.Item label="Time range" span={2}>
          {displayTime(summary.start)} – {displayTime(summary.end)}
        </Descriptions.Item>
        <Descriptions.Item label="Yield">
          {summary.yield_rate === null
            ? "No data"
            : `${(summary.yield_rate * 100).toFixed(2)}%`}
        </Descriptions.Item>
        <Descriptions.Item label="Inspected">
          {summary.inspected_wafers}
        </Descriptions.Item>
        <Descriptions.Item label="Passed">
          {summary.passed_wafers}
        </Descriptions.Item>
        <Descriptions.Item label="Failed">
          {summary.failed_wafers}
        </Descriptions.Item>
      </Descriptions>
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
                    {displayTime(alarm.started_at)} – {displayTime(alarm.ended_at)}
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

export default function MessageItem({
  message,
  isStreaming = false,
  evidence = null,
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
      <Avatar
        className="message-avatar"
        icon={isUser ? <UserOutlined /> : <RobotOutlined />}
      />
      <div className="message-content">
        <div className="message-heading">
          <Typography.Text strong>
            {isUser ? "You" : "Industrial AI Agent"}
          </Typography.Text>
          <Typography.Text type="secondary" className="message-time">
            {displayTime(message.created_at)}
          </Typography.Text>
        </div>
        <Typography.Paragraph
          className={`message-body${isStreaming ? " streaming" : ""}`}
        >
          {content || (isStreaming ? "Generating response…" : "")}
        </Typography.Paragraph>
        {!isStreaming && content && (
          <Button
            className="message-copy"
            type="text"
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
      </div>
    </article>
  );
}
