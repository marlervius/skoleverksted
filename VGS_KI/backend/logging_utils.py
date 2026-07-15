from __future__ import annotations

import logging


class RequestLogger(logging.LoggerAdapter):
    """Logger adapter that injects request_id into every log record."""

    def process(self, msg, kwargs):
        kwargs.setdefault("extra", {})["request_id"] = self.extra.get("request_id", "-")
        return msg, kwargs
