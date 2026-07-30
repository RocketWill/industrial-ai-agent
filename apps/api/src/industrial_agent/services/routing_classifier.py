"""Typed, bounded classifier transport for ambiguous routing requests."""

import json
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import ValidationError

from industrial_agent.domain.routing import ExtractedContext, RouteCandidate
from industrial_agent.llm.errors import (
    LLMConnectionError,
    LLMResponseError,
    LLMServiceError,
)
from industrial_agent.llm.openai_compatible import OpenAICompatibleChatAdapter
from industrial_agent.llm.types import ChatMessage, ToolDefinition

CLASSIFY_REQUEST_TOOL = ToolDefinition(
    name="classify_request",
    description=(
        "Classify one request using only the supported application routes and "
        "return structured exchange-local context."
    ),
    parameters=RouteCandidate.model_json_schema(),
)


class RoutingClassifierError(Exception):
    """Raised after bounded classifier attempts cannot produce a candidate."""


class RoutingClassificationCancelled(Exception):
    """Raised when caller cancellation prevents classification or retry."""


@dataclass(frozen=True, slots=True)
class PriorExchange:
    user: str
    assistant: str


@dataclass(frozen=True, slots=True)
class ClassifierInput:
    latest_question: str
    saved_context: ExtractedContext
    supported_equipment_ids: tuple[str, ...]
    capability_metadata: tuple[str, ...]
    prior_exchange: PriorExchange | None = None

    def __post_init__(self) -> None:
        if not self.latest_question.strip():
            raise ValueError("latest question must not be empty")


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    candidate: RouteCandidate
    retry_count: int


class RoutingClassifier:
    """Request exactly one validated candidate with at most one retry."""

    def __init__(self, adapter: OpenAICompatibleChatAdapter) -> None:
        self._adapter = adapter

    def classify(
        self,
        classifier_input: ClassifierInput,
        *,
        is_cancelled: Callable[[], bool] = lambda: False,
    ) -> RouteCandidate:
        return self.classify_result(
            classifier_input, is_cancelled=is_cancelled
        ).candidate

    def classify_result(
        self,
        classifier_input: ClassifierInput,
        *,
        is_cancelled: Callable[[], bool] = lambda: False,
    ) -> ClassificationResult:
        """Return the candidate and observable retry count."""
        last_error: Exception | None = None
        for attempt in range(2):
            _raise_if_cancelled(is_cancelled)
            try:
                result = self._adapter.complete_with_tools(
                    [_classifier_message(classifier_input)],
                    tools=(CLASSIFY_REQUEST_TOOL,),
                )
                if len(result.tool_calls) != 1:
                    raise LLMResponseError(
                        "Classifier must return exactly one tool call"
                    )
                call = result.tool_calls[0]
                if call.name != CLASSIFY_REQUEST_TOOL.name:
                    raise LLMResponseError("Classifier returned an unknown tool")
                candidate = RouteCandidate.model_validate(call.arguments)
                _raise_if_cancelled(is_cancelled)
                return ClassificationResult(
                    candidate=candidate, retry_count=attempt
                )
            except RoutingClassificationCancelled:
                raise
            except (LLMConnectionError, LLMResponseError, ValidationError) as error:
                last_error = error
            except LLMServiceError as error:
                if not _is_transient_status(error.status_code):
                    raise RoutingClassifierError(
                        "Classifier service rejected the request"
                    ) from error
                last_error = error
            _raise_if_cancelled(is_cancelled)
        raise RoutingClassifierError(
            "Classifier did not return a valid structured candidate"
        ) from last_error


def _classifier_message(value: ClassifierInput) -> ChatMessage:
    payload: dict[str, object] = {
        "latest_question": value.latest_question,
        "saved_context": value.saved_context.model_dump(mode="json"),
        "supported_equipment_ids": value.supported_equipment_ids,
        "capabilities": value.capability_metadata,
    }
    if value.prior_exchange is not None:
        payload["prior_exchange"] = {
            "user": value.prior_exchange.user,
            "assistant": value.prior_exchange.assistant,
        }
    return ChatMessage(
        role="user",
        content=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )


def _raise_if_cancelled(is_cancelled: Callable[[], bool]) -> None:
    if is_cancelled():
        raise RoutingClassificationCancelled("Routing classification cancelled")


def _is_transient_status(status_code: int) -> bool:
    return status_code in {408, 429} or status_code >= 500
