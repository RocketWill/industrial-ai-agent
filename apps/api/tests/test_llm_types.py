import pytest

from industrial_agent.llm.types import (
    ChatMessage,
    FinalAnswerDelta,
    ReasoningDelta,
    ReasoningTruncated,
    StreamItem,
)


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


def test_stream_items_keep_final_answer_and_reasoning_distinct() -> None:
    final_answer = FinalAnswerDelta(content="The alarm is acknowledged.")
    reasoning = ReasoningDelta(content="I matched the alarm code to the fixture.")

    assert final_answer.content == "The alarm is acknowledged."
    assert reasoning.content == "I matched the alarm code to the fixture."
    assert isinstance(final_answer, StreamItem)
    assert isinstance(reasoning, StreamItem)
    assert not isinstance(final_answer, ReasoningDelta)
    assert not isinstance(reasoning, FinalAnswerDelta)


def test_stream_items_include_one_truncation_signal() -> None:
    truncated = ReasoningTruncated()

    assert isinstance(truncated, StreamItem)
