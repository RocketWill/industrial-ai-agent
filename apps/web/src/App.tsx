import { Alert, Badge, Button, Drawer, Modal, Spin, Typography } from "antd";
import { XProvider } from "@ant-design/x";
import { useCallback, useMemo, useState, type CSSProperties } from "react";

import { useHealth, type HealthStatus } from "./hooks/useHealth";
import { useConversations } from "./hooks/useConversations";
import { useWorkspaceContext } from "./hooks/useWorkspaceContext";
import AnalysisContext from "./components/AnalysisContext";
import ConversationNavigation from "./components/ConversationNavigation";
import ConversationWorkspace from "./components/ConversationWorkspace";
import { colors } from "./theme/colors";
import { layoutTokens, workbenchTheme } from "./theme/theme";
import "./App.css";

const { Text, Title } = Typography;

type HealthStatusPanelProps = { status: HealthStatus; onCheckAgain: () => void };

function HealthStatusPanel({ status, onCheckAgain }: HealthStatusPanelProps) {
  if (status === "checking") {
    return <div className="health-status" aria-live="polite"><Spin size="small" /><div><Title level={3}>Checking API connection</Title><Text>Waiting for the API process.</Text></div><Button loading disabled>Check again</Button></div>;
  }
  if (status === "connected") {
    return <div className="health-status" aria-live="polite"><Badge status="success" text="Connected" /><Text>The API process is responding.</Text><Button onClick={onCheckAgain}>Check again</Button></div>;
  }
  return <div className="health-status" aria-live="polite"><Alert title="API unavailable" description="Start the backend, then check the connection again." type="error" showIcon /><Button onClick={onCheckAgain}>Check again</Button></div>;
}

export default function App() {
  const [modal, modalContextHolder] = Modal.useModal();
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [contextDirty, setContextDirty] = useState(false);
  const [contextResetToken, setContextResetToken] = useState(0);
  const { status, checkAgain } = useHealth();
  const conversations = useConversations();
  const contextState = useWorkspaceContext(conversations.selectedConversationId);
  const selectedConversation = useMemo(
    () => conversations.conversations.find((item) => item.id === conversations.selectedConversationId) ?? null,
    [conversations.conversations, conversations.selectedConversationId],
  );

  const discardContext = useCallback((action: () => void) => {
    if (!contextDirty) { action(); return; }
    modal.confirm({
      title: "Discard context changes?",
      content: "The unsaved device, lot, and time range changes will be lost.",
      okText: "Discard",
      okButtonProps: { color: "danger", variant: "solid" },
      onOk: () => { setContextResetToken((value) => value + 1); setContextDirty(false); action(); },
    });
  }, [contextDirty, modal]);

  const selectConversation = useCallback((id: string) => {
    discardContext(() => { conversations.selectConversation(id); setNavigationOpen(false); });
  }, [conversations, discardContext]);

  const closeContext = useCallback(() => {
    discardContext(() => setContextOpen(false));
  }, [discardContext]);

  const workbenchStyle = {
    "--color-sidebar": colors.sidebar,
    "--color-surface": colors.bgContainer,
    "--color-elevated": colors.bgElevated,
    "--color-input": colors.input,
    "--color-border": colors.border,
    "--color-border-subtle": colors.borderSubtle,
    "--color-primary": colors.primary,
    "--color-accent": colors.accent,
    "--color-text-primary": colors.textPrimary,
    "--color-text-secondary": colors.textSecondary,
    "--color-text-muted": colors.textDescription,
    "--panel-radius": `${layoutTokens.radiusPanel}px`,
  } as CSSProperties;

  const navigation = <ConversationNavigation state={conversations} onSelectConversation={selectConversation} footer={<HealthStatusPanel status={status} onCheckAgain={() => void checkAgain()} />} />;
  const context = <AnalysisContext state={contextState} disabled={!conversations.selectedConversationId} resetToken={contextResetToken} onDirtyChange={setContextDirty} />;

  return (
    <XProvider theme={workbenchTheme}>
      {modalContextHolder}
      <main className="application-shell" style={workbenchStyle}>
        <div className="workbench-layout">
          <div className="desktop-sidebar">{navigation}</div>
          <ConversationWorkspace
            conversationId={conversations.selectedConversationId}
            conversationTitle={selectedConversation?.title ?? null}
            onOpenNavigation={() => setNavigationOpen(true)}
            onOpenContext={() => setContextOpen(true)}
          />
          <div className="desktop-inspector">{context}</div>
        </div>
        <Drawer title="Conversations" placement="left" open={navigationOpen} onClose={() => setNavigationOpen(false)} size={320} classNames={{ body: "navigation-drawer-body" }}>{navigation}</Drawer>
        <Drawer title="Analysis context" placement="right" open={contextOpen} onClose={closeContext} size={360} classNames={{ body: "context-drawer-body" }}>{context}</Drawer>
      </main>
    </XProvider>
  );
}
