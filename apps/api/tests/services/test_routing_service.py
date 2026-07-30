import json
import logging

import httpx
import pytest

from industrial_agent.config.settings import Settings
from industrial_agent.domain.routing import (
    DecisionSource,
    ExtractedContext,
    FallbackState,
    RouteIntent,
    TimePreset,
)
from industrial_agent.llm.openai_compatible import OpenAICompatibleChatAdapter
from industrial_agent.services.routing import (
    COMBINED_MESSAGE,
    UNSUPPORTED_MESSAGE,
    route_deterministically,
    route_exchange,
)
from industrial_agent.services.routing_classifier import (
    RoutingClassificationCancelled,
    RoutingClassifier,
)


def _classifier(responses: list[httpx.Response | Exception]):
    def handler(_request: httpx.Request) -> httpx.Response:
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    adapter = OpenAICompatibleChatAdapter.router_from_settings(
        Settings(LLM_MODEL="router"), transport=httpx.MockTransport(handler)
    )
    return adapter, RoutingClassifier(adapter)


def _candidate(arguments: dict[str, object]) -> httpx.Response:
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
                                    "name": "classify_request",
                                    "arguments": json.dumps(arguments),
                                },
                            }
                        ],
                    }
                }
            ]
        },
    )


def test_route_exchange_uses_gate_before_classifier() -> None:
    adapter, classifier = _classifier([])
    with adapter:
        outcome = route_exchange(
            latest_question="Hello, what can you do?", classifier=classifier
        )
    assert outcome.decision.intent is RouteIntent.GENERAL
    assert outcome.decision.decision_source is DecisionSource.DETERMINISTIC_GATE


def test_deterministic_route_does_not_require_classifier() -> None:
    outcome = route_deterministically(latest_question="你好，你可以做什麼？")

    assert outcome is not None
    assert outcome.decision.intent is RouteIntent.GENERAL


def test_deterministic_combined_route_returns_clarification_response() -> None:
    outcome = route_deterministically(
        latest_question="Show production yield and search the documents.",
        saved_context=ExtractedContext(
            equipment_id="AOI-WAFER-01", time_preset=TimePreset.LAST_8_HOURS
        ),
    )

    assert outcome is not None
    assert outcome.decision.intent is RouteIntent.CLARIFICATION
    assert outcome.response_text == COMBINED_MESSAGE


def test_route_exchange_resolves_classifier_context_and_missing_fields() -> None:
    response = _candidate(
        {
            "intent": "production_summary",
            "requested_evidence": {"production": True},
            "extracted_context": {},
            "reason_code": "production_request",
        }
    )
    adapter, classifier = _classifier([response])
    with adapter:
        outcome = route_exchange(
            latest_question="Please investigate the run.",
            classifier=classifier,
            saved_context=ExtractedContext(
                equipment_id="AOI-WAFER-01", time_preset=TimePreset.TODAY
            ),
        )
    assert outcome.decision.intent is RouteIntent.PRODUCTION_SUMMARY
    assert outcome.decision.resolved_context.equipment_id == "AOI-WAFER-01"


def test_route_exchange_converts_combined_candidate_to_clarification() -> None:
    response = _candidate(
        {
            "intent": "combined",
            "requested_evidence": {"production": True, "documents": True},
            "ambiguities": ["multiple_evidence_paths"],
            "reason_code": "combined_request",
        }
    )
    adapter, classifier = _classifier([response])
    with adapter:
        outcome = route_exchange(
            latest_question="Compare what happened with the procedure.",
            classifier=classifier,
        )
    assert outcome.decision.intent is RouteIntent.CLARIFICATION
    assert outcome.response_text == COMBINED_MESSAGE


def test_route_exchange_returns_deterministic_unsupported_message() -> None:
    adapter, classifier = _classifier([])
    with adapter:
        outcome = route_exchange(
            latest_question="Use our private live production records.",
            classifier=classifier,
        )
    assert outcome.decision.intent is RouteIntent.UNSUPPORTED
    assert outcome.response_text == UNSUPPORTED_MESSAGE


def test_route_exchange_uses_safe_general_fallback_after_retry_exhaustion() -> None:
    adapter, classifier = _classifier(
        [httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow")]
    )
    with adapter:
        outcome = route_exchange(
            latest_question="Please investigate the run.",
            classifier=classifier,
        )
    assert outcome.decision.intent is RouteIntent.GENERAL
    assert outcome.decision.decision_source is DecisionSource.FALLBACK
    assert outcome.decision.fallback_state is FallbackState.USED
    assert outcome.decision.retry_count == 1


def test_route_exchange_cancellation_bypasses_fallback() -> None:
    adapter, classifier = _classifier([])
    with adapter, pytest.raises(RoutingClassificationCancelled):
        route_exchange(
            latest_question="Please investigate the run.",
            classifier=classifier,
            is_cancelled=lambda: True,
        )


def test_route_exchange_logs_only_safe_routing_metadata(caplog) -> None:
    adapter, classifier = _classifier([])
    with caplog.at_level(logging.INFO), adapter:
        route_exchange(
            latest_question="Hello, secret prompt text",
            classifier=classifier,
            conversation_id="conversation-1",
            trace_id="trace-1",
        )
    record = next(
        record for record in caplog.records if record.msg == "routing_decided"
    )
    assert record.route == "general"
    assert record.conversation_id == "conversation-1"
    assert "secret prompt text" not in record.getMessage()
