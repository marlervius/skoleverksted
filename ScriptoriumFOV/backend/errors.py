"""Domain exceptions with safe, user-visible messages (Norwegian)."""


class GeminiQuotaExceededError(RuntimeError):
    """
    Raised when Google Gemini returns 429 / RESOURCE_EXHAUSTED or quota errors.

    `user_message` is shown in the API progress / UI; `technical_detail` is for logging & backoff.
    """

    def __init__(self, user_message: str, *, technical_detail: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        self.technical_detail = technical_detail or str(self)
