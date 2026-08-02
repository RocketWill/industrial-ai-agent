import { Prompts } from "@ant-design/x";
import { Typography } from "antd";

const prompts = [
  "What is the production yield?",
  "Show the defect distribution for this context",
  "Summarize the current conversation",
].map((label) => ({ key: label, label }));

type Props = { onPromptSelect: (prompt: string) => void };

export default function EmptyConversation({ onPromptSelect }: Props) {
  return (
    <div className="empty-conversation">
      <div className="empty-mark" aria-hidden="true" />
      <Typography.Title level={2}>Start an analysis</Typography.Title>
      <Typography.Paragraph type="secondary">
        Ask about this synthetic manufacturing context or continue with a suggested question.
      </Typography.Paragraph>
      <Prompts
        className="prompt-suggestions"
        title="Suggested questions"
        items={prompts}
        vertical
        fadeIn={false}
        onItemClick={({ data }) => onPromptSelect(String(data.label))}
      />
    </div>
  );
}
