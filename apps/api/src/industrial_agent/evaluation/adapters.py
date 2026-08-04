"""Closed deterministic adapters for formal offline evaluation."""

from industrial_agent.evaluation.models import AdapterAction, AdapterScript
from industrial_agent.llm.errors import LLMConnectionError
from industrial_agent.llm.types import CompletionResult, ToolCall


class DeterministicClassifierAdapter:
    """Interpret only the approved classifier actions in one scenario script."""

    def __init__(self, script: AdapterScript) -> None:
        self._script = script
        self._attempt = 0

    def complete_with_tools(self, *args: object, **kwargs: object) -> CompletionResult:
        attempt = self._attempt
        self._attempt += 1
        actions = set(self._script.actions)
        if AdapterAction.EXHAUST_CLASSIFIER_RETRY in actions:
            raise LLMConnectionError("deterministic classifier failure")
        if (
            AdapterAction.TRANSIENT_CLASSIFIER_FAILURE in actions
            and attempt == 0
        ):
            raise LLMConnectionError("deterministic transient classifier failure")
        if (
            AdapterAction.RETURN_ROUTE in actions
            and self._script.candidate is not None
        ):
            return CompletionResult(
                content=None,
                tool_calls=(
                    ToolCall(
                        call_id="evaluation-route",
                        name="classify_request",
                        arguments=self._script.candidate.model_dump(mode="json"),
                    ),
                ),
            )
        raise AssertionError("adapter script has no classifier outcome")
