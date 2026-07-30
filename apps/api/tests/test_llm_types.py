import pytest

from industrial_agent.llm.types import ChatMessage


@pytest.mark.parametrize("role", ["user", "assistant"])
def test_chat_message_accepts_supported_roles(role: str) -> None:
    message = ChatMessage(role=role, content="  Explain the alarm  ")

    assert message.role == role
    assert message.content == "Explain the alarm"


def test_chat_message_rejects_unsupported_role() -> None:
    with pytest.raises(ValueError, match="Unsupported chat role"):
        ChatMessage(role="system", content="Prompt")


@pytest.mark.parametrize("content", ["", "   "])
def test_chat_message_rejects_empty_content(content: str) -> None:
    with pytest.raises(ValueError, match="content must not be empty"):
        ChatMessage(role="user", content=content)
