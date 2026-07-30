from fastapi.testclient import TestClient

from industrial_agent.main import create_app


def test_health_returns_process_status() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["content-type"].startswith("application/json")


def test_application_uses_configured_name(
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_NAME", "Test Industrial Agent API")

    application = create_app()

    assert application.title == "Test Industrial Agent API"
