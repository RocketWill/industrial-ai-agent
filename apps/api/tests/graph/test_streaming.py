from collections.abc import Iterator, Sequence

import pytest

from industrial_agent.graph.errors import GraphExecutionError
from industrial_agent.graph.runner import (
    run_stream_exchange,
    run_stream_tool_exchange,
)
from industrial_agent.llm.types import ChatMessage, CompletionResult, ToolCall
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


def test_stream_tool_runner_persists_production_summary_before_assistant_event(
    database_session,
) -> None:
    conversation = create_conversation(database_session, title="Streaming graph")

    def complete_with_tools(_messages, _tools) -> CompletionResult:
        return CompletionResult(
            content=None,
            tool_calls=(
                ToolCall(
                    call_id="call-001",
                    name="get_production_summary",
                    arguments={
                        "equipment_id": "AOI-WAFER-01",
                        "start": "2026-01-15T15:00:00Z",
                        "end": "2026-01-15T18:00:00Z",
                    },
                ),
            ),
        )

    def stream_with_tool_result(_messages, _tool_result):
        yield "The synthetic yield is 85.67%."

    events = []
    for event in run_stream_tool_exchange(
        database_session,
        conversation_id=conversation.id,
        content="What is the production yield for AOI-WAFER-01?",
        complete_with_tools=complete_with_tools,
        stream_with_tool_result=stream_with_tool_result,
    ):
        if event.kind == "tool_result":
            messages = list_messages(database_session, conversation.id)
            assert [message.role for message in messages] == ["user"]
            assert all(message.evidence_snapshot is None for message in messages)
        events.append(event)

    assistant_event = events[-1]
    assert assistant_event.kind == "assistant_message"
    assistant_message = assistant_event.payload
    assert assistant_message.evidence_snapshot is not None
    assert assistant_message.evidence_snapshot["kind"] == "production_summary"
    assert (
        assistant_message.evidence_snapshot["production_summary"]["inspected_wafers"]
        == 300
    )
