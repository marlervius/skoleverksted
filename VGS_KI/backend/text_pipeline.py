"""Deterministic text hygiene for the agent→Typst pipeline.

Implements DEL 1 of SPEC_laeringsark_redesign:

1.1  Unicode normalisation (stray hyphen variants → plain hyphen) so the
     font never has to render a glyph it lacks ("Østerrike1Ungarn"-bug).
1.2  Markdown stripper as a safety net on plain-text fields.
1.3  Deterministic English-leak detection after the proofreading agent.
1.4  Emoji removal (emoji glyphs collapse to arbitrary fallback glyphs in
     the PDF font and are banned from Typst input).
1.5  PDF lint: last gate before delivery, run on both the Typst input and
     the text extracted from the compiled PDF.

DEL 3: `typst_escape()` for interpolating agent text into Typst markup.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata

logger = logging.getLogger(__name__)


# ── 1.1 Unicode normalisation ─────────────────────────────────────────────────

CHAR_MAP = {
    "\u00ad": "",       # soft hyphen -> remove
    "\u2010": "-",      # hyphen
    "\u2011": "-",      # non-breaking hyphen
    "\u2012": "\u2013",  # figure dash -> en-dash
    "\u2043": "-",      # hyphen bullet
    "\ufeff": "",       # BOM
    "\u200b": "",       # zero-width space
    "\u200c": "",       # zero-width non-joiner
    "\u200d": "",       # zero-width joiner
    "\u00a0": " ",      # no-break space -> normal space
    "\u202f": " ",      # narrow no-break space
}


def normalize_text(s: str) -> str:
    """NFC-normalise and replace hyphen/space variants the PDF font may lack."""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    for bad, good in CHAR_MAP.items():
        s = s.replace(bad, good)
    return s


# ── 1.4 Emoji removal ─────────────────────────────────────────────────────────

# Codepoints that ARE allowed even though they sit inside the stripped blocks.
# The template font must cover these (★ ☆ ✓); → is outside the blocks.
_EMOJI_EXCEPTIONS = {0x2605, 0x2606, 0x2192, 0x2713}

# Emoji blocks per spec: U+1F300–U+1FAFF and U+2600–U+27BF (minus exceptions),
# plus variation selector-16 / zero-width-joiner sequences and a few strays
# commonly emitted by LLMs (☑, ✅ live in the ranges already).
_EXTRA_EMOJI = {
    0x2B50,   # ⭐
    0x2B55,   # ⭕
    0x203C,   # ‼
    0x2049,   # ⁉
    0xFE0F,   # variation selector-16
    0x20E3,   # combining enclosing keycap
    0x1F004,  # 🀄
    0x1F0CF,  # 🃏
}


def _is_emoji_codepoint(cp: int) -> bool:
    if cp in _EMOJI_EXCEPTIONS:
        return False
    if 0x1F300 <= cp <= 0x1FAFF:
        return True
    if 0x2600 <= cp <= 0x27BF:
        return True
    if 0x1F000 <= cp <= 0x1F2FF:  # mahjong/dominoes/enclosed ideographs
        return True
    return cp in _EXTRA_EMOJI


def strip_emoji(s: str) -> str:
    """Remove all emoji codepoints (keeping ★ ☆ → ✓ which the font covers)."""
    if not s:
        return ""
    return "".join(ch for ch in s if not _is_emoji_codepoint(ord(ch)))


def find_emoji(s: str) -> list[str]:
    """Return emoji characters present in the string (for linting)."""
    return [ch for ch in (s or "") if _is_emoji_codepoint(ord(ch))]


# ── 1.2 Markdown stripper ─────────────────────────────────────────────────────

def strip_markdown(s: str) -> str:
    """Safety net: remove markdown bold/italic markers, headings and backticks.

    Used on STRUCTURED text fields (JSON data contract) that must be plain
    prose — never on text that still needs markdown→Typst conversion.
    """
    if not s:
        return ""
    s = re.sub(r"\*{1,3}", "", s)            # ** and *
    s = re.sub(r"^#{1,6}\s*", "", s, flags=re.M)
    s = s.replace("`", "")
    return s


# ── 1.3 English-leak detection ────────────────────────────────────────────────

ENGLISH_TOKENS = {
    "the", "is", "and", "to", "of", "with", "these", "this",
    "in", "that", "for", "are", "was", "has",
}

# Tokens that are also common Norwegian words and must never be flagged.
# ("for", "i", "at", "to" are Norwegian; "to" = the number two.)
_NORWEGIAN_HOMOGRAPHS = {"for", "to", "in", "is"}
# "in"/"is" are rare standalone in Norwegian prose but appear in fixed
# expressions; we keep "for"/"to" out and flag the rest only as whole words.
_EFFECTIVE_TOKENS = ENGLISH_TOKENS - {"for", "to"}


def find_english_leaks(s: str, whitelist: tuple[str, ...] | list[str] = ()) -> list[str]:
    """Return English filler words found outside whitelisted phrases.

    `whitelist`: phrases that may legitimately contain English (quoted work
    titles such as *The Sleepwalkers* from `verk` fields in the JSON).
    """
    if not s:
        return []
    text = s
    for phrase in whitelist:
        if phrase:
            text = text.replace(phrase, " ")
    words = re.findall(r"[a-zA-Z]+", text)
    return [w for w in words if w.lower() in _EFFECTIVE_TOKENS]


# ── DEL 3: Typst escaping ─────────────────────────────────────────────────────

_TYPST_ESCAPES = [
    ("\\", "\\\\"),  # backslash first
    ("#", "\\#"),
    ("$", "\\$"),
    ("@", "\\@"),
    ("[", "\\["),
    ("]", "\\]"),
    ("<", "\\<"),
    (">", "\\>"),
    ("_", "\\_"),
    ("*", "\\*"),
    ("`", "\\`"),
    ("{", "\\{"),
    ("}", "\\}"),
]


def typst_escape(s: str) -> str:
    """Escape Typst special characters in agent text before interpolation.

    Without this an LLM-generated `#` or `$` breaks compilation sporadically.
    Also normalises unicode and strips emoji so no raw field can reintroduce
    the P0 bugs.
    """
    if not s:
        return ""
    s = strip_emoji(normalize_text(s))
    for char, escaped in _TYPST_ESCAPES:
        s = s.replace(char, escaped)
    # Line-leading markup markers (- list, + enum, / term list, = heading)
    # would otherwise be interpreted as Typst markup.
    s = re.sub(r"(?m)^(\s*)([-+/=])", r"\1\\\2", s)
    return s


def clean_field(s: str) -> str:
    """Full hygiene for a structured JSON text field: normalise, strip
    markdown and emoji, collapse whitespace. (Escaping happens separately.)"""
    if not s:
        return ""
    s = strip_markdown(strip_emoji(normalize_text(s)))
    return re.sub(r"[ \t]+", " ", s).strip()


# ── 1.5 PDF lint ──────────────────────────────────────────────────────────────

# letter-digit-letter with 1/8 catches the hyphen bug directly
# ("Østerrike1Ungarn", "fransk1tyske"). Case-insensitive so compound names
# with a capital after the stray digit are caught too.
_HYPHEN_BUG_RE = re.compile(r"[a-zæøå][18][a-zæøå]", re.IGNORECASE)

MIN_PAGE_CHARS = 120


def _pdftotext_pages(pdf_bytes: bytes) -> list[str] | None:
    """Extract per-page text via the pdftotext CLI; None if unavailable."""
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    tmp = tempfile.mkdtemp(prefix="pdflint_")
    pdf_path = os.path.join(tmp, "doc.pdf")
    txt_path = os.path.join(tmp, "doc.txt")
    try:
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        result = subprocess.run(
            [exe, "-enc", "UTF-8", pdf_path, txt_path],
            capture_output=True, timeout=30,
        )
        if result.returncode != 0 or not os.path.exists(txt_path):
            return None
        with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
            full = f.read()
        # pdftotext separates pages with form feed
        return full.split("\f")
    except Exception as e:  # pragma: no cover - environment-specific
        logger.warning(f"pdftotext extraction failed: {e}")
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _pypdf_pages(pdf_bytes: bytes) -> list[str] | None:
    """Fallback extraction with pypdf when pdftotext is not installed."""
    try:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        return [(page.extract_text() or "") for page in reader.pages]
    except Exception as e:  # pragma: no cover - optional dependency
        logger.warning(f"pypdf extraction failed: {e}")
        return None


def extract_pdf_pages(pdf_bytes: bytes) -> list[str] | None:
    """Per-page plain text of a PDF, or None if no extractor is available."""
    return _pdftotext_pages(pdf_bytes) or _pypdf_pages(pdf_bytes)


def lint_text(s: str, whitelist: tuple[str, ...] | list[str] = ()) -> list[str]:
    """Lint a text blob per spec 1.5. Returns a list of human-readable issues."""
    issues: list[str] = []
    if not s:
        return issues

    if "**" in s:
        issues.append("markdown-rester: '**' i tekst")
    if "`" in s:
        issues.append("markdown-rester: backtick i tekst")
    if re.search(r"^#{2,6}\s", s, flags=re.M):
        issues.append("markdown-rester: '##'-overskrift i tekst")

    leaks = find_english_leaks(s, whitelist)
    if leaks:
        uniq = sorted({w.lower() for w in leaks})
        issues.append(f"engelske ord utenfor whitelist: {', '.join(uniq[:8])}")

    emoji = find_emoji(s)
    if emoji:
        issues.append(f"emoji i tekst: {' '.join(sorted(set(emoji))[:8])}")

    if s.count("«") != s.count("»"):
        issues.append(f"ubalanserte «»: {s.count('«')} åpne / {s.count('»')} lukkede")
    # MCQ/enum markers like "a)" / "1)" are legitimate lone closing parens.
    paren_text = re.sub(r"(?:^|(?<=\s))[a-d0-9]\)", "", s, flags=re.IGNORECASE | re.M)
    if paren_text.count("(") != paren_text.count(")"):
        issues.append(
            f"ubalanserte parenteser: {paren_text.count('(')} åpne / {paren_text.count(')')} lukkede")

    m = _HYPHEN_BUG_RE.search(s)
    if m:
        issues.append(f"bindestrek-bug-mønster funnet: '{m.group(0)}'")

    return issues


def lint_pdf(pdf_bytes: bytes, whitelist: tuple[str, ...] | list[str] = ()) -> list[str]:
    """Lint a compiled PDF (spec 1.5). Returns a list of issues; empty = OK."""
    pages = extract_pdf_pages(pdf_bytes)
    if pages is None:
        logger.warning("PDF lint skipped: no text extractor available (pdftotext/pypdf)")
        return []

    issues = lint_text("\f".join(pages), whitelist)

    # Orphan pages: any page with under MIN_PAGE_CHARS of actual text.
    for i, page in enumerate(pages, 1):
        stripped = re.sub(r"\s+", "", page)
        # Skip a trailing blank artifact page from extraction
        if i == len(pages) and not stripped:
            continue
        if len(stripped) < MIN_PAGE_CHARS:
            issues.append(f"side {i} har under {MIN_PAGE_CHARS} tegn tekst (foreldreløs side)")

    return issues
