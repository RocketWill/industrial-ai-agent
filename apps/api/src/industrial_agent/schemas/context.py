from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Environment = Literal["development", "synthetic"]
DataSource = Literal["synthetic_demo"]


class WorkspaceContextUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    environment: Environment | None = None
    device: str | None = Field(default=None, max_length=200)
    lot: str | None = Field(default=None, max_length=200)
    time_range: str | None = Field(default=None, max_length=100)
    data_source: DataSource | None = None


class WorkspaceContextRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    environment: Environment
    device: str | None
    lot: str | None
    time_range: str | None
    data_source: DataSource
