import json
import subprocess
import sys
from pathlib import Path

from industrial_agent.evaluation import cli
from industrial_agent.evaluation.results import (
    DimensionAssertion,
    EvaluationRun,
    ExecutionTrace,
    ScenarioResult,
    StageObservation,
    aggregate_results,
)


def test_cli_runs_one_scenario_and_writes_a_partial_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "nested" / "evaluation.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "industrial_agent.evaluation.cli",
            "--scenario",
            "alarm-optical",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["partial"] is True
    assert artifact["scenario_filter"] == "alarm-optical"
    assert artifact["overall_passed"] is True
    assert "retrieval_top_1: 1/1 passed" in completed.stdout


def test_cli_returns_usage_error_for_unknown_scenario(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "industrial_agent.evaluation.cli",
            "--scenario",
            "does-not-exist",
            "--output",
            str(tmp_path / "evaluation.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "Unknown scenario: does-not-exist" in completed.stderr


def test_cli_help_is_available() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "industrial_agent.evaluation.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "--scenario" in completed.stdout
    assert "--output" in completed.stdout


def test_cli_returns_usage_error_when_output_is_a_directory(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "industrial_agent.evaluation.cli",
            "--scenario",
            "alarm-optical",
            "--output",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2


def test_cli_returns_one_when_a_completed_run_misses_a_threshold(
    monkeypatch,
    tmp_path: Path,
) -> None:
    failed = ScenarioResult(
        scenario_id="forced-threshold-failure",
        passed=False,
        trace=ExecutionTrace(),
        assertions=(
            DimensionAssertion(
                dimension="route_accuracy",
                expected="general",
                observed="unsupported",
                passed=False,
                reason="forced test failure",
            ),
        ),
        stages=(StageObservation(name="total", elapsed_ms=0),),
    )
    results = (failed,)
    monkeypatch.setattr(
        cli,
        "run_suite",
        lambda suite, scenario_id=None: EvaluationRun(
            partial=False,
            results=results,
            summary=aggregate_results(results),
        ),
    )

    exit_code = cli.main(["--output", str(tmp_path / "failed.json")])

    assert exit_code == 1
