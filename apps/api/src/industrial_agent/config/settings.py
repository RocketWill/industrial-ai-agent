from typing import Literal

from pydantic import Field
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
