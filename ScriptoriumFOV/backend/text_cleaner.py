"""
Text cleaning and sanitization utilities for Typst PDF generation.

All functions that clean AI output artefacts, sanitize text for Typst,
or format content for rendering live here.
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# AI artefact removal
# ---------------------------------------------------------------------------


def clean_ai_artifacts(text: str) -> str:
    """Remove AI thinking/reasoning artifacts from generated text."""
    if not text:
        return ""

    text = re.sub(r"^(Her er|Jeg har laget|Her kommer)[^.:\n]*[:\n]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Wait,?\s+I\s+need\s+to[^.]*\.", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Let me\s+(think|check|verify|make sure)[^.]*\.", "", text, flags=re.IGNORECASE)
    text = re.sub(r"I (need|should|must) to[^.]*\.", "", text, flags=re.IGNORECASE)
    text = re.sub(r"«[^»]*»", "", text)
    text = re.sub(r"Thought:\s*[^\n]*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Action:\s*[^\n]*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Action Input:\s*[^\n]*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Observation:\s*[^\n]*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Final Answer:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"I\s+followed\s+the\s+exact\s+prompt[^.]*\.", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[_\-]{1,3}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\-_\*]{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)

    return text.strip()


def clean_section_header(text: str) -> str:
    """Remove duplicate/internal headers and Bloom's taxonomy labels from section content."""
    if not text:
        return ""

    header_keywords = [
        "LESEFORSTÅELSE", "Leseforståelse",
        "VIKTIGE BEGREPER", "Viktige begreper",
        "DISKUSJON", "Diskusjon",
        "KULTURBLIKK", "Kulturblikk",
        "OPPGAVER", "Oppgaver",
        "BEGREPER", "Begreper",
        "ORDLISTE", "Ordliste",
        "READING COMPREHENSION", "Reading Comprehension",
        "KEY VOCABULARY", "Key Vocabulary",
        "DISCUSSION", "Discussion",
        "CULTURAL PERSPECTIVE", "Cultural Perspective",
        "ROLE PLAY", "Role Play",
        "IMAGE DESCRIPTION", "Image Description",
        "WRITING FRAME", "Writing Frame",
        "REAL CASE", "Real Case",
    ]

    bloom_words = [
        "Huske", "Forstå", "Anvende", "Analysere", "Vurdere", "Skape",
        "Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create",
    ]

    instruction_fragments = [
        "Velg riktig svar", "basert på teksten", "Snakk sammen med",
        "Svar på spørsmålene", "Her er 4 spørsmål", "Her er fire spørsmål",
        "tilpasset voksne deltakere",
        "Choose the correct answer", "based on the text", "Talk to a partner",
        "Answer the questions", "Here are 4 questions", "Here are four questions",
        "adapted for adult learners",
    ]

    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue

        should_remove = False

        if stripped.upper() in [k.upper() for k in header_keywords]:
            should_remove = True

        if not should_remove:
            for bloom in bloom_words:
                if re.search(rf"\([^)]*{bloom}[^)]*\)", stripped, re.IGNORECASE):
                    should_remove = True
                    break

        if not should_remove:
            for keyword in header_keywords:
                if keyword.upper() in stripped.upper() and len(stripped) < 100:
                    should_remove = True
                    break

        if not should_remove:
            for fragment in instruction_fragments:
                if fragment.lower() in stripped.lower() and len(stripped) < 150:
                    should_remove = True
                    break

        if not should_remove:
            cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def clean_meta_instructions(text: str) -> str:
    """Remove meta-instructions that describe the task."""
    if not text:
        return ""

    meta_patterns = [
        r"^Her er \d+ spørsmål[^.:\n]*[:\n]*",
        r"^Her er fire spørsmål[^.:\n]*[:\n]*",
        r"^Disse (?:spørsmålene|oppgavene)[^.:\n]*[:\n]*",
        r"^Følgende oppgaver[^.:\n]*[:\n]*",
        r"^Under finner du[^.:\n]*[:\n]*",
        r"^Nedenfor er[^.:\n]*[:\n]*",
        r"^Dette er oppgaver[^.:\n]*[:\n]*",
        r"^Denne oppgaven[^.:\n]*[:\n]*",
    ]

    for pattern in meta_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

    return text.strip()


def remove_answer_markers(text: str) -> str:
    """Remove trailing asterisks from answers."""
    if not text:
        return ""

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line = re.sub(r"\s*\*+\s*$", "", line)
        line = re.sub(r"\.\s*\*+\s*$", ".", line)
        line = re.sub(r"\*+\.\s*$", ".", line)
        line = re.sub(r"\s*\(\s*\*+\s*\)\s*$", "", line)
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def convert_markdown_lists_to_typst(text: str) -> str:
    """Convert Markdown * list markers to Typst - list markers."""
    if not text:
        return ""

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        if re.match(r"^\s*\*\s+", line) and not line.strip().startswith("**"):
            line = re.sub(r"^\s*\*\s+", "- ", line)
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


# ---------------------------------------------------------------------------
# Main sanitizer
# ---------------------------------------------------------------------------


def sanitize_for_typst(text: str, is_section_content: bool = False) -> str:
    """
    Sanitize text for safe inclusion in Typst documents.

    Handles AI artefact removal, Typst character escaping, Markdown→Typst
    conversion, and Norwegian character preservation.
    """
    if not text:
        return ""

    text = clean_ai_artifacts(text)

    if is_section_content:
        text = clean_section_header(text)
        text = clean_meta_instructions(text)

    text = convert_markdown_lists_to_typst(text)

    # Bold / italic
    text = re.sub(r"\*\*(.+?)\*\*", r"#strong[\1]", text)
    text = re.sub(r"__(.+?)__", r"#strong[\1]", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"#emph[\1]", text)

    # Protect Typst commands from escaping
    protected_patterns: list[str] = []

    def protect_pattern(match: re.Match) -> str:
        idx = len(protected_patterns)
        protected_patterns.append(match.group(0))
        return f"TYPSTPROTECT{idx}ENDPROTECT"

    text = re.sub(r"#(strong|emph)\[([^\[\]]*)\]", protect_pattern, text, flags=re.DOTALL)

    escape_chars = [
        ("\\", "\\\\"),
        ("#", "\\#"),
        ("$", "\\$"),
        ("@", "\\@"),
        ("<", "\\<"),
        (">", "\\>"),
        ("{", "\\{"),
        ("}", "\\}"),
        ("[", "\\["),
        ("]", "\\]"),
        ("`", "\\`"),
        ("*", "\\*"),
        ("_", "\\_"),
    ]
    for char, escaped in escape_chars:
        text = text.replace(char, escaped)

    for idx, pattern in enumerate(protected_patterns):
        text = text.replace(f"TYPSTPROTECT{idx}ENDPROTECT", pattern)

    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


# ---------------------------------------------------------------------------
# Formatting helpers (depend on sanitize_for_typst)
# ---------------------------------------------------------------------------


def format_vocabulary_as_list(text: str) -> str:
    """Format vocabulary text into a Typst bulleted list with bold terms."""
    if not text:
        return ""

    lines = text.split("\n")
    formatted_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            formatted_lines.append("")
            continue

        clean_line = stripped
        if clean_line.startswith("- "):
            clean_line = clean_line[2:].strip()
        elif clean_line.startswith("• "):
            clean_line = clean_line[2:].strip()

        if "#strong[" in clean_line:
            formatted_lines.append(f"- {clean_line}")
        elif "\\:" in clean_line:
            colon_idx = clean_line.index("\\:")
            term = clean_line[:colon_idx].strip()
            definition = clean_line[colon_idx + 2:].strip()
            if term and definition:
                formatted_lines.append(f"- #strong[{term}:] {definition}")
            elif term:
                formatted_lines.append(f"- #strong[{term}]")
            else:
                formatted_lines.append(f"- {clean_line}")
        elif ": " in clean_line:
            colon_idx = clean_line.index(": ")
            term = clean_line[:colon_idx].strip()
            definition = clean_line[colon_idx + 2:].strip()
            if term and definition:
                formatted_lines.append(f"- #strong[{term}:] {definition}")
            elif term:
                formatted_lines.append(f"- #strong[{term}]")
            else:
                formatted_lines.append(f"- {clean_line}")
        else:
            formatted_lines.append(f"- {clean_line}")

    return "\n".join(formatted_lines)


def sanitize_comprehension_for_typst(text: str) -> str:
    """Sanitize comprehension questions, stripping answer markers."""
    if not text:
        return ""
    text = remove_answer_markers(text)
    return sanitize_for_typst(text, is_section_content=True)


def format_mcq_content(text: str) -> str:
    """Format multiple choice question content for proper layout."""
    if not text:
        return ""

    lines = text.split("\n")
    formatted_lines: list[str] = []
    question_count = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if formatted_lines and formatted_lines[-1] != "#v(0.5em)":
                formatted_lines.append("#v(0.5em)")
            continue

        question_match = re.match(r"^(\d+)[.\)]\s*(.+)$", stripped)
        if question_match:
            question_count += 1
            if question_count > 1:
                formatted_lines.append("#v(0.8em)")
            formatted_lines.append(
                f"#strong[{question_match.group(1)}.] {question_match.group(2)}"
            )
            continue

        option_match = re.match(r"^([a-d])[.\)]\s*(.+)$", stripped, re.IGNORECASE)
        if option_match:
            letter = option_match.group(1).lower()
            formatted_lines.append(f"#h(1em) {letter}) {option_match.group(2)}")
            continue

        formatted_lines.append(stripped)

    return "\n".join(formatted_lines)
