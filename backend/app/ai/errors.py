"""Controlled errors for the LLM orchestration layer."""


class LlmError(Exception):
    """Configuration, provider, or orchestration failure mapped to HTTP."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class DispatchError(Exception):
    """Invalid model tool request. Nothing is executed."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
