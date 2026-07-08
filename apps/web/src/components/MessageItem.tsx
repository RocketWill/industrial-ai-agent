import { Avatar, Button, Typography } from "antd";
import { CopyOutlined, RobotOutlined, UserOutlined } from "@ant-design/icons";
import type { Message } from "../api/messages";
import { normalizeAssistantContent } from "../utils/normalizeAssistantContent";

type Props = { message: Message; isStreaming?: boolean };

export default function MessageItem({ message, isStreaming = false }: Props) {
  const isUser = message.role === "user";
  const content = isUser ? message.content : normalizeAssistantContent(message.content);
  return <article className={`chat-message ${message.role}`} aria-label={`${isUser ? "You" : "Industrial AI Agent"} message`}>
    <Avatar className="message-avatar" icon={isUser ? <UserOutlined /> : <RobotOutlined />} />
    <div className="message-content">
      <div className="message-heading"><Typography.Text strong>{isUser ? "You" : "Industrial AI Agent"}</Typography.Text><Typography.Text type="secondary" className="message-time">{new Date(message.created_at).toLocaleString()}</Typography.Text></div>
      <Typography.Paragraph className={`message-body${isStreaming ? " streaming" : ""}`}>{content || (isStreaming ? "Generating response…" : "")}</Typography.Paragraph>
      {!isStreaming && content && <Button className="message-copy" type="text" size="small" icon={<CopyOutlined />} aria-label="Copy message" onClick={() => void navigator.clipboard?.writeText(content)}>Copy</Button>}
    </div>
  </article>;
}
