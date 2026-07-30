import pytest
from pydantic import ValidationError

from industrial_agent.config.settings import Settings

APP_ENVIRONMENT_VARIABLES = (
    "APP_NAME",
    "APP_ENV",
    "APP_HOST",
    "APP_PORT",
    "APP_DATABASE_URL",
)


def clear_app_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in APP_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def test_settings_use_safe_local_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_app_environment(monkeypatch)

    settings = Settings()

    assert settings.app_name == "Industrial AI Agent API"
    assert settings.env == "development"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.database_url == "sqlite:///./industrial_agent.db"


def test_settings_read_supported_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_app_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_HOST", "0.0.0.0")
    monkeypatch.setenv("APP_PORT", "9000")
    monkeypatch.setenv(
        "APP_DATABASE_URL",
        "sqlite:////tmp/industrial-agent-test.db",
    )

    settings = Settings()

    assert settings.env == "test"
    assert settings.host == "0.0.0.0"
    assert settings.port == 9000
    assert settings.database_url == "sqlite:////tmp/industrial-agent-test.db"


@pytest.mark.parametrize("port", ["0", "65536"])
def test_settings_reject_ports_outside_tcp_range(
    monkeypatch: pytest.MonkeyPatch,
    port: str,
) -> None:
    clear_app_environment(monkeypatch)
    monkeypatch.setenv("APP_PORT", port)

    with pytest.raises(ValidationError):
        Settings()
