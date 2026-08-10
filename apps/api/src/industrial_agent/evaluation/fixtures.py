"""Load and validate versioned deterministic evaluation fixtures."""

from pathlib import Path

from industrial_agent.evaluation.models import EvaluationSuite

FORMAL_SUITE_PATH = Path(__file__).with_name("fixtures") / "v1.json"


def load_evaluation_suite(path: Path) -> EvaluationSuite:
    """Load one UTF-8 JSON suite through the strict public fixture contract."""
    return EvaluationSuite.model_validate_json(path.read_text(encoding="utf-8"))


def load_formal_evaluation_suite() -> EvaluationSuite:
    """Load the package-owned formal deterministic evaluation suite."""
    return load_evaluation_suite(FORMAL_SUITE_PATH)
