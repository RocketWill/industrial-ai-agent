from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response

from industrial_agent.domain.documents import MAX_UPLOAD_BYTES, DocumentValidationError
from industrial_agent.schemas.document import DocumentMetadataRead, DocumentRead
from industrial_agent.services.documents import (
    BuiltInDocumentError,
    DocumentConflictError,
    DocumentCorpusService,
    DocumentNotFoundError,
    DocumentStoreError,
    StoredDocument,
)

router = APIRouter(prefix="/documents", tags=["documents"])
ALLOWED_MEDIA_TYPES = frozenset(
    {"application/octet-stream", "text/markdown", "text/plain"}
)


def _document_service(request: Request) -> DocumentCorpusService:
    return request.app.state.document_corpus_service


def _metadata_response(document: StoredDocument) -> DocumentMetadataRead:
    return DocumentMetadataRead.model_validate(document.metadata, from_attributes=True)


def _document_response(document: StoredDocument) -> DocumentRead:
    return DocumentRead.model_validate(
        {
            **_metadata_response(document).model_dump(),
            "markdown": document.markdown,
        }
    )


@router.get("", response_model=list[DocumentMetadataRead])
def list_documents(request: Request) -> list[DocumentMetadataRead] | JSONResponse:
    service = _document_service(request)
    try:
        documents = service.list_documents()
    except DocumentStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document corpus unavailable",
        ) from error
    if not service.status.available:
        built_ins = [
            DocumentMetadataRead.model_validate(
                document,
                from_attributes=True,
            ).model_dump(mode="json")
            for document in documents
            if document.source == "built_in"
        ]
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Local uploaded-document storage is unavailable",
                "documents": built_ins,
            },
        )
    return [
        DocumentMetadataRead.model_validate(document, from_attributes=True)
        for document in documents
    ]


@router.post(
    "",
    response_model=DocumentMetadataRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    request: Request,
    file: Annotated[UploadFile, File(...)],
) -> DocumentMetadataRead:
    form = await request.form()
    form_items = list(form.multi_items())
    if (
        len(form_items) != 1
        or form_items[0][0] != "file"
        or form_items[0][1] is not file
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Exactly one file field named 'file' is required",
        )

    filename = file.filename or ""
    if not filename.casefold().endswith(".md"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only Markdown (.md) files are supported",
        )
    content_type = (file.content_type or "").split(";", 1)[0].casefold()
    if content_type and content_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The upload media type is not supported",
        )

    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The Markdown document exceeds the 1 MiB limit",
        )

    try:
        document = _document_service(request).upload_document(
            filename=filename,
            content=content,
        )
    except DocumentConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A document with this identity or filename already exists",
        ) from error
    except DocumentValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except DocumentStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is temporarily unavailable",
        ) from error
    return _metadata_response(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, request: Request) -> Response:
    try:
        _document_service(request).delete_document(document_id)
    except BuiltInDocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Built-in documents cannot be deleted",
        ) from error
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        ) from error
    except DocumentStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is temporarily unavailable",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, request: Request) -> DocumentRead:
    service = _document_service(request)
    try:
        document = service.get_document(document_id)
    except DocumentStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document corpus unavailable",
        ) from error

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return _document_response(document)
