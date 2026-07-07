import { useState } from "react";
import { Alert, Button, Form, Input, List, Modal, Skeleton, Typography } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import type { ConversationState } from "../hooks/useConversations";

type Props = { state: ConversationState };

export default function ConversationNavigation({ state }: Props) {
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm<{ title?: string }>();
  const submit = async () => { const values = await form.validateFields(); await state.createConversation(values.title); form.resetFields(); setOpen(false); };
  return <aside className="conversation-navigation" aria-label="Conversation navigation">
    <div className="conversation-heading"><Typography.Title level={3}>Conversations</Typography.Title><Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>New conversation</Button></div>
    {state.error && <Alert type="error" showIcon message={state.error} action={<Button size="small" onClick={() => void state.reload()}>Retry</Button>} />}
    {state.isLoading ? <Skeleton active paragraph={{ rows: 4 }} /> : state.conversations.length === 0 ? <Typography.Text type="secondary">No conversations yet.</Typography.Text> : <List dataSource={state.conversations} renderItem={(item) => <List.Item className={item.id === state.selectedConversationId ? "conversation-item selected" : "conversation-item"} aria-selected={item.id === state.selectedConversationId} onClick={() => state.selectConversation(item.id)} actions={[<Button aria-label={`Delete ${item.title}`} type="text" danger icon={<DeleteOutlined />} disabled={state.isMutating} onClick={(event) => { event.stopPropagation(); Modal.confirm({ title: "Delete conversation?", content: "This conversation will be permanently deleted.", okText: "Delete", okButtonProps: { danger: true }, onOk: () => state.deleteConversation(item.id) }); }} />]}><List.Item.Meta title={item.title} description={new Date(item.created_at).toLocaleString()} /></List.Item>} />}
    <Modal title="New conversation" open={open} onCancel={() => setOpen(false)} onOk={() => void submit()} confirmLoading={state.isMutating}><Form form={form} layout="vertical"><Form.Item name="title" label="Title" rules={[{ max: 200, message: "Title must be 200 characters or fewer." }]}><Input autoFocus placeholder="New conversation" /></Form.Item></Form></Modal>
  </aside>;
}
