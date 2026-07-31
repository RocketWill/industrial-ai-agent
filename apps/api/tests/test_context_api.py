def create_conversation(client) -> dict:
    response = client.post("/conversations", json={"title": "Context"})
    assert response.status_code == 201
    return response.json()


def test_context_defaults_and_partial_update(conversation_client) -> None:
    conversation = create_conversation(conversation_client)
    url = f"/conversations/{conversation['id']}/context"

    initial = conversation_client.get(url)
    assert initial.status_code == 200
    assert initial.json() == {
        "environment": "synthetic",
        "device": None,
        "lot": None,
        "time_range": None,
        "data_source": "synthetic_demo",
    }

    updated = conversation_client.patch(
        url,
        json={"device": "AOI-WAFER-01", "time_range": "Last 4 hours"},
    )
    assert updated.status_code == 200
    assert updated.json()["device"] == "AOI-WAFER-01"
    assert updated.json()["time_range"] == "Last 4 hours"


def test_context_rejects_unknown_fields(conversation_client) -> None:
    conversation = create_conversation(conversation_client)
    response = conversation_client.patch(
        f"/conversations/{conversation['id']}/context",
        json={"model": "not-supported"},
    )
    assert response.status_code == 422
