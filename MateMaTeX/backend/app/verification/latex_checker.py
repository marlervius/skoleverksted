"""
LaTeX compilation checker — uses shared pdflatex runner from app.latex.compiler.
"""

from __future__ import annotations

import re

import structlog

from app.latex.compiler import compile_latex_to_bytes
from app.models.state import LatexCompilationResult

logger = structlog.get_logger()


class LatexChecker:
    """Validates LaTeX by actually compiling it with pdflatex."""

    def __init__(self, pdflatex_path: str = "pdflatex"):
        self._pdflatex = pdflatex_path

    def check(self, full_latex_document: str) -> LatexCompilationResult:
        result = LatexCompilationResult()
        pdf_bytes, log_excerpt = compile_latex_to_bytes(full_latex_document, self._pdflatex)
        result.log_excerpt = log_excerpt[-4000:] if log_excerpt else ""

        if log_excerpt:
            result.errors = self._extract_errors(log_excerpt)
            result.warnings = self._extract_warnings(log_excerpt)

        if pdf_bytes:
            result.success = True
            result.pdf_bytes = pdf_bytes
            logger.info("latex_compilation_success", pdf_size_bytes=len(pdf_bytes))
        else:
            result.success = False
            if not result.errors:
                result.errors = ["PDF compilation failed"]
            logger.warning("latex_compilation_failed", errors=result.errors[:3])

        return result

    @staticmethod
    def _extract_errors(log_text: str) -> list[str]:
        errors: list[str] = []
        patterns = [
            re.compile(r"^!\s*(.+)$", re.MULTILINE),
            re.compile(r"^l\.(\d+)\s*(.+)$", re.MULTILINE),
        ]
        for pattern in patterns:
            for match in pattern.finditer(log_text):
                err_msg = match.group(0).strip()
                if err_msg and err_msg not in errors:
                    errors.append(err_msg)
        return errors[:20]

    @staticmethod
    def _extract_warnings(log_text: str) -> list[str]:
        warnings: list[str] = []
        for match in re.finditer(r"LaTeX Warning:\s*(.+?)(?:\n|$)", log_text):
            warnings.append(match.group(1).strip())
        for match in re.finditer(r"((?:Over|Under)full \\[hv]box.+?)(?:\n|$)", log_text):
            warnings.append(match.group(1).strip())
        return warnings[:20]


def format_latex_errors_for_agent(result: LatexCompilationResult) -> str:
    """Format compilation errors into instructions for the LaTeX fixer agent."""
    if result.success:
        return ""

    lines = [
        "=== LaTeX KOMPILERINGSFEIL ===",
        f"pdflatex feilet med {len(result.errors)} feil.\n",
    ]
    for i, err in enumerate(result.errors[:10], 1):
        lines.append(f"FEIL {i}: {err}")
    lines.append(f"\nSiste del av loggen:\n{result.log_excerpt[-500:]}")
    lines.append("\nRETT ALLE FEILENE og returner hele det korrigerte LaTeX-dokumentet.")
    return "\n".join(lines)
