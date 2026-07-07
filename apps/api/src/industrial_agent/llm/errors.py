class LLMError(Exception):
    pass


class LLMConfigurationError(LLMError):
    pass


class LLMConnectionError(LLMError):
    pass


class LLMServiceError(LLMError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"LLM service returned HTTP {status_code}")


class LLMResponseError(LLMError):
    pass
