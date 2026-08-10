import { Alert, Avatar, BorderBeam, Button, Skeleton, Tag, Typography } from "antd";
import type { BorderBeamGradient } from "antd";
import { ArrowDownOutlined, FileTextOutlined, MenuOutlined, RobotOutlined, SettingOutlined, UserOutlined } from "@ant-design/icons";
import { Bubble, Sender } from "@ant-design/x";
import type { BubbleItemType } from "@ant-design/x";
import { useCallback, useLayoutEffect, useMemo, useRef, useState, type ElementRef, type UIEvent } from "react";

import { useMessages } from "../hooks/useMessages";
import EmptyConversation from "./EmptyConversation";
import MessageItem from "./MessageItem";

type Props = {
  conversationId: string | null;
  conversationTitle: string | null;
  onOpenNavigation: () => void;
  onOpenContext: () => void;
  onOpenDocuments?: () => void;
  documentsOpen?: boolean;
};

const placeholderId = "00000000-0000-1000-8000-000000000000";
const assistantBeamColor: BorderBeamGradient = [
  { color: "#ff7a45", percent: 0 },
  { color: "#f759ab", percent: 24 },
  { color: "#9254de", percent: 50 },
  { color: "#597ef7", percent: 76 },
  { color: "#36cfc9", percent: 100 },
];

export default function ConversationWorkspace({ conversationId, conversationTitle, onOpenNavigation, onOpenContext, onOpenDocuments = () => undefined, documentsOpen = false }: Props) {
  const state = useMessages(conversationId);
  const listRef = useRef<ElementRef<typeof Bubble.List>>(null);
  const documentsTriggerRef = useRef<HTMLButtonElement>(null);
  const documentsWasOpen = useRef(false);
  const pendingInitialScroll = useRef(true);
  const initialScrollFrame = useRef<number | null>(null);
  const lastScrolledMessageKey = useRef("");
  const [followLatest, setFollowLatest] = useState(true);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const latestMessage = state.messages[state.messages.length - 1];
  const latestMessageKey = latestMessage ? `${latestMessage.id}:${latestMessage.content.length}` : "";

  const submit = useCallback((value?: string) => {
    if (value !== undefined && value !== state.draft) state.setDraft(value);
    setFollowLatest(true);
    setShowScrollButton(false);
    if (state.messages.length > 0) {
      listRef.current?.scrollTo({ top: "bottom", behavior: "auto" });
    }
    void state.send(value);
  }, [state]);

  useLayoutEffect(() => {
    if (documentsOpen) {
      documentsWasOpen.current = true;
    } else if (documentsWasOpen.current) {
      documentsWasOpen.current = false;
      documentsTriggerRef.current?.focus();
    }
  }, [documentsOpen]);

  const items = useMemo<BubbleItemType[]>(() => state.messages.map((message, index) => {
    const isActiveAssistant = message.id === placeholderId;
    const evidence = index === state.messages.length - 1 && message.role === "assistant" ? state.evidence : null;
    const status = isActiveAssistant
      ? state.runState.phase === "failed" ? "error"
        : state.runState.phase === "cancelled" ? "abort"
          : "updating"
      : "success";
    const isAnimatedAssistant = message.role === "assistant" && status === "updating" && state.isStreaming;
    return {
      key: message.id,
      role: message.role === "user" ? "user" : "ai",
      content: message.content,
      status,
      streaming: isActiveAssistant && state.isStreaming,
      classNames: message.role === "assistant"
        ? { content: `assistant-bubble-content${isAnimatedAssistant ? " assistant-bubble-streaming" : ""}` }
        : undefined,
      styles: isAnimatedAssistant ? { content: { padding: 0 } } : undefined,
      avatar: <Avatar icon={message.role === "user" ? <UserOutlined /> : <RobotOutlined />} />,
      contentRender: () => {
        const messageItem = (
        <MessageItem
          message={message}
          evidence={evidence}
          isStreaming={isActiveAssistant && state.isStreaming}
          runLabel={isActiveAssistant ? state.runState.label : null}
          showSuggestedActions={index === state.messages.length - 1 && message.role === "assistant"}
          suggestedActionsDisabled={state.isSending}
          onSuggestedAction={submit}
        />
        );

        return isAnimatedAssistant ? (
          <BorderBeam color={assistantBeamColor} duration={6.5} lineWidth={1} outset={0} size={100}>
            <div className="assistant-beam-host">{messageItem}</div>
          </BorderBeam>
        ) : messageItem;
      },
    };
  }), [state.evidence, state.isSending, state.isStreaming, state.messages, state.runState, submit]);

  useLayoutEffect(() => {
    pendingInitialScroll.current = true;
    setFollowLatest(true);
    setShowScrollButton(false);
  }, [conversationId]);

  useLayoutEffect(() => {
    if (!state.isLoading && state.messages.length > 0 && pendingInitialScroll.current) {
      pendingInitialScroll.current = false;
      if (initialScrollFrame.current !== null) cancelAnimationFrame(initialScrollFrame.current);
      initialScrollFrame.current = requestAnimationFrame(() => {
        listRef.current?.scrollTo({ top: "bottom", behavior: "auto" });
        lastScrolledMessageKey.current = latestMessageKey;
        initialScrollFrame.current = null;
      });
    }
    return () => {
      if (initialScrollFrame.current !== null) cancelAnimationFrame(initialScrollFrame.current);
      initialScrollFrame.current = null;
    };
  }, [conversationId, latestMessageKey, state.isLoading, state.messages.length]);

  useLayoutEffect(() => {
    if (followLatest && state.isStreaming && latestMessageKey && lastScrolledMessageKey.current !== latestMessageKey) {
      listRef.current?.scrollTo({ top: "bottom", behavior: "auto" });
      lastScrolledMessageKey.current = latestMessageKey;
    }
  }, [followLatest, latestMessageKey, state.isStreaming]);

  const handleScroll = useCallback((event: UIEvent<HTMLDivElement>) => {
    const nearLatest = Math.abs(event.currentTarget.scrollTop) <= 96;
    setFollowLatest(nearLatest);
    setShowScrollButton(!nearLatest);
  }, []);

  const scrollToBottom = () => {
    setFollowLatest(true);
    setShowScrollButton(false);
    listRef.current?.scrollTo({ top: "bottom", behavior: "auto" });
    lastScrolledMessageKey.current = latestMessageKey;
  };

  return (
    <section className="conversation-workspace" aria-label="Conversation workspace">
      <header className="chat-header">
        <Button className="navigation-trigger" variant="text" shape="circle" icon={<MenuOutlined />} aria-label="Open navigation" onClick={onOpenNavigation} />
        <div className="chat-title">
          <Typography.Text className="section-label">Current conversation</Typography.Text>
          <Typography.Title level={2}>{conversationTitle ?? "Select a conversation"}</Typography.Title>
        </div>
        <div className="chat-header-actions">
          <Tag color="cyan">Synthetic Demo</Tag>
          <Button
            ref={documentsTriggerRef}
            className="documents-trigger"
            icon={<FileTextOutlined />}
            aria-label="Documents"
            aria-haspopup="dialog"
            aria-expanded={documentsOpen}
            onClick={onOpenDocuments}
          >
            Documents
          </Button>
          <Button className="context-trigger" variant="text" shape="circle" icon={<SettingOutlined />} aria-label="Open analysis context" disabled={!conversationId} onClick={onOpenContext} />
        </div>
      </header>
      {state.error && <Alert className="workspace-alert" type="error" showIcon title={state.error} action={<Button size="small" onClick={() => void state.reload()}>Reload history</Button>} />}
      <div className="chat-canvas">
        {state.isLoading ? (
          <Skeleton className="message-skeleton" active paragraph={{ rows: 7 }} />
        ) : !conversationId ? (
          <div className="conversation-empty-select">Select or create a conversation to begin.</div>
        ) : state.messages.length === 0 ? (
          <EmptyConversation onPromptSelect={state.setDraft} />
        ) : (
          <Bubble.List
            ref={listRef}
            className="message-list"
            items={items}
            autoScroll
            onScroll={handleScroll}
            classNames={{ scroll: "message-scroll-region" }}
            role={{
              user: { placement: "end", variant: "filled", shape: "corner" },
              ai: {
                placement: "start",
                variant: "outlined",
                shape: "default",
              },
            }}
          />
        )}
        {showScrollButton && <Button className="scroll-bottom-button" shape="circle" icon={<ArrowDownOutlined />} aria-label="Jump to latest message" onClick={scrollToBottom} />}
      </div>
      <div className="composer-shell">
        <Sender
          value={state.draft}
          onChange={state.setDraft}
          onSubmit={submit}
          onCancel={state.cancelStreaming}
          loading={state.isStreaming}
          disabled={!conversationId || state.isSending}
          submitType="enter"
          placeholder={conversationId ? "Ask about this synthetic analysis" : "Select a conversation first"}
          autoSize={{ minRows: 2, maxRows: 6 }}
        />
        <Typography.Text type="secondary" className="composer-hint">Enter to send. Shift+Enter for a new line.</Typography.Text>
      </div>
    </section>
  );
}
