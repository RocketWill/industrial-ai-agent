"""Immutable routing contracts and the explicit bilingual routing gate."""

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RouteIntent(StrEnum):
    GENERAL = "general"
    PRODUCTION_SUMMARY = "production_summary"
    EQUIPMENT_STATUS = "equipment_status"
    DEFECT_DISTRIBUTION = "defect_distribution"
    DOCUMENT_SEARCH = "document_search"
    COMBINED = "combined"
    CLARIFICATION = "clarification"
    UNSUPPORTED = "unsupported"


class EvidenceKind(StrEnum):
    PRODUCTION = "production"
    EQUIPMENT_STATUS = "equipment_status"
    DEFECT_DISTRIBUTION = "defect_distribution"
    DOCUMENTS = "documents"


class TimePreset(StrEnum):
    TODAY = "today"
    LAST_1_HOUR = "last_1_hour"
    LAST_4_HOURS = "last_4_hours"
    LAST_8_HOURS = "last_8_hours"
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"


class DecisionSource(StrEnum):
    DETERMINISTIC_GATE = "deterministic_gate"
    CLASSIFIER = "classifier"
    FALLBACK = "fallback"


class FallbackState(StrEnum):
    NOT_USED = "not_used"
    USED = "used"


class SafeAction(StrEnum):
    ANSWER_GENERAL = "answer_general"
    EXECUTE_PRODUCTION_SUMMARY = "execute_production_summary"
    EXECUTE_EQUIPMENT_STATUS = "execute_equipment_status"
    EXECUTE_DEFECT_DISTRIBUTION = "execute_defect_distribution"
    EXECUTE_DOCUMENT_SEARCH = "execute_document_search"
    REQUEST_CLARIFICATION = "request_clarification"
    REPORT_UNSUPPORTED = "report_unsupported"


class MissingField(StrEnum):
    EQUIPMENT_ID = "equipment_id"
    TIME_RANGE = "time_range"
    DOCUMENT_QUERY = "document_query"


class AmbiguityCode(StrEnum):
    MULTIPLE_EVIDENCE_PATHS = "multiple_evidence_paths"
    UNSPECIFIC_EVIDENCE_REQUEST = "unspecific_evidence_request"


class ReasonCode(StrEnum):
    GENERAL_REQUEST = "general_request"
    PRODUCTION_REQUEST = "production_request"
    EQUIPMENT_STATUS_REQUEST = "equipment_status_request"
    DEFECT_DISTRIBUTION_REQUEST = "defect_distribution_request"
    DOCUMENT_REQUEST = "document_request"
    COMBINED_REQUEST = "combined_request"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    AMBIGUOUS_REQUEST = "ambiguous_request"


class RequestedEvidence(BaseModel):
    """Evidence kinds proposed by the classifier without execution authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    production: bool = False
    equipment_status: bool = False
    defect_distribution: bool = False
    documents: bool = False

    @property
    def kinds(self) -> frozenset[EvidenceKind]:
        return frozenset(
            kind for kind in EvidenceKind if getattr(self, kind.value)
        )

    @property
    def count(self) -> int:
        return len(self.kinds)


class ExtractedContext(BaseModel):
    """Exchange-local context; construction never mutates saved context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    equipment_id: str | None = Field(default=None, min_length=1)
    lot_id: str | None = Field(default=None, min_length=1)
    start: datetime | None = None
    end: datetime | None = None
    time_preset: TimePreset | None = None
    document_query: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if (self.start is None) != (self.end is None):
            raise ValueError("both start and end must be provided")
        if self.start is not None:
            if self.start.utcoffset() != UTC.utcoffset(self.start):
                raise ValueError("timestamps must use UTC")
            if self.start >= self.end:
                raise ValueError("end must be after start")
        if self.time_preset is not None and self.start is not None:
            raise ValueError("use either an explicit range or a time preset")
        return self


class RouteCandidate(BaseModel):
    """Validated classifier proposal; the application still owns the route."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intent: RouteIntent
    requested_evidence: RequestedEvidence = RequestedEvidence()
    extracted_context: ExtractedContext = ExtractedContext()
    missing_fields: tuple[MissingField, ...] = ()
    ambiguities: tuple[AmbiguityCode, ...] = ()
    reason_code: ReasonCode

    @model_validator(mode="after")
    def validate_route(self) -> Self:
        evidence = self.requested_evidence.count
        required_evidence = {
            RouteIntent.PRODUCTION_SUMMARY: EvidenceKind.PRODUCTION,
            RouteIntent.EQUIPMENT_STATUS: EvidenceKind.EQUIPMENT_STATUS,
            RouteIntent.DEFECT_DISTRIBUTION: EvidenceKind.DEFECT_DISTRIBUTION,
            RouteIntent.DOCUMENT_SEARCH: EvidenceKind.DOCUMENTS,
        }
        required = required_evidence.get(self.intent)
        if required is not None and self.requested_evidence.kinds != {required}:
            raise ValueError(f"{required.value} evidence is required for route")
        if self.intent is RouteIntent.COMBINED and evidence < 2:
            raise ValueError("combined route requires at least two evidence kinds")
        if self.intent is RouteIntent.UNSUPPORTED and evidence:
            raise ValueError("unsupported route cannot request production evidence")
        if self.intent is RouteIntent.CLARIFICATION and not (
            self.missing_fields or self.ambiguities
        ):
            raise ValueError("clarification requires a missing field or ambiguity")
        if self.intent is not RouteIntent.COMBINED and evidence > 1:
            raise ValueError(
                "non-combined route cannot request multiple evidence kinds"
            )
        return self


class RouteDecision(BaseModel):
    """Authoritative route and safe next action for one exchange."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intent: RouteIntent
    resolved_context: ExtractedContext = ExtractedContext()
    decision_source: DecisionSource
    reason_code: ReasonCode
    retry_count: int = Field(default=0, ge=0)
    fallback_state: FallbackState = FallbackState.NOT_USED
    safe_action: SafeAction

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        expected = {
            RouteIntent.GENERAL: SafeAction.ANSWER_GENERAL,
            RouteIntent.PRODUCTION_SUMMARY: SafeAction.EXECUTE_PRODUCTION_SUMMARY,
            RouteIntent.EQUIPMENT_STATUS: SafeAction.EXECUTE_EQUIPMENT_STATUS,
            RouteIntent.DEFECT_DISTRIBUTION: (
                SafeAction.EXECUTE_DEFECT_DISTRIBUTION
            ),
            RouteIntent.DOCUMENT_SEARCH: SafeAction.EXECUTE_DOCUMENT_SEARCH,
            RouteIntent.COMBINED: SafeAction.REQUEST_CLARIFICATION,
            RouteIntent.CLARIFICATION: SafeAction.REQUEST_CLARIFICATION,
            RouteIntent.UNSUPPORTED: SafeAction.REPORT_UNSUPPORTED,
        }
        if self.safe_action is not expected[self.intent]:
            raise ValueError("safe action does not match route")
        if self.retry_count > 1:
            raise ValueError("classifier may retry at most one time")
        if (
            self.fallback_state is FallbackState.USED
            and self.decision_source is not DecisionSource.FALLBACK
        ):
            raise ValueError("fallback state requires fallback decision source")
        return self


def resolve_exchange_context(
    current: ExtractedContext, saved: ExtractedContext
) -> ExtractedContext:
    """Fill only missing current fields from saved context."""
    values = current.model_dump()
    for field in ("equipment_id", "lot_id", "document_query"):
        if values[field] is None:
            values[field] = getattr(saved, field)
    if current.start is None and current.time_preset is None:
        values["start"] = saved.start
        values["end"] = saved.end
        values["time_preset"] = saved.time_preset
    return ExtractedContext(**values)


def deterministic_gate(
    question: str,
    *,
    current_context: ExtractedContext | None = None,
    saved_context: ExtractedContext | None = None,
) -> RouteDecision | None:
    """Select only explicit routes and defer ambiguous requests."""
    text = question.casefold().strip()
    explicit = _extract_question_context(question)
    current = resolve_exchange_context(
        explicit, current_context or ExtractedContext()
    )
    context = resolve_exchange_context(
        current, saved_context or ExtractedContext()
    )

    unsupported_terms = (
        "private",
        "live production",
        "stop aoi-",
        "root cause",
        "即時私人",
        "私人製程",
        "根因",
    )
    if any(term in text for term in unsupported_terms):
        return _decision(
            RouteIntent.UNSUPPORTED,
            context,
            ReasonCode.UNSUPPORTED_CAPABILITY,
        )
    general_terms = (
        "what can you do",
        "hello",
        "thanks",
        "你好",
        "可以做什麼",
        "能協助什麼",
    )
    if any(term in text for term in general_terms):
        return _decision(
            RouteIntent.GENERAL, context, ReasonCode.GENERAL_REQUEST
        )

    flags = {
        EvidenceKind.PRODUCTION: any(
            term in text for term in ("production", "yield", "生產", "良率")
        ),
        EvidenceKind.EQUIPMENT_STATUS: any(
            term in text for term in ("equipment status", "設備狀態")
        ),
        EvidenceKind.DEFECT_DISTRIBUTION: any(
            term in text for term in ("defect distribution", "缺陷分布")
        ),
        EvidenceKind.DOCUMENTS: any(
            term in text
            for term in (
                "document",
                "manual",
                "sop",
                "guide",
                "alarm",
                "operator check",
                "optical-signal-low",
                "文件",
                "手冊",
                "指南",
                "警報",
            )
        ),
    }
    selected = [kind for kind, matched in flags.items() if matched]
    if len(selected) > 1:
        return _decision(
            RouteIntent.COMBINED, context, ReasonCode.COMBINED_REQUEST
        )
    if not selected:
        return None

    kind = selected[0]
    if kind is EvidenceKind.DOCUMENTS:
        if not context.document_query:
            return _decision(
                RouteIntent.CLARIFICATION,
                context,
                ReasonCode.CLARIFICATION_REQUIRED,
            )
        return _decision(
            RouteIntent.DOCUMENT_SEARCH, context, ReasonCode.DOCUMENT_REQUEST
        )

    if not (context.equipment_id and (context.time_preset or context.start)):
        return _decision(
            RouteIntent.CLARIFICATION,
            context,
            ReasonCode.CLARIFICATION_REQUIRED,
        )
    intent = {
        EvidenceKind.PRODUCTION: RouteIntent.PRODUCTION_SUMMARY,
        EvidenceKind.EQUIPMENT_STATUS: RouteIntent.EQUIPMENT_STATUS,
        EvidenceKind.DEFECT_DISTRIBUTION: RouteIntent.DEFECT_DISTRIBUTION,
    }[kind]
    reason = {
        RouteIntent.PRODUCTION_SUMMARY: ReasonCode.PRODUCTION_REQUEST,
        RouteIntent.EQUIPMENT_STATUS: ReasonCode.EQUIPMENT_STATUS_REQUEST,
        RouteIntent.DEFECT_DISTRIBUTION: ReasonCode.DEFECT_DISTRIBUTION_REQUEST,
    }[intent]
    return _decision(intent, context, reason)


def _extract_question_context(question: str) -> ExtractedContext:
    equipment = re.search(r"\bAOI-WAFER-\d{2}\b", question, re.IGNORECASE)
    lot = re.search(r"\bLOT-[A-Z0-9-]+\b", question, re.IGNORECASE)
    text = question.casefold()
    preset = None
    if "last 7 days" in text or "過去七天" in text:
        preset = TimePreset.LAST_7_DAYS
    elif "last 24 hours" in text or "過去 24 小時" in text:
        preset = TimePreset.LAST_24_HOURS
    elif "last 8 hours" in text or "過去 8 小時" in text:
        preset = TimePreset.LAST_8_HOURS
    elif "last 4 hours" in text or "過去 4 小時" in text:
        preset = TimePreset.LAST_4_HOURS
    elif "last 1 hour" in text or "過去 1 小時" in text:
        preset = TimePreset.LAST_1_HOUR
    elif "today" in text or "今天" in text:
        preset = TimePreset.TODAY
    document_query = None
    if any(
        term in text
        for term in ("alarm", "optical", "operator check", "警報", "光學")
    ):
        document_query = question.strip()
    return ExtractedContext(
        equipment_id=equipment.group(0).upper() if equipment else None,
        lot_id=lot.group(0).upper() if lot else None,
        time_preset=preset,
        document_query=document_query,
    )


def _decision(
    intent: RouteIntent,
    context: ExtractedContext,
    reason: ReasonCode,
) -> RouteDecision:
    action = {
        RouteIntent.GENERAL: SafeAction.ANSWER_GENERAL,
        RouteIntent.PRODUCTION_SUMMARY: SafeAction.EXECUTE_PRODUCTION_SUMMARY,
        RouteIntent.EQUIPMENT_STATUS: SafeAction.EXECUTE_EQUIPMENT_STATUS,
        RouteIntent.DEFECT_DISTRIBUTION: (
            SafeAction.EXECUTE_DEFECT_DISTRIBUTION
        ),
        RouteIntent.DOCUMENT_SEARCH: SafeAction.EXECUTE_DOCUMENT_SEARCH,
        RouteIntent.COMBINED: SafeAction.REQUEST_CLARIFICATION,
        RouteIntent.CLARIFICATION: SafeAction.REQUEST_CLARIFICATION,
        RouteIntent.UNSUPPORTED: SafeAction.REPORT_UNSUPPORTED,
    }[intent]
    return RouteDecision(
        intent=intent,
        resolved_context=context,
        decision_source=DecisionSource.DETERMINISTIC_GATE,
        reason_code=reason,
        safe_action=action,
    )
