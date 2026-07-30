from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import sessionmaker

from industrial_agent.llm.errors import (
    LLMConfigurationError,
    LLMConnectionError,
    LLMResponseError,
    LLMServiceError,
)
from industrial_agent.llm.openai_compatible import (
    OpenAICompatibleChatAdapter,
)
from industrial_agent.models.message import Message

UNKNOWN_CONVERSATION_ID = "00000000-0000-0000-0000-000000000099"


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

    response = conversation_client.get(
        f"/conversations/{conversation['id']}/messages"
    )

    assert created["user_message"]["id"] in {
        item["id"] for item in response.json()
    }
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
    history = conversation_client.get(
        f"/conversations/{conversation['id']}/messages"
    )
    assert [
        (item["role"], item["content"])
        for item in history.json()
    ] == [("user", "Keep this question")]


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

    response = conversation_client.get(
        f"/conversations/{conversation['id']}/messages"
    )

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
    response = conversation_client.get(
        "/conversations/not-a-uuid/messages"
    )

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

    response = conversation_client.delete(
        f"/conversations/{conversation['id']}"
    )

    factory = sessionmaker(bind=database_engine)
    with factory() as session:
        remaining = session.scalar(
            select(func.count())
            .select_from(Message)
            .where(
                Message.conversation_id == UUID(conversation["id"])
            )
        )

    assert response.status_code == 204
    assert remaining == 0
