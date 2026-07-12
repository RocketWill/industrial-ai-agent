from typing import Literal

SafeGraphErrorCode = Literal[
    "conversation_not_found",
    "assistant_unavailable",
    "empty_response",
    "persistence_failed",
]


class GraphExecutionError(Exception):
    def __init__(self, *, code: str) -> None:
        allowed_codes = {
            "conversation_not_found",
            "assistant_unavailable",
            "empty_response",
            "persistence_failed",
        }
        if code not in allowed_codes:
            raise ValueError("Graph errors must use a safe public code")
        self.code = code
        super().__init__(code)


class GraphConfigurationError(GraphExecutionError):
    def __init__(self) -> None:
        super().__init__(code="assistant_unavailable")
