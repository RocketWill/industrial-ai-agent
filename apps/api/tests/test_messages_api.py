import json
import socket
import threading
import time
from collections.abc import Generator
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request
from uvicorn import Config, Server

import industrial_agent.graph.runner as runner_module
import industrial_agent.graph.workflow as workflow_module
from industrial_agent.database.session import get_db_session
from industrial_agent.graph.combined import CombinedToolUnavailable
from industrial_agent.llm.errors import (
    LLMConfigurationError,
    LLMConnectionError,
    LLMResponseError,
    LLMServiceError,
)
from industrial_agent.llm.openai_compatible import (
    OpenAICompatibleChatAdapter,
)
from industrial_agent.llm.types import CompletionResult, ToolCall
from industrial_agent.main import create_app
from industrial_agent.models.message import Message
from industrial_agent.tools.document_search import DocumentSearchResult
from industrial_agent.tools.production import ProductionSummaryResult

UNKNOWN_CONVERSATION_ID = "00000000-0000-0000-0000-000000000099"


@pytest.fixture(autouse=True)
def deterministic_router_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRouterAdapter:
        def __enter__(self) -> "FakeRouterAdapter":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def complete_with_tools(self, _messages, *, tools, tool_call=None):
            assert tool_call is None
            assert tools[0].name == "classify_request"
            return CompletionResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        call_id="route-1",
                        name="classify_request",
                        arguments={
                            "intent": "general",
                            "reason_code": "general_request",
                        },
                    ),
                ),
            )

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "router_from_settings",
        classmethod(lambda cls, settings: FakeRouterAdapter()),
    )


@pytest.fixture
def successful_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAdapter:
        def __enter__(self) -> "FakeAdapter":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def complete(self, _: object) -> str:
            return "Assistant answer"

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FakeAdapter()),
    )


def create_conversation(client: TestClient, title: str = "Messages") -> dict:
    response = client.post("/conversations", json={"title": title})
    assert response.status_code == 201
    return response.json()


def test_create_message_returns_persisted_user_and_assistant_messages(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)

    class FakeAdapter:
        def __enter__(self) -> "FakeAdapter":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def complete(self, _: object) -> str:
            return "Assistant answer"

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FakeAdapter()),
    )

    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"content": "  Check chamber pressure  "},
    )

    assert response.status_code == 201
    payload = response.json()
    assert UUID(payload["user_message"]["id"])
    assert payload["user_message"]["conversation_id"] == conversation["id"]
    assert payload["user_message"]["role"] == "user"
    assert payload["user_message"]["content"] == "Check chamber pressure"
    assert payload["assistant_message"]["role"] == "assistant"
    assert payload["assistant_message"]["content"] == "Assistant answer"
    assert payload["user_message"]["suggested_actions"] == []
    assert payload["assistant_message"]["suggested_actions"] == []


def test_explicit_general_route_does_not_construct_router_adapter(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)

    class FakeAnswerAdapter:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def complete(self, _messages):
            return "Hello."

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FakeAnswerAdapter()),
    )
    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "router_from_settings",
        classmethod(
            lambda cls, settings: (_ for _ in ()).throw(
                AssertionError("deterministic route must not construct router")
            )
        ),
    )

    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"content": "Hello, what can you do?"},
    )

    assert response.status_code == 201
    assert response.json()["assistant_message"]["content"] == "Hello."


def test_stream_message_returns_ordered_sse_events(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)

    class FakeAdapter:
        def __enter__(self) -> "FakeAdapter":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def stream(self, _: object):
            yield "Hello"
            yield " world"

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FakeAdapter()),
    )

    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages/stream",
        json={"content": "Question"},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    events = [line for line in response.text.splitlines() if line.startswith("event:")]
    assert events == [
        "event: message_started",
        "event: routing_started",
        "event: routing_decided",
        "event: token",
        "event: token",
        "event: message_completed",
    ]
    history = conversation_client.get(
        f"/conversations/{conversation['id']}/messages"
    ).json()
    assert [(item["role"], item["content"]) for item in history] == [
        ("user", "Question"),
        ("assistant", "Hello world"),
    ]


def test_stream_production_message_emits_tool_events(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)
    conversation_client.patch(
        f"/conversations/{conversation['id']}/context",
        json={"device": "AOI-WAFER-01", "time_range": "Last 4 hours"},
    )

    class FakeAdapter:
        def __enter__(self) -> "FakeAdapter":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def complete_with_tools(self, messages, *, tools, tool_call=None):
            from industrial_agent.llm.types import CompletionResult, ToolCall

            if tool_call is None:
                return CompletionResult(
                    content=None,
                    tool_calls=(
                        ToolCall(
                            call_id="call-001",
                            name="get_production_summary",
                            arguments={
                                "equipment_id": "AOI-WAFER-01",
                                "start": "2026-01-15T13:00:00Z",
                                "end": "2026-01-15T17:00:00Z",
                            },
                        ),
                    ),
                )
            return CompletionResult(content="Yield is 92.5%.")

        def stream_with_tool_result(self, messages, *, tools, tool_call):
            yield "Yield is "
            yield "92.5%."

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FakeAdapter()),
    )
    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages/stream",
        json={"content": "What is the production yield?"},
    )
    assert response.status_code == 200
    events = [line for line in response.text.splitlines() if line.startswith("event:")]
    assert events == [
        "event: message_started",
        "event: routing_started",
        "event: routing_decided",
        "event: tool_call_started",
        "event: tool_result",
        "event: token",
        "event: token",
        "event: message_completed",
    ]
    assert 'data: {"text":"Yield is "}' in response.text
    assert 'data: {"text":"92.5%."}' in response.text


def test_stream_equipment_status_message_emits_recorded_status_evidence(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)
    conversation_client.patch(
        f"/conversations/{conversation['id']}/context",
        json={"device": "AOI-WAFER-01", "time_range": "Last 4 hours"},
    )

    class FakeAdapter:
        def __enter__(self) -> "FakeAdapter":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def complete_with_tools(self, messages, *, tools, tool_call=None):
            from industrial_agent.llm.types import CompletionResult, ToolCall

            assert tools[0].name == "get_equipment_status"
            if tool_call is None:
                return CompletionResult(
                    content=None,
                    tool_calls=(
                        ToolCall(
                            call_id="call-status",
                            name="get_equipment_status",
                            arguments={},
                        ),
                    ),
                )
            return CompletionResult(content="The recorded status is running.")

        def stream_with_tool_result(self, messages, *, tools, tool_call):
            assert tools[0].name == "get_equipment_status"
            assert '"status":"running"' in tool_call.content
            yield "The recorded status is "
            yield "running."

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FakeAdapter()),
    )
    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages/stream",
        json={"content": "What is the equipment status?"},
    )

    assert response.status_code == 200
    events = [line for line in response.text.splitlines() if line.startswith("event:")]
    assert events == [
        "event: message_started",
        "event: routing_started",
        "event: routing_decided",
        "event: tool_call_started",
        "event: tool_result",
        "event: token",
        "event: token",
        "event: message_completed",
    ]
    assert '"equipment_status":{"equipment_id":"AOI-WAFER-01"' in response.text


def test_stream_defect_distribution_message_emits_ranked_evidence(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)
    conversation_client.patch(
        f"/conversations/{conversation['id']}/context",
        json={
            "device": "AOI-WAFER-01",
            "lot": "LOT-DEMO-001",
            "time_range": "Last 4 hours",
        },
    )

    class FakeAdapter:
        def __enter__(self) -> "FakeAdapter":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def complete_with_tools(self, messages, *, tools, tool_call=None):
            from industrial_agent.llm.types import CompletionResult, ToolCall

            assert tools[0].name == "get_defect_distribution"
            return CompletionResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        call_id="call-defects",
                        name="get_defect_distribution",
                        arguments={},
                    ),
                ),
            )

        def stream_with_tool_result(self, messages, *, tools, tool_call):
            assert tools[0].name == "get_defect_distribution"
            assert '"category":"edge-chip"' in tool_call.content
            yield "Edge-chip is the top recorded defect."

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FakeAdapter()),
    )
    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages/stream",
        json={"content": "Show the defect distribution."},
    )

    assert response.status_code == 200
    events = [line for line in response.text.splitlines() if line.startswith("event:")]
    assert events == [
        "event: message_started",
        "event: routing_started",
        "event: routing_decided",
        "event: tool_call_started",
        "event: tool_result",
        "event: token",
        "event: message_completed",
    ]
    assert '"defect_distribution":{"equipment_id":"AOI-WAFER-01"' in response.text
    assert '"category":"edge-chip","count":19' in response.text


def test_stream_document_question_emits_retrieved_source_evidence(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)
    conversation_client.patch(
        f"/conversations/{conversation['id']}/context",
        json={"device": "AOI-WAFER-01", "time_range": "Last 8 hours"},
    )

    class FakeAdapter:
        def __enter__(self) -> "FakeAdapter":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def complete_with_tools(self, messages, *, tools, tool_call=None):
            raise AssertionError("document routing must not ask the model for args")

        def stream_with_tool_result(self, messages, *, tools, tool_call):
            assert tools[0].name == "search_documents"
            assert '"section":"OPTICAL-SIGNAL-LOW"' in tool_call.content
            yield "Check the fictional optical lens cover "
            yield "[aoi-alarm-guide:optical-signal-low:001]."

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FakeAdapter()),
    )
    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages/stream",
        json={
            "content": ("What should an operator check when OPTICAL-SIGNAL-LOW occurs?")
        },
    )

    assert response.status_code == 200
    assert (
        '"document_search":{"query":"What should an operator check when '
        'OPTICAL-SIGNAL-LOW occurs?"'
    ) in response.text
    assert '"section":"OPTICAL-SIGNAL-LOW"' in response.text


def test_stream_combined_request_emits_both_evidence_paths(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)
    conversation_client.patch(
        f"/conversations/{conversation['id']}/context",
        json={"device": "AOI-WAFER-01", "time_range": "Last 8 hours"},
    )

    class FakeAdapter:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def stream_with_tool_result(self, _messages, *, tools, tool_call):
            assert tools[0].name == "combined_evidence"
            payload = json.loads(tool_call.content)
            source_id = payload["documents"]["result"]["sources"][0]["source_id"]
            yield "Combined evidence is available from "
            yield f"{source_id}; the relationship still needs validation."

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FakeAdapter()),
    )
    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages/stream",
        json={"content": "Show production yield and search the documents."},
    )

    assert response.status_code == 200
    assert '"route":"combined"' in response.text
    assert "event: clarification_required" not in response.text
    assert response.text.count("event: tool_call_started") == 2
    assert response.text.count("event: combined_tool_result") == 2
    assert (
        'event: combined_evidence_completed\ndata: {"answer_status":"succeeded"}'
        in response.text
    )
    assert '"path":"manufacturing"' in response.text
    assert '"path":"documents"' in response.text
    assert "event: message_completed" in response.text
    history = conversation_client.get(
        f"/conversations/{conversation['id']}/messages"
    ).json()
    assert history[-1]["suggested_actions"] == []


@pytest.mark.parametrize(
    ("question", "manufacturing_kind"),
    [
        ("Show production yield and search the optical alarm guide.", "production"),
        (
            "Show equipment status and search the optical alarm guide.",
            "equipment_status",
        ),
        (
            "Show defect distribution and search the optical alarm guide.",
            "defect_distribution",
        ),
    ],
)
def test_sync_combined_request_returns_current_exchange_evidence(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    question: str,
    manufacturing_kind: str,
) -> None:
    conversation = create_conversation(conversation_client)
    conversation_client.patch(
        f"/conversations/{conversation['id']}/context",
        json={"device": "AOI-WAFER-01", "time_range": "Last 8 hours"},
    )

    class FakeAdapter:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def complete_with_tools(self, _messages, *, tools, tool_call=None):
            assert tools[0].name == "combined_evidence"
            payload = json.loads(tool_call.content)
            source_id = payload["documents"]["result"]["sources"][0]["source_id"]
            return CompletionResult(
                content=(
                    "Production and document evidence were retrieved. "
                    f"See {source_id}; any relationship still needs validation."
                )
            )

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FakeAdapter()),
    )
    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"content": question},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["assistant_message"]["suggested_actions"] == []
    assert payload["combined_evidence"]["manufacturing_kind"] == manufacturing_kind
    assert payload["combined_evidence"]["manufacturing"]["status"] == "succeeded"
    assert payload["combined_evidence"]["documents"]["status"] == "succeeded"
    assert payload["combined_evidence"]["answer_status"] == "succeeded"
    history = conversation_client.get(
        f"/conversations/{conversation['id']}/messages"
    ).json()
    assert history[-1]["suggested_actions"] == []


def test_sync_combined_model_failure_keeps_current_exchange_evidence(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)
    conversation_client.patch(
        f"/conversations/{conversation['id']}/context",
        json={"device": "AOI-WAFER-01", "time_range": "Last 8 hours"},
    )

    class FailingAdapter:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def complete_with_tools(self, _messages, *, tools, tool_call=None):
            assert tools[0].name == "combined_evidence"
            assert tool_call is not None
            raise LLMConnectionError("private provider detail")

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FailingAdapter()),
    )
    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"content": "Show production yield and search the documents."},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["combined_evidence"]["answer_status"] == "fallback"
    assert payload["combined_evidence"]["manufacturing"]["status"] == "succeeded"
    assert payload["combined_evidence"]["documents"]["status"] == "succeeded"
    assert payload["assistant_message"]["content"] == (
        "Evidence was retrieved, but a combined interpretation could not be "
        "completed. Review the evidence below."
    )
    assert "private provider detail" not in response.text


def test_sync_combined_preserves_manufacturing_when_document_path_fails(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)
    conversation_client.patch(
        f"/conversations/{conversation['id']}/context",
        json={"device": "AOI-WAFER-01", "time_range": "Last 8 hours"},
    )
    original = workflow_module.execute_combined_evidence

    def execute_with_document_failure(**kwargs):
        def fail_documents(_request, *, service=None):
            del service
            raise CombinedToolUnavailable("scripted document failure")

        return original(**kwargs, document_search_tool=fail_documents)

    monkeypatch.setattr(
        workflow_module, "execute_combined_evidence", execute_with_document_failure
    )
    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"content": "Show production yield and search the optical alarm guide."},
    )

    assert response.status_code == 201
    combined = response.json()["combined_evidence"]
    assert combined["manufacturing"]["status"] == "succeeded"
    assert combined["documents"] == {
        "status": "failed",
        "result": None,
        "error_code": "TOOL_UNAVAILABLE",
    }


def test_sse_combined_preserves_documents_when_manufacturing_path_fails(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)
    conversation_client.patch(
        f"/conversations/{conversation['id']}/context",
        json={"device": "AOI-WAFER-01", "time_range": "Last 8 hours"},
    )
    original = runner_module.stream_combined_evidence

    def stream_with_manufacturing_failure(**kwargs):
        def fail_manufacturing(_request):
            raise CombinedToolUnavailable("scripted manufacturing failure")

        return original(**kwargs, production_tool=fail_manufacturing)

    monkeypatch.setattr(
        runner_module, "stream_combined_evidence", stream_with_manufacturing_failure
    )
    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages/stream",
        json={"content": "Show production yield and search the optical alarm guide."},
    )

    assert response.status_code == 200
    assert (
        '"path":"manufacturing","manufacturing_kind":"production","status":"failed"'
        in response.text
    )
    assert (
        '"path":"documents","manufacturing_kind":"production","status":"succeeded"'
        in response.text
    )
    assert response.text.count("event: message_completed") == 1


@pytest.mark.parametrize(
    ("case", "manufacturing_status", "document_status"),
    [
        ("manufacturing_failed", "failed", "succeeded"),
        ("documents_failed", "succeeded", "failed"),
        ("double_failure", "failed", "failed"),
        ("manufacturing_empty", "empty", "succeeded"),
        ("documents_empty", "succeeded", "empty"),
    ],
)
def test_combined_sync_and_sse_keep_failure_and_empty_status_parity(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    manufacturing_status: str,
    document_status: str,
) -> None:
    original_sync = workflow_module.execute_combined_evidence
    original_stream = runner_module.stream_combined_evidence

    def fail_manufacturing(_request):
        raise CombinedToolUnavailable("scripted manufacturing failure")

    def fail_documents(_request, *, service=None):
        del service
        raise CombinedToolUnavailable("scripted document failure")

    def empty_manufacturing(request):
        return ProductionSummaryResult(
            equipment_id=request.equipment_id,
            lot_id=request.lot_id,
            start=request.start,
            end=request.end,
            inspected_wafers=0,
            passed_wafers=0,
            failed_wafers=0,
            yield_rate=None,
            defect_counts=(),
            alarm_events=(),
            limitations=("no_inspection_records",),
        )

    def empty_documents(request, *, service=None):
        del service
        return DocumentSearchResult(
            query=request.query,
            sources=(),
            limitations=("no_relevant_sources",),
        )

    injected: dict[str, object] = {}
    if case in {"manufacturing_failed", "double_failure"}:
        injected["production_tool"] = fail_manufacturing
    elif case == "manufacturing_empty":
        injected["production_tool"] = empty_manufacturing
    if case in {"documents_failed", "double_failure"}:
        injected["document_search_tool"] = fail_documents
    elif case == "documents_empty":
        injected["document_search_tool"] = empty_documents

    monkeypatch.setattr(
        workflow_module,
        "execute_combined_evidence",
        lambda **kwargs: original_sync(**kwargs, **injected),
    )
    monkeypatch.setattr(
        runner_module,
        "stream_combined_evidence",
        lambda **kwargs: original_stream(**kwargs, **injected),
    )

    def create_scoped_conversation() -> dict[str, object]:
        conversation = create_conversation(conversation_client)
        conversation_client.patch(
            f"/conversations/{conversation['id']}/context",
            json={"device": "AOI-WAFER-01", "time_range": "Last 8 hours"},
        )
        return conversation

    sync_conversation = create_scoped_conversation()
    sync_response = conversation_client.post(
        f"/conversations/{sync_conversation['id']}/messages",
        json={"content": "Show production yield and search the optical alarm guide."},
    )
    stream_conversation = create_scoped_conversation()
    stream_response = conversation_client.post(
        f"/conversations/{stream_conversation['id']}/messages/stream",
        json={"content": "Show production yield and search the optical alarm guide."},
    )

    assert sync_response.status_code == 201
    sync_combined = sync_response.json()["combined_evidence"]
    assert sync_combined["manufacturing"]["status"] == manufacturing_status
    assert sync_combined["documents"]["status"] == document_status
    stream_events = []
    for block in stream_response.text.strip().split("\n\n"):
        lines = block.splitlines()
        if len(lines) >= 2:
            stream_events.append(
                (
                    lines[0].removeprefix("event: "),
                    json.loads(lines[1].removeprefix("data: ")),
                )
            )
    path_events = {
        payload["path"]: payload
        for event, payload in stream_events
        if event == "combined_tool_result"
    }
    for path in ("manufacturing", "documents"):
        assert path_events[path]["result"] == sync_combined[path]["result"]
        assert path_events[path]["error_code"] == sync_combined[path]["error_code"]
    expected_manufacturing = (
        '"path":"manufacturing","manufacturing_kind":"production",'
        f'"status":"{manufacturing_status}"'
    )
    expected_documents = (
        '"path":"documents","manufacturing_kind":"production",'
        f'"status":"{document_status}"'
    )
    assert expected_manufacturing in stream_response.text
    assert expected_documents in stream_response.text
    assert stream_response.text.count("event: message_completed") == 1
    completed = next(
        payload for event, payload in stream_events if event == "message_completed"
    )
    sync_text = sync_response.json()["assistant_message"]["content"]
    assert completed["assistant_message"]["content"] == sync_text
    stream_history = conversation_client.get(
        f"/conversations/{stream_conversation['id']}/messages"
    ).json()
    assert stream_history[-1]["content"] == sync_text


def test_sse_combined_cancellation_after_manufacturing_does_not_persist_completion(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)
    conversation_client.patch(
        f"/conversations/{conversation['id']}/context",
        json={"device": "AOI-WAFER-01", "time_range": "Last 8 hours"},
    )
    checks = 0

    async def disconnect_after_manufacturing(_request: Request) -> bool:
        nonlocal checks
        checks += 1
        return checks == 2

    monkeypatch.setattr(Request, "is_disconnected", disconnect_after_manufacturing)
    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages/stream",
        json={"content": "Show production yield and search the optical alarm guide."},
    )

    assert response.status_code == 200
    assert '"path":"manufacturing"' in response.text
    assert '"path":"documents"' not in response.text
    assert "event: message_completed" not in response.text
    history = conversation_client.get(
        f"/conversations/{conversation['id']}/messages"
    ).json()
    assert [message["role"] for message in history] == ["user"]


def test_sse_client_disconnect_does_not_persist_partial_assistant_message(
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = sessionmaker(bind=database_engine)
    application = create_app()

    def override_db_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    application.dependency_overrides[get_db_session] = override_db_session
    provider_started = threading.Event()
    release_provider = threading.Event()

    class PausedAdapter:
        def __enter__(self) -> "PausedAdapter":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def stream(self, _messages: object):
            provider_started.set()
            assert release_provider.wait(timeout=5)
            yield "partial answer"

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: PausedAdapter()),
    )

    listening_socket = socket.socket()
    listening_socket.bind(("127.0.0.1", 0))
    listening_socket.listen()
    port = listening_socket.getsockname()[1]
    server = Server(Config(application, log_level="error", lifespan="off"))
    server_thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [listening_socket]},
        daemon=True,
    )
    server_thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started

    base_url = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(base_url=base_url, timeout=5) as client:
            conversation = client.post(
                "/conversations", json={"title": "Disconnect"}
            ).json()
            with client.stream(
                "POST",
                f"/conversations/{conversation['id']}/messages/stream",
                json={"content": "Question"},
            ):
                assert provider_started.wait(timeout=5)

            release_provider.set()
            time.sleep(0.1)
            history = client.get(
                f"/conversations/{conversation['id']}/messages"
            ).json()
        assert [message["role"] for message in history] == ["user"]
    finally:
        release_provider.set()
        server.should_exit = True
        server_thread.join(timeout=5)
        listening_socket.close()
        application.dependency_overrides.clear()


def test_stream_production_tool_error_persists_safe_response(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)

    class FakeAdapter:
        def __enter__(self) -> "FakeAdapter":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def complete_with_tools(self, messages, *, tools, tool_call=None):
            from industrial_agent.llm.types import CompletionResult, ToolCall

            return CompletionResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        call_id="call-001",
                        name="get_production_summary",
                        arguments={
                            "equipment_id": "UNKNOWN-DEVICE",
                            "start": "2026-01-15T13:00:00Z",
                            "end": "2026-01-15T17:00:00Z",
                        },
                    ),
                ),
            )

        def stream_with_tool_result(self, messages, *, tools, tool_call):
            raise AssertionError("Tool errors must not call the provider stream")

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FakeAdapter()),
    )
    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages/stream",
        json={"content": ("What is the production yield for AOI-WAFER-99 today?")},
    )

    assert response.status_code == 200
    assert (
        'data: {"text":"No sufficient production evidence was found."}' in response.text
    )
    history = conversation_client.get(
        f"/conversations/{conversation['id']}/messages"
    ).json()
    assert history[-1]["content"] == ("No sufficient production evidence was found.")


def test_created_message_persists_across_requests(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = create_conversation(conversation_client)

    class FakeAdapter:
        def __enter__(self) -> "FakeAdapter":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def complete(self, _: object) -> str:
            return "Persistent answer"

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(lambda cls, settings: FakeAdapter()),
    )

    created = conversation_client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"content": "Persistent message"},
    ).json()

    response = conversation_client.get(f"/conversations/{conversation['id']}/messages")

    assert created["user_message"]["id"] in {item["id"] for item in response.json()}
    assert created["assistant_message"]["id"] in {
        item["id"] for item in response.json()
    }


@pytest.mark.parametrize(
    "error",
    [
        LLMConfigurationError("missing model"),
        LLMConnectionError("unavailable"),
        LLMServiceError(502),
        LLMResponseError("invalid response"),
    ],
)
def test_create_message_keeps_user_message_when_llm_fails(
    conversation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    conversation = create_conversation(conversation_client)

    def raise_llm_error(cls: type[object], settings: object) -> object:
        raise error

    monkeypatch.setattr(
        OpenAICompatibleChatAdapter,
        "from_settings",
        classmethod(raise_llm_error),
    )

    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"content": "Keep this question"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Assistant response is temporarily unavailable"
    }
    history = conversation_client.get(f"/conversations/{conversation['id']}/messages")
    assert [(item["role"], item["content"]) for item in history.json()] == [
        ("user", "Keep this question")
    ]


@pytest.mark.parametrize("content", ["", "   ", "x" * 10_001])
def test_create_message_rejects_invalid_content(
    conversation_client: TestClient,
    content: str,
) -> None:
    conversation = create_conversation(conversation_client)

    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"content": content},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "extra_field",
    [{"role": "assistant"}, {"unexpected": "value"}],
)
def test_create_message_rejects_extra_fields(
    conversation_client: TestClient,
    extra_field: dict[str, str],
) -> None:
    conversation = create_conversation(conversation_client)

    response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"content": "Hello", **extra_field},
    )

    assert response.status_code == 422


def test_create_message_returns_404_for_unknown_conversation(
    conversation_client: TestClient,
) -> None:
    response = conversation_client.post(
        f"/conversations/{UNKNOWN_CONVERSATION_ID}/messages",
        json={"content": "Orphan"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found"}


def test_create_message_returns_422_for_malformed_conversation_id(
    conversation_client: TestClient,
) -> None:
    response = conversation_client.post(
        "/conversations/not-a-uuid/messages",
        json={"content": "Invalid parent"},
    )

    assert response.status_code == 422


def test_list_messages_returns_empty_history(
    conversation_client: TestClient,
) -> None:
    conversation = create_conversation(conversation_client)

    response = conversation_client.get(f"/conversations/{conversation['id']}/messages")

    assert response.status_code == 200
    assert response.json() == []


def test_list_messages_returns_oldest_first(
    conversation_client: TestClient,
    successful_adapter: None,
) -> None:
    conversation = create_conversation(conversation_client)
    path = f"/conversations/{conversation['id']}/messages"
    first = conversation_client.post(
        path,
        json={"content": "First"},
    ).json()
    second = conversation_client.post(
        path,
        json={"content": "Second"},
    ).json()

    response = conversation_client.get(path)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        first["user_message"]["id"],
        first["assistant_message"]["id"],
        second["user_message"]["id"],
        second["assistant_message"]["id"],
    ]


def test_list_messages_is_scoped_to_one_conversation(
    conversation_client: TestClient,
    successful_adapter: None,
) -> None:
    first_conversation = create_conversation(
        conversation_client,
        "First conversation",
    )
    second_conversation = create_conversation(
        conversation_client,
        "Second conversation",
    )
    first_message = conversation_client.post(
        f"/conversations/{first_conversation['id']}/messages",
        json={"content": "First only"},
    ).json()
    conversation_client.post(
        f"/conversations/{second_conversation['id']}/messages",
        json={"content": "Second only"},
    )

    response = conversation_client.get(
        f"/conversations/{first_conversation['id']}/messages"
    )

    assert [item["id"] for item in response.json()] == [
        first_message["user_message"]["id"],
        first_message["assistant_message"]["id"],
    ]


def test_list_messages_returns_404_for_unknown_conversation(
    conversation_client: TestClient,
) -> None:
    response = conversation_client.get(
        f"/conversations/{UNKNOWN_CONVERSATION_ID}/messages"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found"}


def test_list_messages_returns_422_for_malformed_conversation_id(
    conversation_client: TestClient,
) -> None:
    response = conversation_client.get("/conversations/not-a-uuid/messages")

    assert response.status_code == 422


def test_delete_conversation_removes_persisted_messages(
    conversation_client: TestClient,
    database_engine: Engine,
    successful_adapter: None,
) -> None:
    conversation = create_conversation(conversation_client)
    create_response = conversation_client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"content": "Delete with parent"},
    )
    assert create_response.status_code == 201

    response = conversation_client.delete(f"/conversations/{conversation['id']}")

    factory = sessionmaker(bind=database_engine)
    with factory() as session:
        remaining = session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == UUID(conversation["id"]))
        )

    assert response.status_code == 204
    assert remaining == 0
