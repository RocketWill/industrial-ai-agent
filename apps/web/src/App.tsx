import {
  Alert,
  Badge,
  Button,
  Card,
  ConfigProvider,
  Spin,
  Typography,
} from "antd";

import { useHealth, type HealthStatus } from "./hooks/useHealth";
import { useConversations } from "./hooks/useConversations";
import ConversationNavigation from "./components/ConversationNavigation";
import ConversationWorkspace from "./components/ConversationWorkspace";
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
  const { status, checkAgain } = useHealth();
  const conversations = useConversations();

  return (
    <ConfigProvider
      theme={{
        token: {
          borderRadius: 8,
          colorBgBase: "#f7f9fc",
          colorError: "#c9362b",
          colorPrimary: "#1677ff",
          colorSuccess: "#16803c",
          colorText: "#111827",
          fontFamily:
            '"Open Sans", Inter, ui-sans-serif, system-ui, -apple-system, sans-serif',
        },
      }}
    >
      <main className="application-shell">
        <header className="identity-area">
          <Text className="eyebrow">Foundation status</Text>
          <Title level={1}>Industrial AI Agent</Title>
        </header>
        <div className="conversation-layout">
          <ConversationNavigation state={conversations} />
          <ConversationWorkspace conversationId={conversations.selectedConversationId} />
        </div>
        <Card className="health-card" title="API connection">
          <HealthStatusPanel
            status={status}
            onCheckAgain={() => void checkAgain()}
          />
        </Card>
      </main>
    </ConfigProvider>
  );
}
