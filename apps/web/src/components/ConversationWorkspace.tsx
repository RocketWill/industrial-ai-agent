import { Alert, Button, Drawer, Input, List, Select, Skeleton, Tag, Typography } from "antd";
import { ArrowDownOutlined, SendOutlined, StopOutlined } from "@ant-design/icons";
import { useMessages } from "../hooks/useMessages";
import { useWorkspaceContext } from "../hooks/useWorkspaceContext";
import { useEffect, useRef, useState } from "react";
import EmptyConversation from "./EmptyConversation";
import MessageItem from "./MessageItem";

type Props = { conversationId: string | null };

export default function ConversationWorkspace({ conversationId }: Props) {
  const state = useMessages(conversationId);
  const contextState = useWorkspaceContext(conversationId);
  const context = contextState.context;
  const [contextOpen, setContextOpen] = useState(false);
  const [device, setDevice] = useState("");
  const [lot, setLot] = useState("");
  const [timeRange, setTimeRange] = useState("");
  const [lotError, setLotError] = useState<string | null>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const messageListRef = useRef<HTMLDivElement>(null);
  useEffect(() => { setDevice(context?.device ?? ""); setLot(context?.lot ?? ""); setTimeRange(context?.time_range ?? ""); }, [context]);
  const submit = () => void state.send();
  const scrollToBottom = () => { messageListRef.current?.scrollTo({ top: messageListRef.current.scrollHeight, behavior: "smooth" }); };
  const saveContext = async () => { if (lot.trim().length > 200) { setLotError("Lot must be 200 characters or fewer."); return; } setLotError(null); const saved = await contextState.save({ device: device.trim() || null, lot: lot.trim() || null, time_range: timeRange.trim() || null }); if (saved) setContextOpen(false); };
  return <section className="conversation-workspace" aria-label="Conversation workspace">
    <div className="conversation-heading"><Typography.Title level={2}>{conversationId ? "Conversation" : "Select a conversation"}</Typography.Title></div>
    <div className="context-bar" aria-label="Current analysis context"><Tag>Device: {context?.device ?? "Not selected"}</Tag><Tag>Lot: {context?.lot ?? "—"}</Tag><Tag>Range: {context?.time_range ?? "Not selected"}</Tag><Tag color="cyan">Source: Synthetic Demo</Tag>{conversationId && <Button type="link" size="small" onClick={() => setContextOpen(true)}>Edit context</Button>}</div>
    {state.error && <Alert type="error" showIcon message={state.error} action={<Button size="small" onClick={() => void state.reload()}>Retry</Button>} />}
    {state.isLoading ? <Skeleton active paragraph={{ rows: 5 }} /> : !conversationId ? <div className="conversation-empty-select">Select a conversation from the sidebar.</div> : state.messages.length === 0 ? <EmptyConversation onPromptSelect={state.setDraft} /> : <div ref={messageListRef} className="message-list" onScroll={(event) => setShowScrollButton(event.currentTarget.scrollHeight - event.currentTarget.scrollTop - event.currentTarget.clientHeight > 96)}><List dataSource={state.messages} renderItem={(message, index) => <List.Item className="message-row"><MessageItem message={message} isStreaming={state.isStreaming && index === state.messages.length - 1 && message.role === "assistant"} /></List.Item>} /></div>}
    {showScrollButton && <Button className="scroll-bottom-button" shape="circle" icon={<ArrowDownOutlined />} aria-label="Scroll to bottom" onClick={scrollToBottom} />}
    <div className="message-composer"><Input.TextArea aria-label="Message" value={state.draft} onChange={(event) => state.setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); submit(); } }} disabled={!conversationId || state.isSending} placeholder={conversationId ? "Ask about equipment, yield, alarms, or production data…" : "Select a conversation first"} autoSize={{ minRows: 2, maxRows: 6 }} />{state.isStreaming ? <Button danger icon={<StopOutlined />} aria-label="Stop generation" onClick={state.cancelStreaming}>Stop</Button> : <Button type="primary" icon={<SendOutlined />} loading={state.isSending} disabled={!conversationId || !state.draft.trim()} onClick={submit}>Send</Button>}</div>
    <Drawer title="Analysis context" open={contextOpen} onClose={() => setContextOpen(false)} extra={<Button type="primary" loading={contextState.isSaving} onClick={() => void saveContext()}>Save</Button>}><Typography.Paragraph type="secondary">These values describe the current analysis context. Data source remains Synthetic Demo.</Typography.Paragraph><label className="context-field">Device<Select aria-label="Device" allowClear loading={contextState.devicesLoading} status={contextState.devicesError ? "error" : undefined} placeholder="Not selected" value={device || undefined} onChange={(value) => setDevice(value ?? "")} options={contextState.devices.map((item) => ({ value: item.id, label: `${item.name} · ${item.category}` }))} /></label><label className="context-field">Lot<Input status={lotError ? "error" : undefined} value={lot} onChange={(event) => setLot(event.target.value)} placeholder="Optional" />{lotError && <Typography.Text type="danger">{lotError}</Typography.Text>}</label><label className="context-field">Time range<Select aria-label="Time range" allowClear placeholder="Not selected" value={timeRange || undefined} onChange={(value) => setTimeRange(value ?? "")} options={["Last 1 hour", "Last 4 hours", "Last 8 hours", "Last 24 hours", "Custom"].map((value) => ({ value, label: value }))} /></label><Tag color="cyan">Data source: Synthetic Demo</Tag>{contextState.devicesError && <Alert type="error" showIcon message={contextState.devicesError} />}{contextState.error && <Alert type="error" showIcon message={contextState.error} />}</Drawer>
  </section>;
}
