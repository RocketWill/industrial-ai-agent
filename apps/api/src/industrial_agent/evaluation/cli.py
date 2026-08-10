"""Command-line entry point for deterministic formal evaluation."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from industrial_agent.evaluation.artifacts import (
    DEFAULT_ARTIFACT_PATH,
    EvaluationArtifact,
    digest_evaluation_fixture,
    write_evaluation_artifact,
)
from industrial_agent.evaluation.fixtures import (
    FORMAL_SUITE_PATH,
    load_formal_evaluation_suite,
)
from industrial_agent.evaluation.runner import EvaluationRunError, run_suite

RUNNER_VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the deterministic Industrial AI Agent evaluation suite."
    )
    parser.add_argument("--scenario", help="Run one scenario ID only.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ARTIFACT_PATH,
        help="Artifact JSON path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    started_at = datetime.now(UTC)
    try:
        suite = load_formal_evaluation_suite()
        run = run_suite(suite, scenario_id=args.scenario)
        artifact = EvaluationArtifact(
            schema_version="1",
            suite_id=suite.suite_id,
            fixture_digest=digest_evaluation_fixture(FORMAL_SUITE_PATH),
            runner_version=RUNNER_VERSION,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            scenario_filter=run.scenario_filter,
            partial=run.partial,
            results=run.results,
            summary=run.summary,
            overall_passed=run.summary.overall_passed,
            suite_failures=run.suite_failures,
        )
        write_evaluation_artifact(artifact, args.output)
    except (EvaluationRunError, OSError, ValueError) as error:
        parser.error(str(error))
    for dimension in run.summary.dimensions:
        print(
            f"{dimension.dimension.value}: "
            f"{dimension.passed}/{dimension.total} passed"
        )
    print(f"artifact: {args.output}")
    return 0 if run.summary.overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
