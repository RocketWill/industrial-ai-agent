def test_lists_deterministic_synthetic_devices(conversation_client) -> None:
    response = conversation_client.get("/devices")
    assert response.status_code == 200
    payload = response.json()
    assert [device["id"] for device in payload] == [
        "AOI-WAFER-01",
        "ETCH-CHAMBER-02",
        "LITHO-TRACK-01",
    ]
    assert all(device["data_source"] == "synthetic_demo" for device in payload)


def test_context_rejects_unknown_device(conversation_client) -> None:
    conversation = conversation_client.post(
        "/conversations", json={"title": "Device context"}
    ).json()
    response = conversation_client.patch(
        f"/conversations/{conversation['id']}/context",
        json={"device": "UNKNOWN-DEVICE"},
    )
    assert response.status_code == 422
