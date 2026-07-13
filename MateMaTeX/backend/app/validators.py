"""Shared request validation helpers."""

from __future__ import annotations

from fastapi import HTTPException

from app.config import get_settings


def ensure_latex_size(content: str, *, field_name: str = "latex_content") -> None:
    limit = get_settings().max_latex_chars
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"{field_name} exceeds maximum size ({limit} characters)",
        )
