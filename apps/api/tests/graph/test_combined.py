from datetime import UTC, datetime

import pytest

from industrial_agent.domain.routing import (
    DecisionSource,
    EvidenceKind,
    ExtractedContext,
    ReasonCode,
    RequestedEvidence,
    RouteDecision,
    RouteIntent,
    SafeAction,
)
from industrial_agent.graph.combined import (
    CombinedExecutionCancelled,
    CombinedToolUnavailable,
    EvidencePathStatus,
    build_enriched_document_query,
    combined_fallback_text,
    execute_combined_evidence,
)
from industrial_agent.graph.workflow import COMBINED_EVIDENCE_TOOL
from industrial_agent.services.evidence import (
    CombinedAnswerRejection,
    validate_combined_answer,
)
from industrial_agent.tools.defect_distribution import (
    DefectDistributionItemResult,
    DefectDistributionResult,
)
from industrial_agent.tools.document_search import DocumentSearchResult
from industrial_agent.tools.equipment_status import EquipmentStatusResult
from industrial_agent.tools.production import (
    AlarmEventResult,
    ProductionSummaryResult,
)

START = datetime(2026, 1, 15, 15, tzinfo=UTC)
END = datetime(2026, 1, 15, 17, tzinfo=UTC)


def _decision(kind: EvidenceKind = EvidenceKind.PRODUCTION) -> RouteDecision:
    return RouteDecision(
        intent=RouteIntent.COMBINED,
        requested_evidence=RequestedEvidence(
            **{kind.value: True, EvidenceKind.DOCUMENTS.value: True}
        ),
        resolved_context=ExtractedContext(
            equipment_id="AOI-WAFER-01", start=START, end=END
        ),
        decision_source=DecisionSource.DETERMINISTIC_GATE,
        reason_code=ReasonCode.COMBINED_REQUEST,
        safe_action=SafeAction.EXECUTE_COMBINED,
    )


def test_document_query_enrichment_uses_only_allowlisted_result_fields() -> None:
    production = ProductionSummaryResult(
        equipment_id="AOI-WAFER-01",
        lot_id="LOT-DEMO-001",
        start=START,
        end=END,
        inspected_wafers=300,
        passed_wafers=257,
        failed_wafers=43,
        yield_rate=257 / 300,
        defect_counts=(),
        alarm_events=(
            AlarmEventResult(
                event_id="ALARM-001",
                code="OPTICAL-SIGNAL-LOW",
                started_at=START,
                ended_at=END,
            ),
        ),
        limitations=(),
    )

    query = build_enriched_document_query(
        "Find the guide for this production result.",
        EvidenceKind.PRODUCTION,
        production,
    )

    assert query == ("Find the guide for this production result. OPTICAL-SIGNAL-LOW")
    assert "300" not in query
    assert "85.67" not in query


def test_document_query_enrichment_is_stable_for_status_and_defects() -> None:
    status = EquipmentStatusResult(
        equipment_id="AOI-WAFER-01",
        observed_at=END,
        status="warning",
        effective_start=START,
        effective_end=END,
        source_event_id="STATE-001",
        reason_code="OPTICAL-SIGNAL-LOW",
        limitations=(),
    )
    distribution = DefectDistributionResult(
        equipment_id="AOI-WAFER-01",
        lot_id=None,
        start=START,
        end=END,
        failed_wafers=4,
        classified_defect_count=4,
        unclassified_failed_wafers=0,
        items=(
            DefectDistributionItemResult(
                category="edge-chip", count=3, share=0.75, rank=1
            ),
            DefectDistributionItemResult(
                category="scratch", count=1, share=0.25, rank=2
            ),
        ),
        limitations=(),
    )

    assert (
        build_enriched_document_query(
            "Explain warning warning.", EvidenceKind.EQUIPMENT_STATUS, status
        )
        == "Explain warning warning. OPTICAL-SIGNAL-LOW"
    )
    assert (
        build_enriched_document_query(
            "Find defect procedures.", EvidenceKind.DEFECT_DISTRIBUTION, distribution
        )
        == "Find defect procedures. edge-chip scratch"
    )


def test_combined_executor_runs_production_then_enriched_document_search() -> None:
    outcome = execute_combined_evidence(
        decision=_decision(),
        original_query="Find the manual for the recorded production alarms.",
    )

    assert outcome.manufacturing.status is EvidencePathStatus.SUCCEEDED
    assert outcome.manufacturing.result is not None
    assert outcome.documents.status is EvidencePathStatus.SUCCEEDED
    assert outcome.documents.result is not None
    assert "OPTICAL-SIGNAL-LOW" in outcome.document_query
    assert outcome.documents.result.query == outcome.document_query
    assert outcome.documents.result.sources


def test_combined_executor_keeps_document_evidence_on_manufacturing_failure() -> None:
    def fail_production(_request):
        raise CombinedToolUnavailable("private provider detail")

    outcome = execute_combined_evidence(
        decision=_decision(),
        original_query="Find the optical signal alarm guide.",
        production_tool=fail_production,
    )

    assert outcome.manufacturing.status is EvidencePathStatus.FAILED
    assert outcome.manufacturing.error_code == "TOOL_UNAVAILABLE"
    assert "private provider detail" not in str(outcome.manufacturing)
    assert outcome.documents.status is EvidencePathStatus.SUCCEEDED
    assert outcome.documents.result is not None
    assert outcome.document_query == "Find the optical signal alarm guide."


@pytest.mark.parametrize(
    ("kind", "query", "expected_term"),
    (
        (
            EvidenceKind.EQUIPMENT_STATUS,
            "Find the guide related to this equipment state.",
            "SYNTHETIC-SCHEDULED-RUN",
        ),
        (
            EvidenceKind.DEFECT_DISTRIBUTION,
            "Find procedures related to these defects.",
            "edge-chip",
        ),
    ),
)
def test_combined_executor_supports_each_manufacturing_pairing(
    kind: EvidenceKind,
    query: str,
    expected_term: str,
) -> None:
    outcome = execute_combined_evidence(decision=_decision(kind), original_query=query)

    assert outcome.manufacturing.status is EvidencePathStatus.SUCCEEDED
    assert expected_term in outcome.document_query
    assert outcome.documents.status in {
        EvidencePathStatus.SUCCEEDED,
        EvidencePathStatus.EMPTY,
    }


def test_combined_executor_distinguishes_empty_evidence_from_failure() -> None:
    empty_decision = RouteDecision(
        **{
            **_decision().model_dump(),
            "resolved_context": ExtractedContext(
                equipment_id="AOI-WAFER-01",
                start=datetime(2026, 1, 10, tzinfo=UTC),
                end=datetime(2026, 1, 11, tzinfo=UTC),
            ),
        }
    )

    outcome = execute_combined_evidence(
        decision=empty_decision,
        original_query="xyzzy qqqnonexistent",
    )

    assert outcome.manufacturing.status is EvidencePathStatus.EMPTY
    assert outcome.manufacturing.result is not None
    assert outcome.documents.status is EvidencePathStatus.EMPTY
    assert outcome.documents.result is not None


def test_combined_executor_reports_two_independent_safe_failures() -> None:
    def fail_production(_request):
        raise CombinedToolUnavailable("production secret")

    def fail_documents(_request, *, service=None):
        raise CombinedToolUnavailable(f"document secret {service}")

    outcome = execute_combined_evidence(
        decision=_decision(),
        original_query="Find the optical signal guide.",
        production_tool=fail_production,
        document_search_tool=fail_documents,
    )

    assert outcome.manufacturing.status is EvidencePathStatus.FAILED
    assert outcome.documents.status is EvidencePathStatus.FAILED
    assert outcome.manufacturing.error_code == "TOOL_UNAVAILABLE"
    assert outcome.documents.error_code == "TOOL_UNAVAILABLE"


def test_combined_executor_cancellation_stops_before_document_search() -> None:
    document_called = False
    cancellation_checks = 0

    def search(_request, *, service=None):
        nonlocal document_called
        document_called = True
        raise AssertionError(service)

    def cancel_after_manufacturing() -> bool:
        nonlocal cancellation_checks
        cancellation_checks += 1
        return cancellation_checks == 2

    with pytest.raises(CombinedExecutionCancelled):
        execute_combined_evidence(
            decision=_decision(),
            original_query="Find the guide.",
            document_search_tool=search,
            is_cancelled=cancel_after_manufacturing,
        )

    assert not document_called
    assert cancellation_checks == 2


def test_combined_answer_rejects_unsupported_values_references_and_claims() -> None:
    outcome = execute_combined_evidence(
        decision=_decision(),
        original_query="Find the manual for the recorded production alarms.",
    )
    source_id = outcome.documents.result.sources[0].source_id
    yield_rate = outcome.manufacturing.result.yield_rate

    assert validate_combined_answer(
        outcome,
        f"The recorded yield was {yield_rate * 100:.1f}%; see {source_id}. "
        "This may be related and still requires validation.",
    )
    unsupported_value = validate_combined_answer(
        outcome, f"The yield was 99.9%; see {source_id}."
    )
    assert not unsupported_value
    assert (
        unsupported_value.reason
        is CombinedAnswerRejection.UNSUPPORTED_MANUFACTURING_VALUE
    )

    invalid_reference = validate_combined_answer(
        outcome,
        f"The recorded yield was {yield_rate * 100:.1f}%; see "
        "fake-guide:missing-section:001.",
    )
    assert not invalid_reference
    assert (
        invalid_reference.reason is CombinedAnswerRejection.INVALID_DOCUMENT_REFERENCE
    )

    causal = validate_combined_answer(
        outcome,
        f"The alarm caused the yield change; see {source_id}.",
    )
    assert not causal
    assert causal.reason is CombinedAnswerRejection.CAUSAL_CLAIM

    negated_causal = validate_combined_answer(
        outcome,
        "The guide says not to infer low yield as the cause of the alarm.",
    )
    assert negated_causal

    false_threshold = validate_combined_answer(
        outcome, "The recorded yield was above 90%."
    )
    assert not false_threshold
    assert (
        false_threshold.reason
        is CombinedAnswerRejection.UNSUPPORTED_MANUFACTURING_VALUE
    )

    contradictory_threshold = validate_combined_answer(
        outcome, "The recorded yield was 87.5%, which is above 90%."
    )
    assert not contradictory_threshold
    assert (
        contradictory_threshold.reason
        is CombinedAnswerRejection.UNSUPPORTED_MANUFACTURING_VALUE
    )

    invented_defect = validate_combined_answer(
        outcome, "The recorded defects included 5 particle defects."
    )
    assert not invented_defect
    assert (
        invented_defect.reason
        is CombinedAnswerRejection.UNSUPPORTED_MANUFACTURING_VALUE
    )

    invented_processed_count = validate_combined_answer(
        outcome,
        "The line processed 999 wafers. Production reached 999 wafers. "
        "Yield is 99.9 percent.",
    )
    assert not invented_processed_count
    assert (
        invented_processed_count.reason
        is CombinedAnswerRejection.UNSUPPORTED_MANUFACTURING_VALUE
    )

    invalid_status = validate_combined_answer(
        execute_combined_evidence(
            decision=_decision(EvidenceKind.EQUIPMENT_STATUS),
            original_query="Find guidance for the recorded equipment status.",
        ),
        "Equipment status is idle.",
    )
    assert not invalid_status
    assert (
        invalid_status.reason is CombinedAnswerRejection.UNSUPPORTED_OPERATIONAL_CLAIM
    )

    operational = validate_combined_answer(
        outcome,
        "The recorded yield indicates no immediate process failure.",
    )
    assert not operational
    assert operational.reason is CombinedAnswerRejection.UNSUPPORTED_OPERATIONAL_CLAIM


def test_combined_answer_accepts_grounded_domain_claims_without_inline_citation() -> (
    None
):
    outcome = execute_combined_evidence(
        decision=_decision(),
        original_query="Find the manual for the recorded production alarms.",
    )

    validation = validate_combined_answer(
        outcome,
        """### Recorded facts
1. 200 wafers were inspected: 175 passed and 25 failed.
2. Yield was 87.5%, which is above 80%.
3. Defects included 19 edge-chip and 6 scratch.

Calculation: (175 / 200) × 100 = 87.5%.
The recorded alarm ran from 15:00 to 16:00.
The structured Sources surface contains the retrieved document references.
This may suggest tool wear, but it is only a hypothesis that requires validation.
""",
    )

    assert validation


def test_combined_answer_requires_explicit_validation_for_hypotheses() -> None:
    outcome = execute_combined_evidence(
        decision=_decision(),
        original_query="Find the manual for the recorded production alarms.",
    )

    validation = validate_combined_answer(
        outcome,
        "Tool wear may be a possible hypothesis.",
    )

    assert not validation
    assert validation.reason is CombinedAnswerRejection.UNVALIDATED_HYPOTHESIS

    guidance = validate_combined_answer(
        outcome,
        "The guide suggests checking the optical path.",
    )
    assert guidance


def test_combined_answer_validates_defect_distribution_counts() -> None:
    outcome = execute_combined_evidence(
        decision=_decision(EvidenceKind.DEFECT_DISTRIBUTION),
        original_query="Find guidance related to the defect distribution.",
    )

    validation = validate_combined_answer(
        outcome,
        "The distribution contains 999 edge-chip defects; edge-chip: 999. "
        "Failed wafers: 999.",
    )

    assert not validation
    assert validation.reason is CombinedAnswerRejection.UNSUPPORTED_MANUFACTURING_VALUE


def test_combined_answer_rejects_source_id_when_documents_are_unavailable() -> None:
    def unavailable_documents(*args: object, **kwargs: object) -> DocumentSearchResult:
        raise CombinedToolUnavailable

    outcome = execute_combined_evidence(
        decision=_decision(),
        original_query="Find the manual for the recorded production alarms.",
        document_search_tool=unavailable_documents,
    )

    validation = validate_combined_answer(
        outcome,
        "See fake-guide:missing-section:001.",
    )

    assert not validation
    assert validation.reason is CombinedAnswerRejection.INVALID_DOCUMENT_REFERENCE


def test_combined_synthesis_contract_guides_small_local_models() -> None:
    description = COMBINED_EVIDENCE_TOOL.description

    assert "Do not repeat source IDs" in description
    assert "requires validation" in description
    assert "Do not claim equipment or process status" in description
    assert "Do not claim causality" in description


def test_combined_fallback_distinguishes_double_failure_from_model_failure() -> None:
    def fail(_request, **_kwargs):
        raise CombinedToolUnavailable("unavailable")

    double_failure = execute_combined_evidence(
        decision=_decision(),
        original_query="Find the guide.",
        production_tool=fail,
        document_search_tool=fail,
    )
    evidence_available = execute_combined_evidence(
        decision=_decision(),
        original_query="Find the optical signal guide.",
    )

    assert combined_fallback_text(double_failure) == (
        "Neither manufacturing nor document evidence could be retrieved."
    )
    assert combined_fallback_text(evidence_available) == (
        "Evidence was retrieved, but a combined interpretation could not be "
        "completed. Review the evidence below."
    )
