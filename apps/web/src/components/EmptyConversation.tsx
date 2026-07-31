import { Button, Typography } from "antd";

const prompts = [
  "Summarize the latest production status",
  "Analyze yield changes in the last shift",
  "Explain the most frequent alarms",
  "Compare defect counts between two periods",
];

type Props = { onPromptSelect: (prompt: string) => void };

export default function EmptyConversation({ onPromptSelect }: Props) {
  return <div className="empty-conversation">
    <Typography.Title level={3}>What would you like to inspect?</Typography.Title>
    <Typography.Paragraph type="secondary">Ask about equipment status, yield, alarms, or production summaries.</Typography.Paragraph>
    <div className="prompt-suggestions" aria-label="Prompt suggestions">
      {prompts.map((prompt) => <Button key={prompt} type="text" onClick={() => onPromptSelect(prompt)}>{prompt}</Button>)}
    </div>
  </div>;
}
