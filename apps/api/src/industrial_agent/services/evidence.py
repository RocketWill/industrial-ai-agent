"""Deterministic evidence sufficiency and final-answer checks."""

import math
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from numbers import Real

from pydantic import BaseModel

from industrial_agent.domain.routing import ExtractedContext, RouteDecision, RouteIntent
from industrial_agent.graph.combined import (
    CombinedEvidenceOutcome,
    EvidencePathStatus,
)
from industrial_agent.graph.state import EvidenceState
from industrial_agent.tools.document_search import DocumentSearchResult

NUMBER_PATTERN = re.compile(r"(?<![\w-])-?\d+(?:\.\d+)?%?")
ANSWER_NUMBER_PATTERN = re.compile(
    r"(?<![\w-])-?\d+(?:\.\d+)?(?:%|\s+percent)?", re.IGNORECASE
)

SAFE_EVIDENCE_FAILURES = {
    RouteIntent.PRODUCTION_SUMMARY: "No sufficient production evidence was found.",
    RouteIntent.EQUIPMENT_STATUS: "No recorded equipment status was found.",
    RouteIntent.DEFECT_DISTRIBUTION: "No defect distribution evidence was found.",
    RouteIntent.DOCUMENT_SEARCH: "No relevant document source was found.",
}
SAFE_ANSWER_FAILURES = {
    RouteIntent.PRODUCTION_SUMMARY: (
        "Production evidence was found, but the generated answer could not be "
        "verified. Review the deterministic evidence below."
    ),
    RouteIntent.EQUIPMENT_STATUS: (
        "Equipment-status evidence was found, but the generated answer could "
        "not be verified. Review the deterministic evidence below."
    ),
    RouteIntent.DEFECT_DISTRIBUTION: (
        "Defect-distribution evidence was found, but the generated answer could "
        "not be verified. Review the deterministic evidence below."
    ),
    RouteIntent.DOCUMENT_SEARCH: (
        "Document evidence was found, but the generated answer could not be "
        "verified. Review the retrieved sources below."
    ),
}

CAUSAL_CLAIM_PATTERN = re.compile(
    r"\b(?:caused?|causing|responsible for|root cause|resulted in)\b|"
    r"(?:造成|導致|根因)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    sufficient: bool
    response_text: str | None = None


def validate_evidence(
    route: RouteDecision,
    evidence: EvidenceState,
) -> EvidenceDecision:
    """Approve only route-matching, non-empty, context-aligned evidence."""
    expected_field = {
        RouteIntent.PRODUCTION_SUMMARY: "production_summary",
        RouteIntent.EQUIPMENT_STATUS: "equipment_status",
        RouteIntent.DEFECT_DISTRIBUTION: "defect_distribution",
        RouteIntent.DOCUMENT_SEARCH: "document_search",
    }.get(route.intent)
    if expected_field is None:
        return EvidenceDecision(sufficient=True)
    result = getattr(evidence, expected_field)
    if evidence.tool_error is not None or result is None:
        return _insufficient(route.intent)
    if not _context_matches(route.resolved_context, result):
        return _insufficient(route.intent)
    if not _contains_only_finite_numbers(result):
        return _insufficient(route.intent)
    if route.intent is RouteIntent.PRODUCTION_SUMMARY:
        if result.inspected_wafers == 0:
            return _insufficient(route.intent)
    elif route.intent is RouteIntent.EQUIPMENT_STATUS:
        if result.status == "unknown":
            return _insufficient(route.intent)
    elif route.intent is RouteIntent.DEFECT_DISTRIBUTION:
        if not result.items:
            return _insufficient(route.intent)
    elif route.intent is RouteIntent.DOCUMENT_SEARCH:
        if not result.sources or any(not source.source_id for source in result.sources):
            return _insufficient(route.intent)
    return EvidenceDecision(sufficient=True)


def validate_answer(
    route: RouteDecision,
    evidence: EvidenceState,
    answer: str,
) -> EvidenceDecision:
    """Reject ungrounded structured numbers or missing document citations."""
    approved = validate_evidence(route, evidence)
    if not approved.sufficient:
        return approved
    result = _result_for_route(route.intent, evidence)
    if result is None:
        return approved
    if route.intent is RouteIntent.DOCUMENT_SEARCH:
        source_ids = {source.source_id for source in result.sources}
        if not any(source_id in answer for source_id in source_ids):
            return _unverified(route.intent)
    evidence_numbers = _numeric_tokens(result.model_dump(mode="json"))
    answer_numbers = {
        token.casefold().replace(" percent", "%")
        for token in ANSWER_NUMBER_PATTERN.findall(answer)
    }
    if not answer_numbers <= evidence_numbers:
        return _unverified(route.intent)
    return EvidenceDecision(sufficient=True)


def validate_combined_answer(
    outcome: CombinedEvidenceOutcome,
    answer: str,
) -> bool:
    """Accept only cited, numerically grounded, non-causal combined prose."""
    if not answer.strip() or CAUSAL_CLAIM_PATTERN.search(answer):
        return False
    available_results = tuple(
        path.result
        for path in (outcome.manufacturing, outcome.documents)
        if path.status in {EvidencePathStatus.SUCCEEDED, EvidencePathStatus.EMPTY}
        and path.result is not None
    )
    if not available_results:
        return False
    evidence_numbers = set().union(
        *(
            _numeric_tokens(result.model_dump(mode="json"))
            for result in available_results
        )
    )
    answer_numbers = {
        token.casefold().replace(" percent", "%")
        for token in ANSWER_NUMBER_PATTERN.findall(answer)
    }
    if not answer_numbers <= evidence_numbers:
        return False
    document_result = outcome.documents.result
    if (
        outcome.documents.status is EvidencePathStatus.SUCCEEDED
        and isinstance(document_result, DocumentSearchResult)
    ):
        source_ids = {source.source_id for source in document_result.sources}
        if not any(source_id in answer for source_id in source_ids):
            return False
    return True


def _context_matches(context: ExtractedContext, result: BaseModel) -> bool:
    payload = result.model_dump()
    if context.equipment_id is not None and "equipment_id" in payload:
        if payload.get("equipment_id") != context.equipment_id:
            return False
    if context.lot_id is not None and "lot_id" in payload:
        if payload.get("lot_id") != context.lot_id:
            return False
    if context.start is not None and "start" in payload:
        if payload.get("start") != context.start or payload.get("end") != context.end:
            return False
    if context.document_query is not None and "query" in payload:
        if payload.get("query") != context.document_query:
            return False
    return True


def _contains_only_finite_numbers(value: BaseModel) -> bool:
    def visit(item: object) -> bool:
        if isinstance(item, float):
            return math.isfinite(item)
        if isinstance(item, dict):
            return all(visit(child) for child in item.values())
        if isinstance(item, (list, tuple)):
            return all(visit(child) for child in item)
        return True

    return visit(value.model_dump())


def _numeric_tokens(value: object) -> set[str]:
    if isinstance(value, bool):
        return set()
    if isinstance(value, Real):
        number = float(value)
        tokens = {str(value), f"{number:g}", f"{number:.2f}"}
        if 0 <= number <= 1:
            percentage = Decimal(str(number)) * 100
            percentage_one_decimal = percentage.quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
            tokens.update(
                {
                    f"{number * 100:g}",
                    str(percentage_one_decimal),
                    f"{number * 100:.2f}",
                    f"{number * 100:g}%",
                    f"{percentage_one_decimal}%",
                    f"{number * 100:.2f}%",
                }
            )
        return tokens
    if isinstance(value, datetime):
        return set()
    if isinstance(value, str):
        return set(NUMBER_PATTERN.findall(value))
    if isinstance(value, dict):
        return set().union(*(_numeric_tokens(item) for item in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(_numeric_tokens(item) for item in value))
    return set()


def _result_for_route(intent: RouteIntent, evidence: EvidenceState):
    return {
        RouteIntent.PRODUCTION_SUMMARY: evidence.production_summary,
        RouteIntent.EQUIPMENT_STATUS: evidence.equipment_status,
        RouteIntent.DEFECT_DISTRIBUTION: evidence.defect_distribution,
        RouteIntent.DOCUMENT_SEARCH: evidence.document_search,
    }.get(intent)


def _insufficient(intent: RouteIntent) -> EvidenceDecision:
    return EvidenceDecision(False, SAFE_EVIDENCE_FAILURES[intent])


def _unverified(intent: RouteIntent) -> EvidenceDecision:
    return EvidenceDecision(False, SAFE_ANSWER_FAILURES[intent])
