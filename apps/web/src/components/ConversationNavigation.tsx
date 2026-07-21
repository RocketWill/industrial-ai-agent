import { useMemo, useState, type ReactNode } from "react";
import { Alert, Form, Input, Modal, Skeleton, Typography } from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Conversations } from "@ant-design/x";
import type { ConversationItemType } from "@ant-design/x";

import type { Conversation } from "../api/conversations";
import type { ConversationState } from "../hooks/useConversations";

type Props = {
  state: ConversationState;
  footer: ReactNode;
  onSelectConversation: (id: string) => void;
};

function conversationGroup(createdAt: string): string {
  const created = new Date(createdAt);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const age = today.getTime() - new Date(created.getFullYear(), created.getMonth(), created.getDate()).getTime();
  if (age <= 0) return "Today";
  if (age <= 7 * 24 * 60 * 60 * 1000) return "Previous 7 days";
  return "Older";
}

export default function ConversationNavigation({ state, footer, onSelectConversation }: Props) {
  const [modal, modalContextHolder] = Modal.useModal();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm<{ title?: string }>();
  const items = useMemo<ConversationItemType[]>(() => state.conversations.map((item: Conversation) => ({
    key: item.id,
    label: item.title,
    group: conversationGroup(item.created_at),
  })), [state.conversations]);

  const submit = async () => {
    const values = await form.validateFields();
    await state.createConversation(values.title);
    form.resetFields();
    setOpen(false);
  };

  return (
    <aside className="conversation-navigation" aria-label="Conversation navigation">
      {modalContextHolder}
      <header className="sidebar-brand">
        <div className="brand-mark" aria-hidden="true" />
        <div>
          <Typography.Title level={3}>Industrial AI Agent</Typography.Title>
          <Typography.Text type="secondary">Semiconductor analysis</Typography.Text>
        </div>
      </header>
      <Typography.Text className="section-label">Recent conversations</Typography.Text>
      {state.error && <Alert type="error" showIcon title={state.error} action={<button className="text-action" onClick={() => void state.reload()}>Retry</button>} />}
      {state.isLoading ? (
        <Skeleton active paragraph={{ rows: 5 }} />
      ) : (
        <Conversations
          className="conversation-list"
          items={items}
          activeKey={state.selectedConversationId ?? undefined}
          onActiveChange={onSelectConversation}
          groupable={{ collapsible: false }}
          creation={{
            label: "New analysis",
            icon: <PlusOutlined />,
            disabled: state.isMutating,
            onClick: () => setOpen(true),
          }}
          menu={(item) => ({
            items: [{ key: "delete", label: "Delete", danger: true, icon: <DeleteOutlined /> }],
            onClick: ({ domEvent }) => {
              domEvent.stopPropagation();
              modal.confirm({
                title: "Delete conversation?",
                content: "This conversation will be permanently deleted.",
                okText: "Delete",
                okButtonProps: { color: "danger", variant: "solid" },
                onOk: () => state.deleteConversation(item.key),
              });
            },
          })}
        />
      )}
      {!state.isLoading && state.conversations.length === 0 && <Typography.Text type="secondary" className="conversation-empty">No conversations yet.</Typography.Text>}
      <footer className="sidebar-footer">{footer}</footer>
      <Modal
        title="New conversation"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => void submit()}
        confirmLoading={state.isMutating}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="Title" rules={[{ max: 200, message: "Title must be 200 characters or fewer." }]}>
            <Input autoFocus placeholder="New conversation" />
          </Form.Item>
        </Form>
      </Modal>
    </aside>
  );
}
