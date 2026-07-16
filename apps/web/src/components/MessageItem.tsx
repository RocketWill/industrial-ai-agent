import { Avatar, Button, Descriptions, Tag, Typography } from "antd";
import { CopyOutlined, RobotOutlined, UserOutlined } from "@ant-design/icons";
import type { Message, ProductionEvidence } from "../api/messages";
import { normalizeAssistantContent } from "../utils/normalizeAssistantContent";

type Props = { message: Message; isStreaming?: boolean; evidence?: ProductionEvidence | null };

export default function MessageItem({ message, isStreaming = false, evidence = null }: Props) {
  const isUser = message.role === "user";
  const content = isUser ? message.content : normalizeAssistantContent(message.content);
  return <article className={`chat-message ${message.role}`} aria-label={`${isUser ? "You" : "Industrial AI Agent"} message`}>
    <Avatar className="message-avatar" icon={isUser ? <UserOutlined /> : <RobotOutlined />} />
    <div className="message-content">
      <div className="message-heading"><Typography.Text strong>{isUser ? "You" : "Industrial AI Agent"}</Typography.Text><Typography.Text type="secondary" className="message-time">{new Date(message.created_at).toLocaleString()}</Typography.Text></div>
      <Typography.Paragraph className={`message-body${isStreaming ? " streaming" : ""}`}>{content || (isStreaming ? "Generating response…" : "")}</Typography.Paragraph>
      {!isStreaming && content && <Button className="message-copy" type="text" size="small" icon={<CopyOutlined />} aria-label="Copy message" onClick={() => void navigator.clipboard?.writeText(content)}>Copy</Button>}
      {!isUser && !isStreaming && evidence?.production_summary && <section className="evidence-card" aria-label="Production evidence"><div className="evidence-heading"><Typography.Text strong>Production summary</Typography.Text><Tag color="cyan">Deterministic</Tag></div><Descriptions size="small" column={2}><Descriptions.Item label="Equipment">{evidence.production_summary.equipment_id}</Descriptions.Item><Descriptions.Item label="Lot">{evidence.production_summary.lot_id ?? "All lots"}</Descriptions.Item><Descriptions.Item label="Time range" span={2}>{new Date(evidence.production_summary.start).toLocaleString()} – {new Date(evidence.production_summary.end).toLocaleString()}</Descriptions.Item><Descriptions.Item label="Yield">{evidence.production_summary.yield_rate === null ? "No data" : `${(evidence.production_summary.yield_rate * 100).toFixed(2)}%`}</Descriptions.Item><Descriptions.Item label="Inspected">{evidence.production_summary.inspected_wafers}</Descriptions.Item><Descriptions.Item label="Passed">{evidence.production_summary.passed_wafers}</Descriptions.Item><Descriptions.Item label="Failed">{evidence.production_summary.failed_wafers}</Descriptions.Item></Descriptions>{evidence.production_summary.limitations.length > 0 && <Typography.Text type="secondary">{evidence.production_summary.limitations.join(" ")}</Typography.Text>}</section>}
    </div>
  </article>;
}
