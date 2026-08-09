from fastapi import FastAPI

from industrial_agent.api.context import router as context_router
from industrial_agent.api.conversations import router as conversation_router
from industrial_agent.api.devices import router as device_router
from industrial_agent.api.documents import router as document_router
from industrial_agent.api.health import router as health_router
from industrial_agent.api.messages import router as message_router
from industrial_agent.config.settings import Settings
from industrial_agent.services.documents import (
    DocumentCorpusService,
    get_document_corpus_service,
)


def create_app(
    *, document_corpus_service: DocumentCorpusService | None = None
) -> FastAPI:
    settings = Settings()
    application = FastAPI(title=settings.app_name)
    application.state.document_corpus_service = (
        document_corpus_service or get_document_corpus_service()
    )
    application.include_router(health_router)
    application.include_router(conversation_router)
    application.include_router(context_router)
    application.include_router(device_router)
    application.include_router(document_router)
    application.include_router(message_router)
    return application


app = create_app()
