import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from industrial_agent.domain.routing import (
    AmbiguityCode,
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
    TimePreset,
    deterministic_gate,
    resolve_exchange_context,
)

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "routing_scenarios.json"


def _context(payload: dict[str, object] | None) -> ExtractedContext:
    return ExtractedContext(**(payload or {}))


def test_route_intent_exposes_only_the_approved_routes() -> None:
    assert tuple(intent.value for intent in RouteIntent) == (
        "general",
        "production_summary",
        "equipment_status",
        "defect_distribution",
        "document_search",
        "combined",
        "clarification",
        "unsupported",
    )


@pytest.mark.parametrize(
    ("phrase", "preset"),
    [
        ("last 1 hour", TimePreset.LAST_1_HOUR),
        ("last 4 hours", TimePreset.LAST_4_HOURS),
        ("last 8 hours", TimePreset.LAST_8_HOURS),
        ("過去 4 小時", TimePreset.LAST_4_HOURS),
    ],
)
def test_gate_extracts_supported_short_presets_and_lot(
    phrase: str, preset: TimePreset
) -> None:
    decision = deterministic_gate(
        f"Show AOI-WAFER-01 yield for LOT-DEMO-001 over the {phrase}."
    )

    assert decision is not None
    assert decision.resolved_context.time_preset is preset
    assert decision.resolved_context.lot_id == "LOT-DEMO-001"


def test_routing_enums_are_string_enums() -> None:
    assert isinstance(RouteIntent.GENERAL, str)
    assert EvidenceKind.PRODUCTION.value == "production"
    assert TimePreset.TODAY.value == "today"
    assert DecisionSource.DETERMINISTIC_GATE.value == "deterministic_gate"
    assert FallbackState.NOT_USED.value == "not_used"


def test_requested_evidence_is_immutable_and_exposes_selected_kinds() -> None:
    from industrial_agent.domain.routing import RequestedEvidence

    evidence = RequestedEvidence(production=True, documents=True)

    assert evidence.kinds == frozenset(
        {EvidenceKind.PRODUCTION, EvidenceKind.DOCUMENTS}
    )
    assert evidence.count == 2
    with pytest.raises(ValidationError):
        evidence.documents = False
    with pytest.raises(ValidationError):
        RequestedEvidence(production=True, unexpected=True)


def test_extracted_context_requires_a_complete_utc_range_or_supported_preset() -> None:
    with pytest.raises(ValidationError, match="both start and end"):
        ExtractedContext(start=datetime(2026, 1, 1, 0, tzinfo=UTC))

    with pytest.raises(ValidationError, match="UTC"):
        ExtractedContext(
            start=datetime(2026, 1, 1, 0),
            end=datetime(2026, 1, 2, 0),
        )

    with pytest.raises(ValidationError, match="after start"):
        ExtractedContext(
            start=datetime(2026, 1, 2, 0, tzinfo=UTC),
            end=datetime(2026, 1, 1, 0, tzinfo=UTC),
        )

    with pytest.raises(ValidationError, match="preset"):
        ExtractedContext(
            start=datetime(2026, 1, 1, 0, tzinfo=UTC),
            end=datetime(2026, 1, 2, 0, tzinfo=UTC),
            time_preset=TimePreset.TODAY,
        )


def test_context_resolution_prefers_current_values_and_fills_only_missing_values(
) -> None:
    current = ExtractedContext(
        equipment_id="AOI-WAFER-01",
        start=datetime(2026, 1, 2, 0, tzinfo=UTC),
        end=datetime(2026, 1, 3, 0, tzinfo=UTC),
    )
    saved = ExtractedContext(
        equipment_id="AOI-WAFER-02",
        lot_id="LOT-DEMO-001",
        time_preset=TimePreset.LAST_24_HOURS,
        document_query="optical signal alarm",
    )

    resolved = resolve_exchange_context(current, saved)

    assert resolved.equipment_id == "AOI-WAFER-01"
    assert resolved.lot_id == "LOT-DEMO-001"
    assert resolved.start == current.start
    assert resolved.end == current.end
    assert resolved.time_preset is None
    assert resolved.document_query == "optical signal alarm"


def test_route_candidate_rejects_invalid_evidence_and_forbidden_model_fields() -> None:
    with pytest.raises(ValidationError, match="production evidence"):
        RouteCandidate(
            intent=RouteIntent.PRODUCTION_SUMMARY,
            requested_evidence={"documents": True},
            reason_code=ReasonCode.PRODUCTION_REQUEST,
        )

    with pytest.raises(ValidationError, match="documents and exactly one"):
        RouteCandidate(
            intent=RouteIntent.COMBINED,
            requested_evidence={"production": True},
            reason_code=ReasonCode.COMBINED_REQUEST,
        )

    with pytest.raises(ValidationError, match="documents and exactly one"):
        RouteCandidate(
            intent=RouteIntent.COMBINED,
            requested_evidence={
                "production": True,
                "equipment_status": True,
                "documents": True,
            },
            reason_code=ReasonCode.COMBINED_REQUEST,
        )

    combined = RouteCandidate(
        intent=RouteIntent.COMBINED,
        requested_evidence={"equipment_status": True, "documents": True},
        reason_code=ReasonCode.COMBINED_REQUEST,
    )
    assert combined.requested_evidence.kinds == {
        EvidenceKind.EQUIPMENT_STATUS,
        EvidenceKind.DOCUMENTS,
    }

    with pytest.raises(ValidationError, match="unsupported"):
        RouteCandidate(
            intent=RouteIntent.UNSUPPORTED,
            requested_evidence={"documents": True},
            reason_code=ReasonCode.UNSUPPORTED_CAPABILITY,
        )

    with pytest.raises(ValidationError, match="confidence"):
        RouteCandidate(
            intent=RouteIntent.GENERAL,
            reason_code=ReasonCode.GENERAL_REQUEST,
            confidence=0.99,
        )

    with pytest.raises(ValidationError, match="reasoning"):
        RouteCandidate(
            intent=RouteIntent.GENERAL,
            reason_code=ReasonCode.GENERAL_REQUEST,
            reasoning="hidden model chain",
        )


def test_clarification_candidate_requires_a_missing_field_or_ambiguity() -> None:
    with pytest.raises(ValidationError, match="missing field or ambiguity"):
        RouteCandidate(
            intent=RouteIntent.CLARIFICATION,
            reason_code=ReasonCode.CLARIFICATION_REQUIRED,
        )

    candidate = RouteCandidate(
        intent=RouteIntent.CLARIFICATION,
        missing_fields=(MissingField.EQUIPMENT_ID,),
        ambiguities=(AmbiguityCode.MULTIPLE_EVIDENCE_PATHS,),
        reason_code=ReasonCode.CLARIFICATION_REQUIRED,
    )
    assert candidate.missing_fields == (MissingField.EQUIPMENT_ID,)


def test_route_decision_validates_action_source_retry_and_fallback_alignment() -> None:
    context = ExtractedContext(
        equipment_id="AOI-WAFER-01", time_preset=TimePreset.TODAY
    )
    decision = RouteDecision(
        intent=RouteIntent.PRODUCTION_SUMMARY,
        resolved_context=context,
        decision_source=DecisionSource.DETERMINISTIC_GATE,
        reason_code=ReasonCode.PRODUCTION_REQUEST,
        safe_action=SafeAction.EXECUTE_PRODUCTION_SUMMARY,
    )
    assert decision.retry_count == 0
    assert decision.fallback_state is FallbackState.NOT_USED

    with pytest.raises(ValidationError, match="safe action"):
        RouteDecision(
            intent=RouteIntent.PRODUCTION_SUMMARY,
            resolved_context=context,
            decision_source=DecisionSource.DETERMINISTIC_GATE,
            reason_code=ReasonCode.PRODUCTION_REQUEST,
            safe_action=SafeAction.ANSWER_GENERAL,
        )

    with pytest.raises(ValidationError, match="at most one"):
        RouteDecision(
            intent=RouteIntent.GENERAL,
            resolved_context=ExtractedContext(),
            decision_source=DecisionSource.CLASSIFIER,
            reason_code=ReasonCode.GENERAL_REQUEST,
            retry_count=2,
            safe_action=SafeAction.ANSWER_GENERAL,
        )

    with pytest.raises(ValidationError, match="fallback"):
        RouteDecision(
            intent=RouteIntent.GENERAL,
            resolved_context=ExtractedContext(),
            decision_source=DecisionSource.CLASSIFIER,
            reason_code=ReasonCode.GENERAL_REQUEST,
            fallback_state=FallbackState.USED,
            safe_action=SafeAction.ANSWER_GENERAL,
        )


@pytest.mark.parametrize(
    "question",
    (
        "Show yield and equipment status from the documents.",
        "Show yield and equipment status.",
    ),
)
def test_deterministic_gate_clarifies_multiple_manufacturing_intents(
    question: str,
) -> None:
    decision = deterministic_gate(
        question,
        saved_context=ExtractedContext(
            equipment_id="AOI-WAFER-01",
            time_preset=TimePreset.TODAY,
            document_query="status procedure",
        ),
    )

    assert decision is not None
    assert decision.intent is RouteIntent.CLARIFICATION
    assert decision.safe_action is SafeAction.REQUEST_CLARIFICATION


def test_deterministic_gate_handles_high_confidence_english_routes() -> None:
    context = ExtractedContext(
        equipment_id="AOI-WAFER-01", time_preset=TimePreset.TODAY
    )

    cases = (
        ("Hello, what can you do?", RouteIntent.GENERAL),
        (
            "Show the production summary for AOI-WAFER-01 today.",
            RouteIntent.PRODUCTION_SUMMARY,
        ),
        (
            "What is the equipment status for AOI-WAFER-01 today?",
            RouteIntent.EQUIPMENT_STATUS,
        ),
        (
            "Show the defect distribution for AOI-WAFER-01 today.",
            RouteIntent.DEFECT_DISTRIBUTION,
        ),
        (
            "Find the operator SOP for optical signal alarms.",
            RouteIntent.DOCUMENT_SEARCH,
        ),
        (
            "Show today's yield and find the manual for optical signal alarms.",
            RouteIntent.COMBINED,
        ),
        ("Use our private live production records.", RouteIntent.UNSUPPORTED),
    )

    for question, expected_intent in cases:
        decision = deterministic_gate(question, current_context=context)
        assert decision is not None
        assert decision.intent is expected_intent
        assert decision.decision_source is DecisionSource.DETERMINISTIC_GATE

    clarification = deterministic_gate("Show today's yield.")
    assert clarification is not None
    assert clarification.intent is RouteIntent.CLARIFICATION


def test_deterministic_gate_handles_high_confidence_traditional_chinese_routes(
) -> None:
    context = ExtractedContext(
        equipment_id="AOI-WAFER-01", time_preset=TimePreset.TODAY
    )

    cases = (
        ("你好，你可以做什麼？", RouteIntent.GENERAL),
        ("請查詢 AOI-WAFER-01 今天的生產摘要。", RouteIntent.PRODUCTION_SUMMARY),
        ("請查詢 AOI-WAFER-01 今天的設備狀態。", RouteIntent.EQUIPMENT_STATUS),
        ("請顯示 AOI-WAFER-01 今天的缺陷分布。", RouteIntent.DEFECT_DISTRIBUTION),
        ("請搜尋光學訊號警報的操作手冊。", RouteIntent.DOCUMENT_SEARCH),
        ("請查詢今天的良率，並搜尋光學訊號警報指南。", RouteIntent.COMBINED),
        ("請使用我們的即時私人製程資料。", RouteIntent.UNSUPPORTED),
    )

    for question, expected_intent in cases:
        decision = deterministic_gate(question, current_context=context)
        assert decision is not None
        assert decision.intent is expected_intent

    clarification = deterministic_gate("請顯示今天的良率。")
    assert clarification is not None
    assert clarification.intent is RouteIntent.CLARIFICATION


@pytest.mark.parametrize(
    "question",
    (
        "Can you analyze the manufacturing data?",
        "What happened on the line?",
        "可以幫我分析資料嗎？",
        "產線發生了什麼事？",
    ),
)
def test_deterministic_gate_defers_ambiguous_evidence_seeking_requests(
    question: str,
) -> None:
    assert deterministic_gate(question) is None


def test_fixture_is_bilingual_machine_readable_and_exercises_the_gate() -> None:
    scenarios = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert isinstance(scenarios, list)
    assert len(scenarios) >= 30
    assert {scenario["language"] for scenario in scenarios} >= {"en", "zh-TW"}
    assert {scenario["expected_intent"] for scenario in scenarios} >= {
        intent.value for intent in RouteIntent
    }

    required_fields = {
        "id",
        "language",
        "question",
        "category",
        "expected_intent",
        "expected_gate",
    }
    for scenario in scenarios:
        assert required_fields <= scenario.keys()
        assert scenario["expected_gate"] in {
            *[intent.value for intent in RouteIntent],
            None,
        }
        decision = deterministic_gate(
            scenario["question"],
            current_context=_context(scenario.get("current_context")),
            saved_context=_context(scenario.get("saved_context")),
        )
        if scenario["expected_gate"] is None:
            assert decision is None, scenario["id"]
            continue
        assert decision is not None, scenario["id"]
        assert decision.intent.value == scenario["expected_gate"]
        expected_context = scenario.get("expected_resolved_context")
        if expected_context is not None:
            resolved = decision.resolved_context
            for field, expected_value in expected_context.items():
                assert getattr(resolved, field) == expected_value, scenario["id"]


def test_fixture_categories_cover_context_follow_up_safety_and_failure_cases() -> None:
    scenarios = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    categories = {scenario["category"] for scenario in scenarios}

    assert {
        "explicit",
        "context_precedence",
        "context_missing",
        "follow_up",
        "combined",
        "safety",
        "failure_ambiguous",
        "failure_classifier_boundary",
    } <= categories
