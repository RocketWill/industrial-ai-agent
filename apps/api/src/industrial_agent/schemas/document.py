from typing import Literal

from pydantic import BaseModel, ConfigDict

DocumentType = Literal["alarm_guide", "operator_sop", "maintenance_guide"]


class DocumentRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str
    title: str
    document_type: DocumentType
    relative_path: str
    markdown: str
    synthetic_demo: Literal[True] = True
