"""Bounded orchestration primitives for one combined evidence exchange."""

from collections.abc import Callable, Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from industrial_agent.domain.routing import (
    EvidenceKind,
    RouteDecision,
    RouteIntent,
    TimePreset,
)
from industrial_agent.llm.errors import LLMError
from industrial_agent.services.documents import (
    DocumentCorpusService,
    DocumentStoreError,
)
from industrial_agent.tools.defect_distribution import (
    DefectDistributionRequest,
    DefectDistributionResult,
    DefectDistributionToolError,
    get_defect_distribution,
)
from industrial_agent.tools.document_search import (
    DocumentSearchRequest,
    DocumentSearchResult,
    search_documents,
)
from industrial_agent.tools.equipment_status import (
    EquipmentStatusRequest,
    EquipmentStatusResult,
    EquipmentStatusToolError,
    get_equipment_status,
)
from industrial_agent.tools.production import (
    ProductionSummaryRequest,
    ProductionSummaryResult,
    ProductionToolError,
    get_production_summary,
)

ManufacturingResult = (
    ProductionSummaryResult | EquipmentStatusResult | DefectDistributionResult
)
EvidenceResult = ManufacturingResult | DocumentSearchResult

_DEMO_SHIFT_END = datetime(2026, 1, 15, 17, tzinfo=UTC)


class EvidencePathStatus(StrEnum):
    """Observable terminal state for one bounded evidence path."""

    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    FAILED = "failed"
    NOT_RUN = "not_run"


class CombinedAnswerStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FALLBACK = "fallback"


class CombinedExecutionCancelled(RuntimeError):
    """Raised when caller cancellation stops remaining evidence work."""


class CombinedToolUnavailable(RuntimeError):
    """Typed boundary for an expected tool/service availability failure."""


@dataclass(frozen=True, slots=True)
class EvidencePathOutcome:
    status: EvidencePathStatus
    result: EvidenceResult | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class CombinedEvidenceOutcome:
    manufacturing_kind: EvidenceKind
    manufacturing: EvidencePathOutcome
    documents: EvidencePathOutcome
    document_query: str


@dataclass(frozen=True, slots=True)
class CombinedProgress:
    """One observable step emitted at the real sequential execution boundary."""

    phase: str
    path: str | None = None
    manufacturing_kind: EvidenceKind | None = None
    outcome: EvidencePathOutcome | None = None
    document_query: str | None = None
    completed: CombinedEvidenceOutcome | None = None


@dataclass(frozen=True, slots=True)
class CombinedAnswer:
    text: str
    status: CombinedAnswerStatus


@dataclass(frozen=True, slots=True)
class CombinedExchangeEvidence:
    evidence: CombinedEvidenceOutcome
    answer_status: CombinedAnswerStatus

    @property
    def manufacturing_kind(self) -> EvidenceKind:
        return self.evidence.manufacturing_kind

    @property
    def manufacturing(self) -> EvidencePathOutcome:
        return self.evidence.manufacturing

    @property
    def documents(self) -> EvidencePathOutcome:
        return self.evidence.documents

    @property
    def document_query(self) -> str:
        return self.evidence.document_query


def combined_evidence_payload(outcome: CombinedEvidenceOutcome) -> dict[str, object]:
    """Serialize current-exchange evidence without private exception details."""

    def path_payload(path: EvidencePathOutcome) -> dict[str, object]:
        return {
            "status": path.status.value,
            "result": (
                path.result.model_dump(mode="json") if path.result is not None else None
            ),
            "error_code": path.error_code,
        }

    return {
        "manufacturing_kind": outcome.manufacturing_kind.value,
        "manufacturing": path_payload(outcome.manufacturing),
        "documents": path_payload(outcome.documents),
        "document_query": outcome.document_query,
    }


def combined_fallback_text(outcome: CombinedEvidenceOutcome) -> str:
    """Return application-owned text without reconstructing missing evidence."""
    if all(
        path.status is EvidencePathStatus.FAILED
        for path in (outcome.manufacturing, outcome.documents)
    ):
        return "Neither manufacturing nor document evidence could be retrieved."
    return (
        "Evidence was retrieved, but a combined interpretation could not be "
        "completed. Review the evidence below."
    )


def synthesize_combined_answer(
    outcome: CombinedEvidenceOutcome,
    *,
    generate: Callable[[dict[str, object]], str] | None,
    validate: Callable[[CombinedEvidenceOutcome, str], bool],
) -> CombinedAnswer:
    """Generate once when possible and otherwise retain a fixed safe fallback."""
    fallback = CombinedAnswer(
        combined_fallback_text(outcome), CombinedAnswerStatus.FALLBACK
    )
    if generate is None or all(
        path.status is EvidencePathStatus.FAILED
        for path in (outcome.manufacturing, outcome.documents)
    ):
        return fallback
    try:
        candidate = generate(combined_evidence_payload(outcome)).strip()
    except LLMError:
        return fallback
    if validate(outcome, candidate):
        return CombinedAnswer(candidate, CombinedAnswerStatus.SUCCEEDED)
    return fallback


def build_enriched_document_query(
    original_query: str,
    evidence_kind: EvidenceKind,
    result: ManufacturingResult | None,
) -> str:
    """Append only explicit allowlisted manufacturing fields in stable order."""
    terms: tuple[str, ...] = ()
    if evidence_kind is EvidenceKind.PRODUCTION and isinstance(
        result, ProductionSummaryResult
    ):
        terms = tuple(alarm.code for alarm in result.alarm_events)
    elif evidence_kind is EvidenceKind.EQUIPMENT_STATUS and isinstance(
        result, EquipmentStatusResult
    ):
        terms = tuple(term for term in (result.status, result.reason_code) if term)
    elif evidence_kind is EvidenceKind.DEFECT_DISTRIBUTION and isinstance(
        result, DefectDistributionResult
    ):
        terms = tuple(item.category for item in result.items)

    existing = set(original_query.casefold().split())
    appended: list[str] = []
    for term in terms:
        normalized = term.casefold()
        if normalized not in existing and normalized not in {
            item.casefold() for item in appended
        }:
            appended.append(term)
    return " ".join((original_query.strip(), *appended)).strip()


def execute_combined_evidence(
    *,
    decision: RouteDecision,
    original_query: str,
    document_corpus_service: DocumentCorpusService | None = None,
    production_tool: Callable[
        [ProductionSummaryRequest], ProductionSummaryResult
    ] = get_production_summary,
    equipment_status_tool: Callable[
        [EquipmentStatusRequest], EquipmentStatusResult
    ] = get_equipment_status,
    defect_distribution_tool: Callable[
        [DefectDistributionRequest], DefectDistributionResult
    ] = get_defect_distribution,
    document_search_tool: Callable[..., DocumentSearchResult] = search_documents,
    is_cancelled: Callable[[], bool] = lambda: False,
) -> CombinedEvidenceOutcome:
    """Execute one manufacturing path, then one deterministically enriched search."""
    progress = stream_combined_evidence(
        decision=decision,
        original_query=original_query,
        document_corpus_service=document_corpus_service,
        production_tool=production_tool,
        equipment_status_tool=equipment_status_tool,
        defect_distribution_tool=defect_distribution_tool,
        document_search_tool=document_search_tool,
        is_cancelled=is_cancelled,
    )
    completed: CombinedEvidenceOutcome | None = None
    for event in progress:
        if event.completed is not None:
            completed = event.completed
    if completed is None:
        raise RuntimeError("combined execution ended without a result")
    return completed


def stream_combined_evidence(
    *,
    decision: RouteDecision,
    original_query: str,
    document_corpus_service: DocumentCorpusService | None = None,
    production_tool: Callable[
        [ProductionSummaryRequest], ProductionSummaryResult
    ] = get_production_summary,
    equipment_status_tool: Callable[
        [EquipmentStatusRequest], EquipmentStatusResult
    ] = get_equipment_status,
    defect_distribution_tool: Callable[
        [DefectDistributionRequest], DefectDistributionResult
    ] = get_defect_distribution,
    document_search_tool: Callable[..., DocumentSearchResult] = search_documents,
    is_cancelled: Callable[[], bool] = lambda: False,
) -> Generator[CombinedProgress, None, None]:
    """Yield live path boundaries while executing manufacturing before documents."""
    if decision.intent is not RouteIntent.COMBINED:
        raise ValueError("combined evidence requires a combined route")
    kinds = decision.requested_evidence.kinds - {EvidenceKind.DOCUMENTS}
    if len(kinds) != 1:
        raise ValueError("combined route must select one manufacturing evidence kind")
    manufacturing_kind = next(iter(kinds))
    if is_cancelled():
        raise CombinedExecutionCancelled("Combined evidence execution cancelled")
    yield CombinedProgress(
        phase="started", path="manufacturing", manufacturing_kind=manufacturing_kind
    )
    try:
        manufacturing_result = _execute_manufacturing(
            decision,
            manufacturing_kind,
            production_tool=production_tool,
            equipment_status_tool=equipment_status_tool,
            defect_distribution_tool=defect_distribution_tool,
        )
    except (
        ProductionToolError,
        EquipmentStatusToolError,
        DefectDistributionToolError,
        CombinedToolUnavailable,
    ):
        manufacturing_result = None
        manufacturing = EvidencePathOutcome(
            status=EvidencePathStatus.FAILED,
            error_code="TOOL_UNAVAILABLE",
        )
    else:
        manufacturing = EvidencePathOutcome(
            status=(
                EvidencePathStatus.EMPTY
                if _is_empty(manufacturing_result)
                else EvidencePathStatus.SUCCEEDED
            ),
            result=manufacturing_result,
        )
    yield CombinedProgress(
        phase="completed",
        path="manufacturing",
        manufacturing_kind=manufacturing_kind,
        outcome=manufacturing,
    )

    document_query = build_enriched_document_query(
        original_query, manufacturing_kind, manufacturing_result
    )
    if is_cancelled():
        raise CombinedExecutionCancelled("Combined evidence execution cancelled")
    yield CombinedProgress(
        phase="started",
        path="documents",
        manufacturing_kind=manufacturing_kind,
        document_query=document_query,
    )
    try:
        document_result = document_search_tool(
            DocumentSearchRequest(query=document_query, limit=3),
            service=document_corpus_service,
        )
    except (DocumentStoreError, CombinedToolUnavailable):
        documents = EvidencePathOutcome(
            status=EvidencePathStatus.FAILED,
            error_code="TOOL_UNAVAILABLE",
        )
    else:
        documents = EvidencePathOutcome(
            status=(
                EvidencePathStatus.EMPTY
                if _is_empty(document_result)
                else EvidencePathStatus.SUCCEEDED
            ),
            result=document_result,
        )
    yield CombinedProgress(
        phase="completed",
        path="documents",
        manufacturing_kind=manufacturing_kind,
        outcome=documents,
        document_query=document_query,
    )
    completed = CombinedEvidenceOutcome(
        manufacturing_kind=manufacturing_kind,
        manufacturing=manufacturing,
        documents=documents,
        document_query=document_query,
    )
    yield CombinedProgress(phase="finished", completed=completed)


def _execute_manufacturing(
    decision: RouteDecision,
    kind: EvidenceKind,
    *,
    production_tool: Callable[[ProductionSummaryRequest], ProductionSummaryResult],
    equipment_status_tool: Callable[[EquipmentStatusRequest], EquipmentStatusResult],
    defect_distribution_tool: Callable[
        [DefectDistributionRequest], DefectDistributionResult
    ],
) -> ManufacturingResult:
    context = decision.resolved_context
    if context.equipment_id is None:
        raise ValueError("equipment context is required")
    start, end = _resolve_range(context.start, context.end, context.time_preset)
    if kind is EvidenceKind.EQUIPMENT_STATUS:
        return equipment_status_tool(
            EquipmentStatusRequest(equipment_id=context.equipment_id, at=end)
        )
    request_values = {
        "equipment_id": context.equipment_id,
        "lot_id": context.lot_id,
        "start": start,
        "end": end,
    }
    if kind is EvidenceKind.PRODUCTION:
        return production_tool(ProductionSummaryRequest(**request_values))
    if kind is EvidenceKind.DEFECT_DISTRIBUTION:
        return defect_distribution_tool(DefectDistributionRequest(**request_values))
    raise ValueError("unsupported manufacturing evidence kind")


def _resolve_range(
    start: datetime | None,
    end: datetime | None,
    preset: TimePreset | None,
) -> tuple[datetime, datetime]:
    if start is not None and end is not None:
        return start, end
    if preset is None:
        raise ValueError("time range is required")
    if preset is TimePreset.TODAY:
        return _DEMO_SHIFT_END.replace(hour=0), _DEMO_SHIFT_END
    hours = {
        TimePreset.LAST_1_HOUR: 1,
        TimePreset.LAST_4_HOURS: 4,
        TimePreset.LAST_8_HOURS: 8,
        TimePreset.LAST_24_HOURS: 24,
        TimePreset.LAST_7_DAYS: 24 * 7,
    }[preset]
    return _DEMO_SHIFT_END - timedelta(hours=hours), _DEMO_SHIFT_END


def _is_empty(result: EvidenceResult) -> bool:
    if isinstance(result, ProductionSummaryResult):
        return result.inspected_wafers == 0
    if isinstance(result, EquipmentStatusResult):
        return result.status == "unknown"
    if isinstance(result, DefectDistributionResult):
        return not result.items
    return not result.sources
