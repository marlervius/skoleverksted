"""Deterministic structural checks for generated compendium text.

These checks intentionally do not try to replace a language model or a
teacher.  They catch damage that is unsafe to pass on as normal prose:
truncation, empty headings, placeholder-like fragments and broken sentences.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TextQualityIssue:
    code: str
    message: str


_LEADING_FRAGMENT_RE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:særlig\s+ble|blant disse var|eksempler er|årsaken var|blant annet)\b\s*(?:[.!?…]|$|en\b|et\b|den\b|det\b|de\b)"
)
_EMPTY_PREDICATE_RE = re.compile(
    r"(?i)\b(?:særlig|blant disse var|eksempler er|årsaken var|var|ble|er|som)\s+(?:ble|var|er)?\s*\."
)
_SOURCE_FRAGMENT_RE = re.compile(r"(?i)\b(?:var|ble|er)\s+\(Kilde:")
_TRAILING_CONNECTOR_RE = re.compile(
    r"(?i)(?:\b(?:særlig|blant disse var|eksempler er|årsaken var|fordi|som|og|eller)\s*)$"
)


def _headings_have_content(text: str) -> bool:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        heading = re.match(r"^\s{0,3}(#{1,6})\s+\S", line)
        if not heading:
            continue
        level = len(heading.group(1))
        for following in lines[index + 1 :]:
            stripped = following.strip()
            if not stripped:
                continue
            child_heading = re.match(r"^\s{0,3}(#{1,6})\s+\S", following)
            if child_heading:
                # A document title may be followed directly by its first
                # subsection. That subsection is content for the title; only
                # a sibling/parent heading with no intervening content is
                # genuinely empty.
                if len(child_heading.group(1)) <= level:
                    return False
                break
            break
        else:
            return False
    return True


def inspect_markdown(text: str, *, min_words: int = 120) -> list[TextQualityIssue]:
    """Return structural issues in Markdown prose, in deterministic order."""
    value = str(text or "").strip()
    issues: list[TextQualityIssue] = []

    def add(code: str, message: str) -> None:
        if not any(item.code == code for item in issues):
            issues.append(TextQualityIssue(code, message))

    if not value:
        add("empty_content", "Kapittelteksten er tom.")
        return issues
    word_count = len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ]{2,}\b", value, flags=re.UNICODE))
    if word_count < min_words:
        add("content_too_short", f"Kapittelteksten har bare {word_count} ord; minst {min_words} forventes.")
    if re.search(r"<\/?(?:br|p|div)\b", value, flags=re.IGNORECASE):
        add("html_markup", "Kapittelteksten inneholder HTML-markup som ikke skal følge med i Markdown.")
    if value.endswith(("...", "…")):
        add("possible_truncation", "Kapittelteksten slutter med en avkortingsmarkør.")
    if not _headings_have_content(value):
        add("empty_heading", "Minst én overskrift mangler innhold.")
    if _LEADING_FRAGMENT_RE.search(value):
        add("sentence_fragment", "Teksten inneholder en innledende setningsfragment-konstruksjon.")
    if _EMPTY_PREDICATE_RE.search(value):
        add("missing_subject", "Teksten inneholder et tomt predikat eller manglende subjekt.")
    if _SOURCE_FRAGMENT_RE.search(value):
        add("source_fragment", "En kildehenvisning følger et ufullstendig predikat.")
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if lines and _TRAILING_CONNECTOR_RE.search(re.sub(r"\s+", " ", lines[-1].rstrip("*_- "))):
        add("trailing_fragment", "Siste tekstlinje slutter med en ufullstendig innledning.")
    return issues
