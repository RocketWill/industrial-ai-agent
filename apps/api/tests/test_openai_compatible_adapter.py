import json

import httpx
import pytest

from industrial_agent.config.settings import Settings
from industrial_agent.llm.errors import (
    LLMConfigurationError,
    LLMConnectionError,
    LLMResponseError,
    LLMServiceError,
)
from industrial_agent.llm.openai_compatible import (
    OpenAICompatibleChatAdapter,
)
from industrial_agent.llm.types import ChatMessage


def test_complete_sends_compatible_request_and_returns_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == (
            "http://llm.example/v1/chat/completions"
        )
        assert json.loads(request.content) == {
            "model": "test-model",
            "messages": [
                {"role": "user", "content": "Question"},
                {"role": "assistant", "content": "Earlier answer"},
            ],
            "stream": False,
        }
        assert request.headers["authorization"] == "Bearer local-secret"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "  Final answer  "}}
                ]
            },
        )

    settings = Settings(
        LLM_BASE_URL="http://llm.example/v1",
        LLM_API_KEY="local-secret",
        LLM_MODEL="test-model",
    )
    adapter = OpenAICompatibleChatAdapter.from_settings(
        settings,
        transport=httpx.MockTransport(handler),
    )

    with adapter:
        result = adapter.complete(
            [
                ChatMessage(role="user", content="Question"),
                ChatMessage(
                    role="assistant",
                    content="Earlier answer",
                ),
            ]
        )

    assert result == "Final answer"


def test_complete_omits_authorization_without_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Answer"}}]},
        )

    adapter = OpenAICompatibleChatAdapter.from_settings(
        Settings(LLM_MODEL="test-model"),
        transport=httpx.MockTransport(handler),
    )

    with adapter:
        assert adapter.complete(
            [ChatMessage(role="user", content="Question")]
        ) == "Answer"


def test_from_settings_rejects_missing_model() -> None:
    settings = Settings(LLM_MODEL=None)

    with pytest.raises(
        LLMConfigurationError,
        match="LLM_MODEL is required",
    ):
        OpenAICompatibleChatAdapter.from_settings(settings)


def test_close_keeps_caller_owned_client_open() -> None:
    client = httpx.Client(
        base_url="http://llm.example/v1",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200)
        ),
    )
    adapter = OpenAICompatibleChatAdapter(
        model="test-model",
        client=client,
    )

    adapter.close()

    assert not client.is_closed
    client.close()


def test_close_closes_factory_owned_client() -> None:
    adapter = OpenAICompatibleChatAdapter.from_settings(
        Settings(LLM_MODEL="test-model"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200)
        ),
    )

    adapter.close()

    assert adapter.is_closed


def test_context_manager_closes_factory_owned_client() -> None:
    with OpenAICompatibleChatAdapter.from_settings(
        Settings(LLM_MODEL="test-model"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200)
        ),
    ) as adapter:
        assert not adapter.is_closed

    assert adapter.is_closed


def test_complete_rejects_empty_message_sequence_without_request() -> None:
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200)

    adapter = OpenAICompatibleChatAdapter.from_settings(
        Settings(LLM_MODEL="test-model"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ValueError, match="At least one chat message"):
        adapter.complete([])

    assert requests == 0
    adapter.close()


@pytest.mark.parametrize(
    "error_type, message",
    [
        (httpx.ConnectError, "offline"),
        (httpx.ReadTimeout, "slow"),
    ],
)
def test_complete_maps_transport_errors(
    error_type: type[httpx.HTTPError],
    message: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error_type(message, request=request)

    adapter = OpenAICompatibleChatAdapter.from_settings(
        Settings(LLM_MODEL="test-model"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        LLMConnectionError,
        match="Unable to reach LLM service",
    ) as captured:
        adapter.complete([ChatMessage(role="user", content="Question")])

    assert isinstance(captured.value.__cause__, httpx.HTTPError)
    adapter.close()


@pytest.mark.parametrize("status_code", [400, 401, 404, 429, 500])
def test_complete_maps_non_success_responses(status_code: int) -> None:
    adapter = OpenAICompatibleChatAdapter.from_settings(
        Settings(LLM_MODEL="test-model"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                status_code,
                text="provider detail with sentinel-secret",
            )
        ),
    )

    with pytest.raises(LLMServiceError) as captured:
        adapter.complete([ChatMessage(role="user", content="Question")])

    assert captured.value.status_code == status_code
    assert "sentinel-secret" not in str(captured.value)
    adapter.close()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{}]}),
        httpx.Response(200, json={"choices": [{"message": {}}]}),
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": None}}]},
        ),
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": 123}}]},
        ),
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": "   "}}]},
        ),
    ],
)
def test_complete_rejects_invalid_response(
    response: httpx.Response,
) -> None:
    adapter = OpenAICompatibleChatAdapter.from_settings(
        Settings(LLM_MODEL="test-model"),
        transport=httpx.MockTransport(lambda _request: response),
    )

    with pytest.raises(LLMResponseError):
        adapter.complete([ChatMessage(role="user", content="Question")])

    adapter.close()
