"""Deterministic evidence sufficiency and final-answer checks."""

import math
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from numbers import Real

from pydantic import BaseModel

from industrial_agent.domain.routing import ExtractedContext, RouteDecision, RouteIntent
from industrial_agent.graph.combined import (
    CombinedEvidenceOutcome,
    EvidencePathStatus,
)
from industrial_agent.graph.state import EvidenceState
from industrial_agent.tools.defect_distribution import DefectDistributionResult
from industrial_agent.tools.document_search import DocumentSearchResult
from industrial_agent.tools.equipment_status import EquipmentStatusResult
from industrial_agent.tools.production import ProductionSummaryResult

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
UNSUPPORTED_OPERATIONAL_CLAIM_PATTERN = re.compile(
    r"\b(?:indicates?|shows?|means?)\s+(?:that\s+)?(?:there\s+is\s+)?"
    r"(?:no\s+)?(?:immediate\s+)?process failure\b|"
    r"\b(?:equipment|process|tool|system)\s+(?:is\s+)?"
    r"(?:healthy|normal|stable|safe to operate|safe to run)\b|"
    r"\b(?:return|resume)\s+(?:the\s+)?(?:equipment|process|tool|system)\s+"
    r"to service\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    sufficient: bool
    response_text: str | None = None


class CombinedAnswerRejection(StrEnum):
    """Internal reason why combined model prose was rejected."""

    EMPTY_ANSWER = "empty_answer"
    NO_EVIDENCE = "no_evidence"
    CAUSAL_CLAIM = "causal_claim"
    UNSUPPORTED_MANUFACTURING_VALUE = "unsupported_manufacturing_value"
    INVALID_DOCUMENT_REFERENCE = "invalid_document_reference"
    UNSUPPORTED_OPERATIONAL_CLAIM = "unsupported_operational_claim"
    UNVALIDATED_HYPOTHESIS = "unvalidated_hypothesis"


@dataclass(frozen=True, slots=True)
class CombinedAnswerValidation:
    """Internal combined-answer decision without retaining discarded prose."""

    accepted: bool
    reason: CombinedAnswerRejection | None = None

    def __bool__(self) -> bool:
        return self.accepted


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
) -> CombinedAnswerValidation:
    """Accept only traceable, domain-grounded, non-causal combined prose."""
    if not answer.strip():
        return CombinedAnswerValidation(False, CombinedAnswerRejection.EMPTY_ANSWER)
    if _has_causal_claim(answer):
        return CombinedAnswerValidation(False, CombinedAnswerRejection.CAUSAL_CLAIM)
    if _has_unsupported_operational_claim(answer):
        return CombinedAnswerValidation(
            False, CombinedAnswerRejection.UNSUPPORTED_OPERATIONAL_CLAIM
        )
    if _has_unvalidated_hypothesis(answer):
        return CombinedAnswerValidation(
            False, CombinedAnswerRejection.UNVALIDATED_HYPOTHESIS
        )
    available_results = tuple(
        path.result
        for path in (outcome.manufacturing, outcome.documents)
        if path.status in {EvidencePathStatus.SUCCEEDED, EvidencePathStatus.EMPTY}
        and path.result is not None
    )
    if not available_results:
        return CombinedAnswerValidation(False, CombinedAnswerRejection.NO_EVIDENCE)
    manufacturing_result = outcome.manufacturing.result
    if isinstance(manufacturing_result, ProductionSummaryResult):
        if not _production_claims_are_grounded(manufacturing_result, answer):
            return CombinedAnswerValidation(
                False, CombinedAnswerRejection.UNSUPPORTED_MANUFACTURING_VALUE
            )
    if isinstance(manufacturing_result, DefectDistributionResult):
        if not _defect_distribution_claims_are_grounded(manufacturing_result, answer):
            return CombinedAnswerValidation(
                False, CombinedAnswerRejection.UNSUPPORTED_MANUFACTURING_VALUE
            )
    if isinstance(manufacturing_result, EquipmentStatusResult):
        if not _equipment_status_claims_are_grounded(manufacturing_result, answer):
            return CombinedAnswerValidation(
                False, CombinedAnswerRejection.UNSUPPORTED_OPERATIONAL_CLAIM
            )
    document_result = outcome.documents.result
    source_ids = (
        {source.source_id for source in document_result.sources}
        if isinstance(document_result, DocumentSearchResult)
        else set()
    )
    inline_ids = set(SOURCE_ID_PATTERN.findall(answer))
    if inline_ids and not inline_ids <= source_ids:
        return CombinedAnswerValidation(
            False, CombinedAnswerRejection.INVALID_DOCUMENT_REFERENCE
        )
    return CombinedAnswerValidation(True)


SOURCE_ID_PATTERN = re.compile(r"\b[a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9-]*:\d{3}\b")


def _has_unsupported_operational_claim(answer: str) -> bool:
    for match in UNSUPPORTED_OPERATIONAL_CLAIM_PATTERN.finditer(answer):
        qualifier = answer[max(0, match.start() - 24) : match.start()].casefold()
        if not re.search(r"\b(?:may|might|could|possibly)\s+$", qualifier):
            return True
    return False


def _has_causal_claim(answer: str) -> bool:
    for match in CAUSAL_CLAIM_PATTERN.finditer(answer):
        context = answer[max(0, match.start() - 48) : match.start()].casefold()
        if re.search(
            r"(?:\b(?:do not|does not|did not|not to|cannot|prohibits?|without)\b|"
            r"(?:不要|不得|不可|並非|不是|無法))[^.。\n]{0,36}$",
            context,
        ):
            continue
        return True
    return False


def _has_unvalidated_hypothesis(answer: str) -> bool:
    uncertainty = re.compile(
        r"\b(?:may|might|could|possibly|hypothes(?:is|ize))\b|"
        r"(?:可能|或許|假設|推測)",
        re.IGNORECASE,
    )
    validation = re.compile(
        r"\b(?:requires?|needs?)\s+(?:further\s+)?(?:validation|confirmation)\b|"
        r"(?:需要|仍需|有待)(?:進一步)?(?:驗證|確認)",
        re.IGNORECASE,
    )
    return any(
        uncertainty.search(sentence) and not validation.search(sentence)
        for sentence in re.split(r"[.。\n]+", answer)
    )


def _production_claims_are_grounded(
    result: ProductionSummaryResult, answer: str
) -> bool:
    expected_counts = {
        "inspected": result.inspected_wafers,
        "passed": result.passed_wafers,
        "failed": result.failed_wafers,
    }
    for label, expected in expected_counts.items():
        patterns = (
            rf"\b(\d+)\s+(?:wafers?\s+)?(?:was\s+|were\s+)?{label}\b",
            rf"^\s*(?:[-*]\s*)?{label}\s*(?::|was|were|=)?\s*(\d+)\b",
        )
        if any(
            int(value) != expected
            for pattern in patterns
            for value in re.findall(pattern, answer, re.IGNORECASE | re.MULTILINE)
        ):
            return False

    total_patterns = (
        r"\b(?:recorded\s+)?total\s*(?::|was|were|is|=)?\s*(\d+)\b",
        r"檢測總數(?:為|是|：|:|=)?\s*(\d+)",
    )
    if any(
        int(value) != result.inspected_wafers
        for pattern in total_patterns
        for value in re.findall(pattern, answer, re.IGNORECASE)
    ):
        return False

    processed_patterns = (
        r"\b(?:line|equipment|tool|system)\s+(?:processed|produced)\s+(\d+)\s+"
        r"(?:wafers?|units?)\b",
        r"(?:產線|設備|機台|系統)(?:處理|生產)\s*(\d+)\s*(?:片|個|件)?",
        r"\bproduction\s+(?:reached|totaled)\s+(\d+)\s+(?:wafers?|units?)\b",
    )
    if any(
        int(value) != result.inspected_wafers
        for pattern in processed_patterns
        for value in re.findall(pattern, answer, re.IGNORECASE)
    ):
        return False

    for defect in result.defect_counts:
        escaped = re.escape(defect.category)
        patterns = (
            rf"\b(\d+)\s+{escaped}\b",
            rf"^\s*(?:[-*]\s*)?{escaped}\s*(?::|was|were|=)?\s*(\d+)\b",
        )
        if any(
            int(value) != defect.count
            for pattern in patterns
            for value in re.findall(pattern, answer, re.IGNORECASE | re.MULTILINE)
        ):
            return False

    expected_defects = {
        defect.category.casefold(): defect.count for defect in result.defect_counts
    }
    for count, category in re.findall(
        r"\b(\d+)\s+([a-z][a-z-]*)\s+defects?\b", answer, re.IGNORECASE
    ):
        if expected_defects.get(category.casefold()) != int(count):
            return False

    if result.yield_rate is not None:
        expected_yield = result.yield_rate * 100
        for sentence in re.findall(
            r"\b(?:yield(?:\s+rate)?|良率)(?:\d+\.\d+|[^.\n])*",
            answer,
            re.IGNORECASE,
        ):
            comparisons = tuple(
                re.finditer(
                    r"\b(above|over|greater than|below|under|less than)\s+"
                    r"(\d+(?:\.\d+)?)%",
                    sentence,
                    re.IGNORECASE,
                )
            )
            comparison_spans = tuple(match.span(2) for match in comparisons)
            for match in comparisons:
                operator = match.group(1).casefold()
                value = float(match.group(2))
                if operator in ("above", "over", "greater than"):
                    if not expected_yield > value:
                        return False
                elif not expected_yield < value:
                    return False
            for match in re.finditer(
                r"(\d+(?:\.\d+)?)(?:%|\s+percent)", sentence, re.IGNORECASE
            ):
                if any(
                    start <= match.start(1) < end for start, end in comparison_spans
                ):
                    continue
                if not math.isclose(
                    float(match.group(1)), expected_yield, abs_tol=0.005
                ):
                    return False
    return True


def _defect_distribution_claims_are_grounded(
    result: DefectDistributionResult, answer: str
) -> bool:
    expected_defects = {item.category.casefold(): item.count for item in result.items}
    category_patterns = (
        r"\b(\d+)\s+([a-z][a-z-]*)\s+defects?\b",
        r"\b([a-z][a-z-]*)\s*(?::|was|were|=)\s*(\d+)\b",
    )
    for index, pattern in enumerate(category_patterns):
        for first, second in re.findall(pattern, answer, re.IGNORECASE):
            count, category = (first, second) if index == 0 else (second, first)
            if category.casefold() in expected_defects:
                if expected_defects[category.casefold()] != int(count):
                    return False

    count_claims = {
        "failed wafers": result.failed_wafers,
        "classified defects": result.classified_defect_count,
        "unclassified failed wafers": result.unclassified_failed_wafers,
    }
    for label, expected in count_claims.items():
        for value in re.findall(
            rf"\b{re.escape(label)}\s*(?::|was|were|=)?\s*(\d+)\b",
            answer,
            re.IGNORECASE,
        ):
            if int(value) != expected:
                return False
    return True


def _equipment_status_claims_are_grounded(
    result: EquipmentStatusResult, answer: str
) -> bool:
    for value in re.findall(
        r"\b(?:equipment|tool|system)\s+status\s*(?::|was|is|=)\s*"
        r"([a-z][a-z_-]*)\b",
        answer,
        re.IGNORECASE,
    ):
        if value.casefold() != result.status.casefold():
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
