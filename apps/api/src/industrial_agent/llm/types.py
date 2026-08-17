from dataclasses import dataclass
from typing import Any, Literal, cast

type ChatRole = Literal["user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: ChatRole
    content: str

    def __post_init__(self) -> None:
        if self.role not in ("user", "assistant"):
            raise ValueError(f"Unsupported chat role: {self.role}")
        normalized = self.content.strip()
        if not normalized:
            raise ValueError("Chat message content must not be empty")
        object.__setattr__(self, "role", cast(ChatRole, self.role))
        object.__setattr__(self, "content", normalized)


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """OpenAI-compatible function tool schema."""

    name: str
    description: str
    parameters: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Tool name must not be empty")
        if not self.description.strip():
            raise ValueError("Tool description must not be empty")
        if self.parameters.get("type") != "object":
            raise ValueError("Tool parameters must be an object schema")

    def as_payload(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One parsed model request to invoke a named tool."""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """A tool result paired with the model Tool Call that requested it."""

    call_id: str
    name: str
    arguments: dict[str, Any]
    content: str


@dataclass(frozen=True, slots=True)
class FinalAnswerDelta:
    """One literal final-answer fragment from a streaming completion."""

    content: str


@dataclass(frozen=True, slots=True)
class ReasoningDelta:
    """One literal provider-reasoning fragment from a streaming completion."""

    content: str


@dataclass(frozen=True, slots=True)
class ReasoningTruncated:
    """Marker emitted once when provider reasoning reaches its display cap."""


StreamItem = FinalAnswerDelta | ReasoningDelta | ReasoningTruncated


@dataclass(frozen=True, slots=True)
class CompletionResult:
    """A model completion containing text, one tool call, or neither."""

    content: str | None
    tool_calls: tuple[ToolCall, ...] = ()
