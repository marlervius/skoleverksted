"""
Normalize agent text before LaTeX compilation.

Fixes Unicode hyphen variants that render as wrong glyphs in some fonts,
and strips markdown leakage from LLM output.
"""

from __future__ import annotations

import re
import unicodedata

# Non-standard hyphens / invisible chars that often become wrong glyphs in PDF.
CHAR_MAP: dict[str, str] = {
    "\u00ad": "",       # soft hyphen
    "\u2010": "-",      # hyphen
    "\u2011": "-",      # non-breaking hyphen
    "\u2012": "\u2013", # figure dash → en-dash
    "\u2043": "-",      # hyphen bullet
    "\ufeff": "",       # BOM
    "\u200b": "",       # zero-width space
    "\u200c": "",       # zero-width non-joiner
    "\u200d": "",       # zero-width joiner
    "\u2060": "",       # word joiner
}

# Protect LaTeX math and commands from markdown stripping.
_PLACEHOLDER_PREFIX = "\x00MMTX"
_MATH_RE = re.compile(
    r"(\$\$[\s\S]*?\$\$|\$[^$\n]+\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\))"
)
_CMD_RE = re.compile(r"(\\[a-zA-Z@]+(?:\[[^\]]*\])?(?:\{[^{}]*\})*)")


def normalize_text(text: str) -> str:
    """Unicode NFC + map problematic hyphen / invisible characters."""
    if not text:
        return text
    s = unicodedata.normalize("NFC", text)
    for bad, good in CHAR_MAP.items():
        s = s.replace(bad, good)
    return s


def strip_markdown(text: str) -> str:
    """Remove common markdown artifacts outside LaTeX math/commands."""
    if not text:
        return text

    placeholders: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        placeholders.append(match.group(0))
        return f"{_PLACEHOLDER_PREFIX}{len(placeholders) - 1}\x00"

    protected = _MATH_RE.sub(_stash, text)
    protected = _CMD_RE.sub(_stash, protected)

    protected = re.sub(r"\*{1,3}", "", protected)
    protected = re.sub(r"^#{1,6}\s*", "", protected, flags=re.M)
    protected = protected.replace("`", "")

    for idx, original in enumerate(placeholders):
        protected = protected.replace(f"{_PLACEHOLDER_PREFIX}{idx}\x00", original)

    return protected


def sanitize_latex_body(text: str) -> str:
    """Full pipeline: normalize Unicode, then strip markdown outside math."""
    return strip_markdown(normalize_text(text))
