import { Button, Typography } from "antd";

const prompts = [
  "Describe a manufacturing question",
  "Test a synthetic analysis scenario",
  "Summarize the current conversation",
];

type Props = { onPromptSelect: (prompt: string) => void };

export default function EmptyConversation({ onPromptSelect }: Props) {
  return <div className="empty-conversation">
    <Typography.Title level={3}>Start with a question</Typography.Title>
    <Typography.Paragraph type="secondary">Use this workspace to explore a synthetic industrial analysis conversation.</Typography.Paragraph>
    <div className="prompt-suggestions" aria-label="Prompt suggestions">
      {prompts.map((prompt) => <Button key={prompt} type="text" onClick={() => onPromptSelect(prompt)}>{prompt}</Button>)}
    </div>
  </div>;
}
