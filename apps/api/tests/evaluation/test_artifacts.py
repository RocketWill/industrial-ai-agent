import json
from datetime import UTC, datetime
from pathlib import Path

from industrial_agent.evaluation.artifacts import (
    EvaluationArtifact,
    digest_evaluation_fixture,
    write_evaluation_artifact,
)
from industrial_agent.evaluation.models import EvaluationDimension
from industrial_agent.evaluation.results import (
    DimensionAssertion,
    ScenarioResult,
    aggregate_results,
)


def test_write_evaluation_artifact_uses_versioned_stable_json(tmp_path: Path) -> None:
    result = ScenarioResult(
        scenario_id="en-general-greeting",
        passed=True,
        assertions=(
            DimensionAssertion(
                dimension=EvaluationDimension.ROUTE_ACCURACY,
                expected="general",
                observed="general",
                passed=True,
                reason="route matched",
            ),
        ),
        stages=(),
    )
    artifact = EvaluationArtifact(
        schema_version="1",
        suite_id="formal-v1",
        fixture_digest="a" * 64,
        runner_version="0.1.0",
        started_at=datetime(2026, 8, 10, 1, tzinfo=UTC),
        completed_at=datetime(2026, 8, 10, 1, 0, 1, tzinfo=UTC),
        scenario_filter=None,
        partial=False,
        results=(result,),
        summary=aggregate_results((result,)),
        overall_passed=True,
        suite_failures=(),
    )
    output = tmp_path / "evaluation.json"

    write_evaluation_artifact(artifact, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "1"
    assert payload["results"][0]["scenario_id"] == "en-general-greeting"
    assert payload["summary"]["dimensions"][0]["dimension"] == "route_accuracy"
    assert str(tmp_path) not in output.read_text(encoding="utf-8")


def test_digest_evaluation_fixture_hashes_exact_file_bytes(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_bytes(b"{}")

    assert digest_evaluation_fixture(fixture) == (
        "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    )
