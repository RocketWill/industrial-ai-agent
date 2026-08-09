"""Application-owned routing policy shared by future execution paths."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from industrial_agent.domain.routing import (
    DecisionSource,
    EvidenceKind,
    ExtractedContext,
    FallbackState,
    MissingField,
    ReasonCode,
    RouteCandidate,
    RouteDecision,
    RouteIntent,
    SafeAction,
    deterministic_gate,
    resolve_exchange_context,
)
from industrial_agent.services.routing_classifier import (
    ClassifierInput,
    PriorExchange,
    RoutingClassificationCancelled,
    RoutingClassifier,
    RoutingClassifierError,
)

LOGGER = logging.getLogger(__name__)

CLARIFICATION_MESSAGES = {
    MissingField.EQUIPMENT_ID: (
        "Which fictional equipment should I use for this request?"
    ),
    MissingField.TIME_RANGE: "Which supported time range should I use?",
    MissingField.DOCUMENT_QUERY: "What should I search for in the documents?",
}
COMBINED_MESSAGE = (
    "This request needs both production and document evidence. "
    "Please choose which evidence path to run first."
)
UNSUPPORTED_MESSAGE = (
    "That request is outside this synthetic portfolio project's supported "
    "capabilities."
)


@dataclass(frozen=True, slots=True)
class RoutingOutcome:
    decision: RouteDecision
    response_text: str | None = None


def route_exchange(
    *,
    latest_question: str,
    classifier: RoutingClassifier,
    current_context: ExtractedContext | None = None,
    saved_context: ExtractedContext | None = None,
    supported_equipment_ids: tuple[str, ...] = (),
    capability_metadata: tuple[str, ...] = (),
    prior_exchange: PriorExchange | None = None,
    is_cancelled: Callable[[], bool] = lambda: False,
    conversation_id: str | None = None,
    trace_id: str | None = None,
) -> RoutingOutcome:
    """Return one authoritative route or deterministic user response."""
    current_context = current_context or ExtractedContext()
    saved_context = saved_context or ExtractedContext()
    deterministic = route_deterministically(
        latest_question=latest_question,
        current_context=current_context,
        saved_context=saved_context,
        conversation_id=conversation_id,
        trace_id=trace_id,
    )
    if deterministic is not None:
        return deterministic

    try:
        classified = classifier.classify_result(
            ClassifierInput(
                latest_question=latest_question,
                prior_exchange=prior_exchange,
                saved_context=saved_context,
                supported_equipment_ids=supported_equipment_ids,
                capability_metadata=capability_metadata,
            ),
            is_cancelled=is_cancelled,
        )
    except RoutingClassificationCancelled:
        raise
    except RoutingClassifierError:
        decision = RouteDecision(
            intent=RouteIntent.GENERAL,
            resolved_context=resolve_exchange_context(
                current_context, saved_context
            ),
            decision_source=DecisionSource.FALLBACK,
            reason_code=ReasonCode.AMBIGUOUS_REQUEST,
            retry_count=1,
            fallback_state=FallbackState.USED,
            safe_action=SafeAction.ANSWER_GENERAL,
        )
        _log_decision(decision, conversation_id, trace_id)
        return RoutingOutcome(decision=decision)

    decision = _resolve_candidate(
        classified.candidate,
        current_context=current_context,
        saved_context=saved_context,
        retry_count=classified.retry_count,
    )
    outcome = _outcome_for_decision(decision, classified.candidate)
    _log_decision(decision, conversation_id, trace_id)
    return outcome


def route_deterministically(
    *,
    latest_question: str,
    current_context: ExtractedContext | None = None,
    saved_context: ExtractedContext | None = None,
    conversation_id: str | None = None,
    trace_id: str | None = None,
) -> RoutingOutcome | None:
    """Return a high-confidence route without constructing a classifier."""
    decision = deterministic_gate(
        latest_question,
        current_context=current_context or ExtractedContext(),
        saved_context=saved_context or ExtractedContext(),
    )
    if decision is None:
        return None
    if decision.intent is RouteIntent.COMBINED:
        decision = RouteDecision(
            intent=RouteIntent.CLARIFICATION,
            resolved_context=decision.resolved_context,
            decision_source=decision.decision_source,
            reason_code=ReasonCode.CLARIFICATION_REQUIRED,
            retry_count=decision.retry_count,
            fallback_state=decision.fallback_state,
            safe_action=SafeAction.REQUEST_CLARIFICATION,
        )
        outcome = RoutingOutcome(decision, COMBINED_MESSAGE)
        _log_decision(outcome.decision, conversation_id, trace_id)
        return outcome
    outcome = _outcome_for_decision(decision)
    _log_decision(outcome.decision, conversation_id, trace_id)
    return outcome


def _resolve_candidate(
    candidate: RouteCandidate,
    *,
    current_context: ExtractedContext,
    saved_context: ExtractedContext,
    retry_count: int,
) -> RouteDecision:
    resolved = resolve_exchange_context(
        candidate.extracted_context,
        resolve_exchange_context(current_context, saved_context),
    )
    intent = candidate.intent
    missing = set(candidate.missing_fields)
    if candidate.requested_evidence.kinds & {
        EvidenceKind.PRODUCTION,
        EvidenceKind.EQUIPMENT_STATUS,
        EvidenceKind.DEFECT_DISTRIBUTION,
    }:
        if not resolved.equipment_id:
            missing.add(MissingField.EQUIPMENT_ID)
        if not (resolved.time_preset or resolved.start):
            missing.add(MissingField.TIME_RANGE)
    if EvidenceKind.DOCUMENTS in candidate.requested_evidence.kinds:
        if not resolved.document_query:
            missing.add(MissingField.DOCUMENT_QUERY)
    if missing or candidate.ambiguities or intent is RouteIntent.COMBINED:
        intent = RouteIntent.CLARIFICATION
    action = {
        RouteIntent.GENERAL: SafeAction.ANSWER_GENERAL,
        RouteIntent.PRODUCTION_SUMMARY: SafeAction.EXECUTE_PRODUCTION_SUMMARY,
        RouteIntent.EQUIPMENT_STATUS: SafeAction.EXECUTE_EQUIPMENT_STATUS,
        RouteIntent.DEFECT_DISTRIBUTION: (
            SafeAction.EXECUTE_DEFECT_DISTRIBUTION
        ),
        RouteIntent.DOCUMENT_SEARCH: SafeAction.EXECUTE_DOCUMENT_SEARCH,
        RouteIntent.CLARIFICATION: SafeAction.REQUEST_CLARIFICATION,
        RouteIntent.UNSUPPORTED: SafeAction.REPORT_UNSUPPORTED,
    }[intent]
    reason = (
        ReasonCode.CLARIFICATION_REQUIRED
        if intent is RouteIntent.CLARIFICATION
        else candidate.reason_code
    )
    return RouteDecision(
        intent=intent,
        resolved_context=resolved,
        decision_source=DecisionSource.CLASSIFIER,
        reason_code=reason,
        retry_count=retry_count,
        safe_action=action,
    )


def _outcome_for_decision(
    decision: RouteDecision,
    candidate: RouteCandidate | None = None,
) -> RoutingOutcome:
    if decision.intent is RouteIntent.UNSUPPORTED:
        return RoutingOutcome(decision, UNSUPPORTED_MESSAGE)
    if decision.intent is not RouteIntent.CLARIFICATION:
        return RoutingOutcome(decision)
    if candidate is not None and candidate.intent is RouteIntent.COMBINED:
        return RoutingOutcome(decision, COMBINED_MESSAGE)
    missing = candidate.missing_fields if candidate is not None else ()
    message = next(
        (CLARIFICATION_MESSAGES[field] for field in missing),
        "Please clarify which supported evidence you want to use.",
    )
    return RoutingOutcome(decision, message)


def _log_decision(
    decision: RouteDecision,
    conversation_id: str | None,
    trace_id: str | None,
) -> None:
    LOGGER.info(
        "routing_decided",
        extra={
            "route": decision.intent.value,
            "reason_code": decision.reason_code.value,
            "retry_count": decision.retry_count,
            "fallback_state": decision.fallback_state.value,
            "conversation_id": conversation_id,
            "trace_id": trace_id,
        },
    )
