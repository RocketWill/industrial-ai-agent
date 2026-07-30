import json

import httpx
import pytest

from industrial_agent.config.settings import Settings
from industrial_agent.domain.routing import (
    ExtractedContext,
    ReasonCode,
    RouteIntent,
)
from industrial_agent.llm.openai_compatible import OpenAICompatibleChatAdapter
from industrial_agent.services.routing_classifier import (
    CLASSIFY_REQUEST_TOOL,
    ClassifierInput,
    PriorExchange,
    RoutingClassificationCancelled,
    RoutingClassifier,
    RoutingClassifierError,
)


def _tool_response(arguments: dict[str, object], *, name: str = "classify_request"):
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "route-1",
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(arguments),
                                },
                            }
                        ],
                    }
                }
            ]
        },
    )


def _input() -> ClassifierInput:
    return ClassifierInput(
        latest_question="What happened?",
        prior_exchange=PriorExchange(user="Earlier", assistant="Answer"),
        saved_context=ExtractedContext(equipment_id="AOI-WAFER-01"),
        supported_equipment_ids=("AOI-WAFER-01",),
        capability_metadata=("synthetic production summary",),
    )


def test_classifier_sends_exact_tool_and_approved_input_boundary() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["tools"] == [CLASSIFY_REQUEST_TOOL.as_payload()]
        assert payload["model"] == "router-model"
        content = json.loads(payload["messages"][0]["content"])
        assert set(content) == {
            "latest_question",
            "prior_exchange",
            "saved_context",
            "supported_equipment_ids",
            "capabilities",
        }
        assert "password" not in payload["messages"][0]["content"]
        return _tool_response(
            {
                "intent": "general",
                "reason_code": "general_request",
            }
        )

    adapter = OpenAICompatibleChatAdapter.router_from_settings(
        Settings(LLM_MODEL="answer-model", LLM_ROUTER_MODEL="router-model"),
        transport=httpx.MockTransport(handler),
    )
    with adapter:
        candidate = RoutingClassifier(adapter).classify(_input())

    assert candidate.intent is RouteIntent.GENERAL
    assert candidate.reason_code is ReasonCode.GENERAL_REQUEST


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"choices": [{"message": {"content": "text"}}]}),
        _tool_response({}, name="unknown_tool"),
        _tool_response({"intent": "not-a-route", "reason_code": "bad"}),
    ],
)
def test_classifier_retries_invalid_structured_output_once(
    response: httpx.Response,
) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response

    adapter = OpenAICompatibleChatAdapter.router_from_settings(
        Settings(LLM_MODEL="model"), transport=httpx.MockTransport(handler)
    )
    with adapter, pytest.raises(RoutingClassifierError):
        RoutingClassifier(adapter).classify(_input())

    assert calls == 2


def test_classifier_retries_transient_failure_then_returns_candidate() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("slow")
        return _tool_response(
            {"intent": "general", "reason_code": "general_request"}
        )

    adapter = OpenAICompatibleChatAdapter.router_from_settings(
        Settings(LLM_MODEL="model"), transport=httpx.MockTransport(handler)
    )
    with adapter:
        result = RoutingClassifier(adapter).classify(_input())

    assert result.intent is RouteIntent.GENERAL
    assert calls == 2


def test_classifier_cancellation_bypasses_attempt_and_retry() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _tool_response(
            {"intent": "general", "reason_code": "general_request"}
        )

    adapter = OpenAICompatibleChatAdapter.router_from_settings(
        Settings(LLM_MODEL="model"), transport=httpx.MockTransport(handler)
    )
    with adapter, pytest.raises(RoutingClassificationCancelled):
        RoutingClassifier(adapter).classify(_input(), is_cancelled=lambda: True)

    assert calls == 0
