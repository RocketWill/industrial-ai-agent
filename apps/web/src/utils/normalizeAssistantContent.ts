const COMPLETE_THINK_BLOCK = /<think\b[^>]*>[\s\S]*?<\/think\s*>/gi;
const OPEN_THINK_TAG = /<think\b[^>]*>[\s\S]*$/gi;
const CLOSE_THINK_TAG = /<\/think\s*>/gi;

export function normalizeAssistantContent(content: string): string {
  return content
    .replace(COMPLETE_THINK_BLOCK, "")
    .replace(OPEN_THINK_TAG, "")
    .replace(CLOSE_THINK_TAG, "")
    .trim();
}
