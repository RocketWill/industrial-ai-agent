from typing import Literal

from pydantic import BaseModel, ConfigDict

DocumentType = Literal["alarm_guide", "operator_sop", "maintenance_guide"]
ManagedDocumentType = Literal[
    "alarm_guide",
    "operator_sop",
    "maintenance_guide",
    "uploaded_document",
]
DocumentSource = Literal["built_in", "local_upload"]
DocumentStatus = Literal["ready"]


class DocumentMetadataRead(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    document_id: str
    title: str
    document_type: ManagedDocumentType
    source: DocumentSource
    filename: str
    relative_path: str
    size_bytes: int
    status: DocumentStatus
    deletable: bool
    synthetic_demo: bool


class DocumentRead(DocumentMetadataRead):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    markdown: str
