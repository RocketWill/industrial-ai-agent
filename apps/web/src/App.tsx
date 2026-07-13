import {
  Alert,
  Badge,
  Button,
  ConfigProvider,
  Drawer,
  Spin,
  Typography,
} from "antd";
import { MenuOutlined } from "@ant-design/icons";
import { useState } from "react";
import type { CSSProperties } from "react";

import { useHealth, type HealthStatus } from "./hooks/useHealth";
import { useConversations } from "./hooks/useConversations";
import ConversationNavigation from "./components/ConversationNavigation";
import ConversationWorkspace from "./components/ConversationWorkspace";
import { colors } from "./theme/colors";
import { antdTheme, layoutTokens, spacing } from "./theme/theme";
import "./App.css";

const { Text, Title } = Typography;

type HealthStatusPanelProps = {
  status: HealthStatus;
  onCheckAgain: () => void;
};

function HealthStatusPanel({
  status,
  onCheckAgain,
}: HealthStatusPanelProps) {
  if (status === "checking") {
    return (
      <div className="health-status" aria-live="polite">
        <Spin size="small" />
        <div>
          <Title level={3}>Checking API connection</Title>
          <Text>The application is checking whether the API process responds.</Text>
        </div>
        <Button loading disabled onClick={onCheckAgain}>
          Check again
        </Button>
      </div>
    );
  }

  if (status === "connected") {
    return (
      <div className="health-status" aria-live="polite">
        <Badge status="success" text="Connected" />
        <Text>The API process is responding.</Text>
        <Button onClick={onCheckAgain}>Check again</Button>
      </div>
    );
  }

  return (
    <div className="health-status" aria-live="polite">
      <Alert
        message="API unavailable"
        description="The application could not reach the API. Check that the backend is running, then try again."
        type="error"
        showIcon
      />
      <Button onClick={onCheckAgain}>Check again</Button>
    </div>
  );
}

export default function App() {
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const { status, checkAgain } = useHealth();
  const conversations = useConversations();

  const workbenchStyle = {
    "--app-padding": `${layoutTokens.appPadding}px`,
    "--app-gap": `${layoutTokens.appGap}px`,
    "--sidebar-width": `${layoutTokens.sidebarWidth}px`,
    "--sidebar-padding": `${layoutTokens.sidebarPadding}px`,
    "--workspace-min-width": `${layoutTokens.workspaceMinWidth}px`,
    "--workspace-bar-height": `${layoutTokens.workspaceBarHeight}px`,
    "--panel-padding": `${layoutTokens.panelPadding}px`,
    "--composer-padding": `${layoutTokens.composerPadding}px`,
    "--conversation-item-padding-inline": `${layoutTokens.conversationItemPaddingInline}px`,
    "--message-item-padding-inline": `${layoutTokens.messageItemPaddingInline}px`,
    "--control-min-height": `${layoutTokens.controlMinHeight}px`,
    "--panel-radius": `${layoutTokens.radiusPanel}px`,
    "--space-lg": `${spacing.lg}px`,
    "--space-xxl": `${spacing.xxl}px`,
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
    "--color-description": colors.textDescription,
  } as CSSProperties;

  return (
    <ConfigProvider
      theme={antdTheme}
    >
      <main className="application-shell" style={workbenchStyle}>
        <div className="workbench-layout">
          <div className="desktop-sidebar"><ConversationNavigation state={conversations} footer={<HealthStatusPanel status={status} onCheckAgain={() => void checkAgain()} />} /></div>
          <section className="workspace-column">
            <header className="workspace-bar">
              <div className="workspace-title"><Button className="mobile-menu-button" type="text" icon={<MenuOutlined />} aria-label="Open navigation" onClick={() => setMobileNavigationOpen(true)} /><div><Text className="workspace-eyebrow">Industrial AI Agent</Text><Title level={2}>Analysis workspace</Title></div></div>
              <Badge className="synthetic-data-badge" color="#37C6D0" text="Synthetic Demo" />
            </header>
            <ConversationWorkspace conversationId={conversations.selectedConversationId} />
          </section>
        </div>
        <Drawer title="Navigation" placement="left" open={mobileNavigationOpen} onClose={() => setMobileNavigationOpen(false)} width={280}><ConversationNavigation state={conversations} footer={<HealthStatusPanel status={status} onCheckAgain={() => void checkAgain()} />} /></Drawer>
      </main>
    </ConfigProvider>
  );
}
