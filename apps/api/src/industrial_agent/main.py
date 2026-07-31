from fastapi import FastAPI

from industrial_agent.api.context import router as context_router
from industrial_agent.api.conversations import router as conversation_router
from industrial_agent.api.devices import router as device_router
from industrial_agent.api.health import router as health_router
from industrial_agent.api.messages import router as message_router
from industrial_agent.config.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()
    application = FastAPI(title=settings.app_name)
    application.include_router(health_router)
    application.include_router(conversation_router)
    application.include_router(context_router)
    application.include_router(device_router)
    application.include_router(message_router)
    return application


app = create_app()
