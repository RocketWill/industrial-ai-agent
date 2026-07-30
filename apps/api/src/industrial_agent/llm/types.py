from dataclasses import dataclass
from typing import Literal, cast

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
