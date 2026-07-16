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
from industrial_agent.llm.types import ChatMessage, ToolDefinition, ToolResult


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


def test_complete_with_tools_sends_schema_and_parses_one_tool_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "get_production_summary",
                    "description": "Read production evidence",
                    "parameters": {
                        "type": "object",
                        "properties": {"equipment_id": {"type": "string"}},
                        "required": ["equipment_id"],
                        "additionalProperties": False,
                    },
                },
            }
        ]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-001",
                                    "type": "function",
                                    "function": {
                                        "name": "get_production_summary",
                                        "arguments": '{"equipment_id":"AOI-WAFER-01"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    adapter = OpenAICompatibleChatAdapter.from_settings(
        Settings(LLM_MODEL="test-model"),
        transport=httpx.MockTransport(handler),
    )

    with adapter:
        result = adapter.complete_with_tools(
            [ChatMessage(role="user", content="What is yield?")],
            tools=(
                ToolDefinition(
                    name="get_production_summary",
                    description="Read production evidence",
                    parameters={
                        "type": "object",
                        "properties": {"equipment_id": {"type": "string"}},
                        "required": ["equipment_id"],
                        "additionalProperties": False,
                    },
                ),
            ),
        )

    assert result.content is None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].call_id == "call-001"
    assert result.tool_calls[0].name == "get_production_summary"
    assert result.tool_calls[0].arguments == {"equipment_id": "AOI-WAFER-01"}


def test_complete_with_tools_rejects_multiple_tool_calls() -> None:
    adapter = OpenAICompatibleChatAdapter.from_settings(
        Settings(LLM_MODEL="test-model"),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call-001",
                                        "type": "function",
                                        "function": {
                                            "name": "first",
                                            "arguments": "{}",
                                        },
                                    },
                                    {
                                        "id": "call-002",
                                        "type": "function",
                                        "function": {
                                            "name": "second",
                                            "arguments": "{}",
                                        },
                                    },
                                ],
                            }
                        }
                    ]
                },
            )
        ),
    )

    with adapter, pytest.raises(LLMResponseError, match="one tool call"):
        adapter.complete_with_tools(
            [ChatMessage(role="user", content="Question")],
            tools=(),
        )


def test_complete_with_tools_sends_tool_result_for_final_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["messages"][-2:] == [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-001",
                        "type": "function",
                        "function": {
                            "name": "get_production_summary",
                            "arguments": '{"equipment_id":"AOI-WAFER-01"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call-001",
                "content": '{"yield_rate":0.9}',
            },
        ]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Yield is 90%."}}]},
        )

    adapter = OpenAICompatibleChatAdapter.from_settings(
        Settings(LLM_MODEL="test-model"),
        transport=httpx.MockTransport(handler),
    )

    with adapter:
        result = adapter.complete_with_tools(
            [ChatMessage(role="user", content="What is yield?")],
            tools=(
                ToolDefinition(
                    name="get_production_summary",
                    description="Read production evidence",
                    parameters={"type": "object"},
                ),
            ),
            tool_call=ToolResult(
                call_id="call-001",
                name="get_production_summary",
                arguments={"equipment_id": "AOI-WAFER-01"},
                content='{"yield_rate":0.9}',
            ),
        )

    assert result.content == "Yield is 90%."
    assert result.tool_calls == ()


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


def test_stream_yields_compatible_deltas() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200,
            text=(
                "data: {\"choices\":[{\"delta\":{\"content\":\"Hel\"}}]}\n\n"
                "data: {\"choices\":[{\"delta\":{\"content\":\"lo\"}}]}\n\n"
                "data: [DONE]\n\n"
            ),
        )

    adapter = OpenAICompatibleChatAdapter.from_settings(
        Settings(LLM_MODEL="test-model"),
        transport=httpx.MockTransport(handler),
    )

    with adapter:
        assert list(adapter.stream([ChatMessage(role="user", content="Q")])) == [
            "Hel",
            "lo",
        ]


def test_stream_rejects_incomplete_or_malformed_response() -> None:
    responses = [
        "data: {\"choices\":[]}\n\ndata: [DONE]\n\n",
        "data: {\"choices\":[{\"delta\":{}}]}\n\ndata: [DONE]\n\n",
    ]
    for body in responses:
        adapter = OpenAICompatibleChatAdapter.from_settings(
            Settings(LLM_MODEL="test-model"),
            transport=httpx.MockTransport(
                lambda _request, body=body: httpx.Response(200, text=body)
            ),
        )
        with adapter, pytest.raises(LLMResponseError):
            list(adapter.stream([ChatMessage(role="user", content="Q")]))
