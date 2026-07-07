from collections.abc import Sequence
from types import TracebackType

import httpx

from industrial_agent.config.settings import Settings
from industrial_agent.llm.errors import (
    LLMConfigurationError,
    LLMConnectionError,
    LLMResponseError,
    LLMServiceError,
)
from industrial_agent.llm.types import ChatMessage


class OpenAICompatibleChatAdapter:
    def __init__(
        self,
        *,
        model: str,
        client: httpx.Client,
        owns_client: bool = False,
    ) -> None:
        normalized_model = model.strip()
        if not normalized_model:
            raise LLMConfigurationError("LLM model is required")
        self._model = normalized_model
        self._client = client
        self._owns_client = owns_client

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> "OpenAICompatibleChatAdapter":
        if settings.llm_model is None:
            raise LLMConfigurationError("LLM_MODEL is required")
        headers = {"Content-Type": "application/json"}
        if settings.llm_api_key is not None:
            headers["Authorization"] = (
                "Bearer " + settings.llm_api_key.get_secret_value()
            )
        client = httpx.Client(
            base_url=settings.llm_base_url,
            headers=headers,
            timeout=settings.llm_timeout_seconds,
            transport=transport,
        )
        return cls(
            model=settings.llm_model,
            client=client,
            owns_client=True,
        )

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        if not messages:
            raise ValueError("At least one chat message is required")
        try:
            response = self._client.post(
                "chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": message.role,
                            "content": message.content,
                        }
                        for message in messages
                    ],
                    "stream": False,
                },
            )
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise LLMConnectionError("Unable to reach LLM service") from error
        if not response.is_success:
            raise LLMServiceError(response.status_code)
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise LLMResponseError(
                "LLM service returned an invalid response"
            ) from error
        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError(
                "LLM service returned empty assistant content"
            )
        return content.strip()

    @property
    def is_closed(self) -> bool:
        return self._client.is_closed

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "OpenAICompatibleChatAdapter":
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()
