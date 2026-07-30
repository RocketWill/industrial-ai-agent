from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        extra="ignore",
    )

    app_name: str = Field(
        default="Industrial AI Agent API",
        validation_alias="APP_NAME",
    )
    env: Literal["development", "test", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "sqlite:///./industrial_agent.db"
    llm_base_url: str = Field(
        default="http://127.0.0.1:11434/v1",
        validation_alias="LLM_BASE_URL",
    )
    llm_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="LLM_API_KEY",
    )
    llm_model: str | None = Field(
        default=None,
        validation_alias="LLM_MODEL",
    )
    llm_timeout_seconds: float = Field(
        default=60,
        gt=0,
        validation_alias="LLM_TIMEOUT_SECONDS",
    )
    llm_router_model: str | None = Field(
        default=None,
        validation_alias="LLM_ROUTER_MODEL",
    )
    llm_router_timeout_seconds: float = Field(
        default=10,
        ge=1,
        le=30,
        validation_alias="LLM_ROUTER_TIMEOUT_SECONDS",
    )

    @field_validator("llm_model", "llm_router_model", mode="after")
    @classmethod
    def normalize_llm_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @property
    def resolved_llm_router_model(self) -> str | None:
        """Use the answer model when no dedicated router model is configured."""
        return self.llm_router_model or self.llm_model

    @field_validator("llm_api_key", mode="after")
    @classmethod
    def normalize_llm_api_key(
        cls,
        value: SecretStr | None,
    ) -> SecretStr | None:
        if value is None or not value.get_secret_value().strip():
            return None
        return value
