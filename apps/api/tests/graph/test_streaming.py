from collections.abc import Iterator, Sequence

import pytest

from industrial_agent.graph.errors import GraphExecutionError
from industrial_agent.graph.runner import run_stream_exchange
from industrial_agent.llm.types import ChatMessage
from industrial_agent.services.conversation import create_conversation
from industrial_agent.services.message import list_messages


def test_stream_runner_yields_ordered_user_tokens_and_assistant(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Streaming graph")

    def stream(messages: Sequence[ChatMessage]) -> Iterator[str]:
        assert [message.content for message in messages] == ["Question"]
        yield "First "
        yield "answer."

    events = list(
        run_stream_exchange(
            database_session,
            conversation_id=conversation.id,
            content="Question",
            stream=stream,
        )
    )

    assert [event.kind for event in events] == [
        "user_message",
        "token",
        "token",
        "assistant_message",
    ]
    assert events[1].payload == {"text": "First "}
    assert events[3].payload.content == "First answer."


@pytest.mark.parametrize("chunks", [[], ["", "  "]])
def test_stream_runner_does_not_persist_empty_assistant(
    database_session,
    chunks: list[str],
) -> None:
    conversation = create_conversation(database_session, title="Streaming graph")

    def stream(_: Sequence[ChatMessage]) -> Iterator[str]:
        yield from chunks

    with pytest.raises(GraphExecutionError, match="empty_response"):
        list(
            run_stream_exchange(
                database_session,
                conversation_id=conversation.id,
                content="Question",
                stream=stream,
            )
        )

    assert [message.role for message in list_messages(
        database_session, conversation.id
    )] == ["user"]


def test_stream_runner_ignores_non_string_deltas(database_session) -> None:
    conversation = create_conversation(database_session, title="Streaming graph")

    def stream(_: Sequence[ChatMessage]):
        yield None
        yield "Answer"

    events = list(
        run_stream_exchange(
            database_session,
            conversation_id=conversation.id,
            content="Question",
            stream=stream,
        )
    )

    assert [event.kind for event in events] == [
        "user_message",
        "token",
        "assistant_message",
    ]
