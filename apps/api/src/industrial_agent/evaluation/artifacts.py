"""Versioned machine-readable evaluation artifacts."""

from datetime import datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from pydantic import Field, model_validator

from industrial_agent.evaluation.models import EvaluationModel
from industrial_agent.evaluation.results import EvaluationSummary, ScenarioResult

DEFAULT_ARTIFACT_PATH = Path(".artifacts/evaluation/latest.json")


def digest_evaluation_fixture(path: Path) -> str:
    """Return the SHA-256 digest of the fixture's exact tracked bytes."""
    return sha256(path.read_bytes()).hexdigest()


class EvaluationArtifact(EvaluationModel):
    """Complete formal or filtered evaluation run artifact."""

    schema_version: Literal["1"]
    suite_id: str
    fixture_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    runner_version: str
    started_at: datetime
    completed_at: datetime
    scenario_filter: str | None
    partial: bool
    results: tuple[ScenarioResult, ...]
    summary: EvaluationSummary
    overall_passed: bool
    suite_failures: tuple[str, ...]

    @model_validator(mode="after")
    def validate_run_state(self) -> "EvaluationArtifact":
        if self.started_at.utcoffset() is None or self.completed_at.utcoffset() is None:
            raise ValueError("artifact timestamps must use UTC")
        if self.started_at.utcoffset().total_seconds() != 0:
            raise ValueError("artifact timestamps must use UTC")
        if self.completed_at.utcoffset().total_seconds() != 0:
            raise ValueError("artifact timestamps must use UTC")
        if self.completed_at < self.started_at:
            raise ValueError("artifact completion must not precede start")
        if self.overall_passed != self.summary.overall_passed:
            raise ValueError("artifact pass state must match summary")
        return self


def write_evaluation_artifact(
    artifact: EvaluationArtifact,
    output_path: Path = DEFAULT_ARTIFACT_PATH,
) -> None:
    """Atomically write one artifact to an explicit file target."""
    if output_path.exists() and output_path.is_dir():
        raise IsADirectoryError(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = artifact.model_dump_json(indent=2) + "\n"
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        delete=False,
    ) as temporary:
        temporary.write(payload)
        temporary_path = Path(temporary.name)
    temporary_path.replace(output_path)
