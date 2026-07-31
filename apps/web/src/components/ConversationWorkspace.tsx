import { Alert, Button, Empty, Input, List, Skeleton, Typography } from "antd";
import { SendOutlined, StopOutlined } from "@ant-design/icons";
import { useMessages } from "../hooks/useMessages";

type Props = { conversationId: string | null };

export default function ConversationWorkspace({ conversationId }: Props) {
  const state = useMessages(conversationId);
  const submit = () => void state.send();
  return <section className="conversation-workspace" aria-label="Conversation workspace">
    <Typography.Title level={2}>{conversationId ? "Conversation" : "Select a conversation"}</Typography.Title>
    {state.error && <Alert type="error" showIcon message={state.error} action={<Button size="small" onClick={() => void state.reload()}>Retry</Button>} />}
    {state.isLoading ? <Skeleton active paragraph={{ rows: 5 }} /> : !conversationId ? <Empty description="Choose a conversation to view its history." /> : state.messages.length === 0 ? <Empty description="Start this conversation." /> : <List className="message-list" dataSource={state.messages} renderItem={(message) => <List.Item className={`message-item ${message.role}`}><List.Item.Meta title={message.role === "user" ? "You" : "Assistant"} description={<><span>{message.content}</span><Typography.Text type="secondary" className="message-time">{new Date(message.created_at).toLocaleString()}</Typography.Text></>} /></List.Item>} />}
    <div className="message-composer"><Input.TextArea aria-label="Message" value={state.draft} onChange={(event) => state.setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } }} disabled={!conversationId || state.isSending} placeholder={conversationId ? "Ask a question" : "Select a conversation first"} autoSize={{ minRows: 2, maxRows: 6 }} />{state.isStreaming ? <Button danger icon={<StopOutlined />} onClick={state.cancelStreaming}>Stop</Button> : <Button type="primary" icon={<SendOutlined />} loading={state.isSending} disabled={!conversationId || !state.draft.trim()} onClick={submit}>Send</Button>}</div>
  </section>;
}
