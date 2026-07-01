from uuid import UUID

import pytest
from fastapi.testclient import TestClient


def test_create_conversation_with_explicit_title(
    conversation_client: TestClient,
) -> None:
    response = conversation_client.post(
        "/conversations",
        json={"title": "Yield investigation"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert UUID(payload["id"])
    assert payload["title"] == "Yield investigation"
    assert payload["created_at"].endswith("Z")


def test_create_conversation_uses_default_title(
    conversation_client: TestClient,
) -> None:
    response = conversation_client.post("/conversations", json={})

    assert response.status_code == 201
    assert response.json()["title"] == "New conversation"


def test_create_conversation_trims_title(
    conversation_client: TestClient,
) -> None:
    response = conversation_client.post(
        "/conversations",
        json={"title": "  Yield investigation  "},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Yield investigation"


@pytest.mark.parametrize("title", ["", "   ", "x" * 201])
def test_create_conversation_rejects_invalid_title(
    conversation_client: TestClient,
    title: str,
) -> None:
    response = conversation_client.post(
        "/conversations",
        json={"title": title},
    )

    assert response.status_code == 422


def test_list_conversations_returns_newest_first(
    conversation_client: TestClient,
) -> None:
    first = conversation_client.post(
        "/conversations",
        json={"title": "First"},
    ).json()
    second = conversation_client.post(
        "/conversations",
        json={"title": "Second"},
    ).json()

    response = conversation_client.get("/conversations")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        second["id"],
        first["id"],
    ]


def test_conversation_persists_across_requests(
    conversation_client: TestClient,
) -> None:
    created = conversation_client.post(
        "/conversations",
        json={"title": "Persistent"},
    ).json()

    response = conversation_client.get("/conversations")

    assert created["id"] in {
        conversation["id"] for conversation in response.json()
    }


def test_get_conversation_returns_one_item(
    conversation_client: TestClient,
) -> None:
    created = conversation_client.post(
        "/conversations",
        json={"title": "Yield investigation"},
    ).json()

    response = conversation_client.get(f"/conversations/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_conversation_returns_404_for_unknown_id(
    conversation_client: TestClient,
) -> None:
    response = conversation_client.get(
        "/conversations/00000000-0000-0000-0000-000000000099"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found"}


def test_get_conversation_returns_422_for_malformed_id(
    conversation_client: TestClient,
) -> None:
    response = conversation_client.get("/conversations/not-a-uuid")

    assert response.status_code == 422


def test_delete_conversation_returns_204_and_removes_item(
    conversation_client: TestClient,
) -> None:
    created = conversation_client.post(
        "/conversations",
        json={"title": "Temporary"},
    ).json()

    delete_response = conversation_client.delete(
        f"/conversations/{created['id']}"
    )
    get_response = conversation_client.get(
        f"/conversations/{created['id']}"
    )

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert get_response.status_code == 404


def test_delete_conversation_returns_404_for_unknown_id(
    conversation_client: TestClient,
) -> None:
    response = conversation_client.delete(
        "/conversations/00000000-0000-0000-0000-000000000099"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found"}


def test_delete_conversation_returns_422_for_malformed_id(
    conversation_client: TestClient,
) -> None:
    response = conversation_client.delete("/conversations/not-a-uuid")

    assert response.status_code == 422
