import pytest
from pydantic import ValidationError

from industrial_agent.config.settings import Settings

APP_ENVIRONMENT_VARIABLES = (
    "APP_NAME",
    "APP_ENV",
    "APP_HOST",
    "APP_PORT",
    "APP_DATABASE_URL",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_TIMEOUT_SECONDS",
    "LLM_ROUTER_MODEL",
    "LLM_ROUTER_TIMEOUT_SECONDS",
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
    assert settings.llm_base_url == "http://127.0.0.1:11434/v1"
    assert settings.llm_api_key is None
    assert settings.llm_model is None
    assert settings.llm_timeout_seconds == 60
    assert settings.llm_router_model is None
    assert settings.resolved_llm_router_model is None
    assert settings.llm_router_timeout_seconds == 10


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


def test_settings_read_llm_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_app_environment(monkeypatch)
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("LLM_API_KEY", "local-secret")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("LLM_ROUTER_MODEL", "router-model")
    monkeypatch.setenv("LLM_ROUTER_TIMEOUT_SECONDS", "8")

    settings = Settings()

    assert settings.llm_base_url == "https://llm.example/v1"
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "local-secret"
    assert settings.llm_model == "test-model"
    assert settings.llm_timeout_seconds == 12.5
    assert settings.llm_router_model == "router-model"
    assert settings.resolved_llm_router_model == "router-model"
    assert settings.llm_router_timeout_seconds == 8


def test_router_model_defaults_to_answer_model() -> None:
    settings = Settings(LLM_MODEL="answer-model", LLM_ROUTER_MODEL="   ")

    assert settings.llm_router_model is None
    assert settings.resolved_llm_router_model == "answer-model"


@pytest.mark.parametrize("timeout", ["0", "0.9", "30.1", "31"])
def test_settings_reject_router_timeout_outside_range(
    monkeypatch: pytest.MonkeyPatch,
    timeout: str,
) -> None:
    clear_app_environment(monkeypatch)
    monkeypatch.setenv("LLM_ROUTER_TIMEOUT_SECONDS", timeout)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_treat_blank_llm_api_key_as_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_app_environment(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "   ")

    assert Settings().llm_api_key is None


@pytest.mark.parametrize("timeout", ["0", "-1"])
def test_settings_reject_non_positive_llm_timeout(
    monkeypatch: pytest.MonkeyPatch,
    timeout: str,
) -> None:
    clear_app_environment(monkeypatch)
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", timeout)

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("port", ["0", "65536"])
def test_settings_reject_ports_outside_tcp_range(
    monkeypatch: pytest.MonkeyPatch,
    port: str,
) -> None:
    clear_app_environment(monkeypatch)
    monkeypatch.setenv("APP_PORT", port)

    with pytest.raises(ValidationError):
        Settings()
