from datetime import UTC, datetime

from industrial_agent.domain.routing import (
    DecisionSource,
    ExtractedContext,
    ReasonCode,
    RouteDecision,
    RouteIntent,
    SafeAction,
)
from industrial_agent.graph.state import EvidenceState
from industrial_agent.services.evidence import validate_answer, validate_evidence
from industrial_agent.tools.document_search import (
    DocumentSearchResult,
    RetrievedSourceResult,
)
from industrial_agent.tools.equipment_status import EquipmentStatusResult
from industrial_agent.tools.production import ProductionSummaryResult

START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 2, tzinfo=UTC)


def _route(intent: RouteIntent, context: ExtractedContext) -> RouteDecision:
    action = {
        RouteIntent.PRODUCTION_SUMMARY: SafeAction.EXECUTE_PRODUCTION_SUMMARY,
        RouteIntent.EQUIPMENT_STATUS: SafeAction.EXECUTE_EQUIPMENT_STATUS,
        RouteIntent.DOCUMENT_SEARCH: SafeAction.EXECUTE_DOCUMENT_SEARCH,
    }[intent]
    reason = {
        RouteIntent.PRODUCTION_SUMMARY: ReasonCode.PRODUCTION_REQUEST,
        RouteIntent.EQUIPMENT_STATUS: ReasonCode.EQUIPMENT_STATUS_REQUEST,
        RouteIntent.DOCUMENT_SEARCH: ReasonCode.DOCUMENT_REQUEST,
    }[intent]
    return RouteDecision(
        intent=intent,
        resolved_context=context,
        decision_source=DecisionSource.CLASSIFIER,
        reason_code=reason,
        safe_action=action,
    )


def _production(*, equipment_id: str = "AOI-WAFER-01", inspected: int = 10):
    return ProductionSummaryResult(
        equipment_id=equipment_id,
        lot_id=None,
        start=START,
        end=END,
        inspected_wafers=inspected,
        passed_wafers=9 if inspected else 0,
        failed_wafers=1 if inspected else 0,
        yield_rate=0.9 if inspected else None,
        defect_counts=(),
        alarm_events=(),
        limitations=(),
    )


def test_evidence_rejects_route_mismatch_identity_mismatch_and_empty_result():
    route = _route(
        RouteIntent.PRODUCTION_SUMMARY,
        ExtractedContext(equipment_id="AOI-WAFER-01", start=START, end=END),
    )
    assert not validate_evidence(route, EvidenceState()).sufficient
    assert not validate_evidence(
        route,
        EvidenceState(production_summary=_production(equipment_id="OTHER")),
    ).sufficient
    assert not validate_evidence(
        route, EvidenceState(production_summary=_production(inspected=0))
    ).sufficient


def test_evidence_rejects_unknown_equipment_status():
    route = _route(
        RouteIntent.EQUIPMENT_STATUS,
        ExtractedContext(equipment_id="AOI-WAFER-01"),
    )
    result = EquipmentStatusResult(
        equipment_id="AOI-WAFER-01",
        observed_at=START,
        status="unknown",
        effective_start=None,
        effective_end=None,
        source_event_id=None,
        reason_code=None,
        limitations=("no_recorded_state",),
    )
    assert not validate_evidence(
        route, EvidenceState(equipment_status=result)
    ).sufficient


def test_document_evidence_requires_source_and_answer_citation():
    route = _route(
        RouteIntent.DOCUMENT_SEARCH,
        ExtractedContext(document_query="alarm reset"),
    )
    result = DocumentSearchResult(
        query="alarm reset",
        sources=(
            RetrievedSourceResult(
                source_id="alarm-guide:reset:001",
                title="Alarm Guide",
                section="Reset",
                relative_path="data/synthetic/documents/alarm.md",
                excerpt="Reset only after inspection.",
                score=0.8,
                source="built_in",
            ),
        ),
        limitations=(),
    )
    evidence = EvidenceState(document_search=result)
    assert validate_evidence(route, evidence).sufficient
    rejected = validate_answer(route, evidence, "Reset after inspection.")
    assert not rejected.sufficient
    assert rejected.response_text == (
        "Document evidence was found, but the generated answer could not be "
        "verified. Review the retrieved sources below."
    )
    assert validate_answer(
        route, evidence, "Reset after inspection [alarm-guide:reset:001]."
    ).sufficient


def test_document_evidence_ignores_unrelated_saved_equipment_context():
    route = _route(
        RouteIntent.DOCUMENT_SEARCH,
        ExtractedContext(
            equipment_id="AOI-WAFER-01", document_query="alarm reset"
        ),
    )
    result = DocumentSearchResult(
        query="alarm reset",
        sources=(
            RetrievedSourceResult(
                source_id="alarm-guide:reset:001",
                title="Alarm Guide",
                section="Reset",
                relative_path="data/synthetic/documents/alarm.md",
                excerpt="Reset only after inspection.",
                score=0.8,
                source="built_in",
            ),
        ),
        limitations=(),
    )

    assert validate_evidence(
        route, EvidenceState(document_search=result)
    ).sufficient


def test_answer_rejects_numeric_value_absent_from_evidence():
    route = _route(
        RouteIntent.PRODUCTION_SUMMARY,
        ExtractedContext(equipment_id="AOI-WAFER-01", start=START, end=END),
    )
    evidence = EvidenceState(production_summary=_production())
    assert validate_answer(
        route, evidence, "Yield was 90% across 10 wafers."
    ).sufficient
    rejected = validate_answer(route, evidence, "Yield was 75%.")
    assert not rejected.sufficient
    assert rejected.response_text == (
        "Production evidence was found, but the generated answer could not be "
        "verified. Review the deterministic evidence below."
    )


def test_answer_accepts_evidence_percentage_with_display_rounding():
    route = _route(
        RouteIntent.PRODUCTION_SUMMARY,
        ExtractedContext(equipment_id="AOI-WAFER-01", start=START, end=END),
    )
    evidence = EvidenceState(
        production_summary=ProductionSummaryResult(
            equipment_id="AOI-WAFER-01",
            lot_id=None,
            start=START,
            end=END,
            inspected_wafers=800,
            passed_wafers=762,
            failed_wafers=38,
            yield_rate=0.9525,
            defect_counts=(),
            alarm_events=(),
            limitations=(),
        )
    )

    assert validate_answer(
        route, evidence, "Yield was 95.3 percent across 800 wafers."
    ).sufficient
