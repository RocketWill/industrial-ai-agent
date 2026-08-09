from fastapi import APIRouter, HTTPException, status

from industrial_agent.domain.documents import (
    CorpusConstructionError,
    read_registry_document,
)
from industrial_agent.schemas.document import DocumentRead

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str) -> DocumentRead:
    try:
        document = read_registry_document(document_id)
    except CorpusConstructionError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document corpus unavailable",
        ) from error

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentRead(
        document_id=document.document_id,
        title=document.title,
        document_type=document.document_type,
        relative_path=document.relative_path,
        markdown=document.markdown,
    )
