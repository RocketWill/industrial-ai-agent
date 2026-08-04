from industrial_agent.evaluation.fixtures import load_formal_evaluation_suite
from industrial_agent.evaluation.models import EvaluationSuite
from industrial_agent.evaluation.runner import EvaluationRunError, run_suite


def test_run_suite_filters_one_scenario_and_marks_partial() -> None:
    suite = load_formal_evaluation_suite()

    run = run_suite(suite, scenario_id="alarm-optical")

    assert run.partial is True
    assert [result.scenario_id for result in run.results] == ["alarm-optical"]
    assert run.summary.overall_passed is True


def test_run_suite_rejects_an_unknown_scenario_filter() -> None:
    suite = load_formal_evaluation_suite()

    try:
        run_suite(suite, scenario_id="does-not-exist")
    except EvaluationRunError as error:
        assert str(error) == "Unknown scenario: does-not-exist"
    else:
        raise AssertionError("missing scenario filter should fail")


def test_run_suite_continues_after_an_unexpected_scenario_failure(
    monkeypatch,
) -> None:
    suite = load_formal_evaluation_suite()
    selected = EvaluationSuite(
        schema_version="1",
        suite_id="failure-isolation",
        scenarios=suite.scenarios[:2],
    )
    real_run_scenario = __import__(
        "industrial_agent.evaluation.runner", fromlist=["run_scenario"]
    ).run_scenario

    def fail_first(scenario):
        if scenario.id == selected.scenarios[0].id:
            raise RuntimeError("private detail must not enter the artifact")
        return real_run_scenario(scenario)

    monkeypatch.setattr(
        "industrial_agent.evaluation.runner.run_scenario", fail_first
    )

    run = run_suite(selected)

    assert len(run.results) == 2
    assert run.results[0].failure == "Scenario execution failed."
    assert "private detail" not in run.results[0].model_dump_json()
    assert run.results[1].passed is True
    assert run.summary.overall_passed is False
