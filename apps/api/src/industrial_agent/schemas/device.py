from typing import Literal

from pydantic import BaseModel, ConfigDict

DeviceCategory = Literal["inspection", "etch", "lithography"]


class SyntheticDeviceRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    category: DeviceCategory
    data_source: Literal["synthetic_demo"] = "synthetic_demo"
