"""
Export API — PDF (enhanced), Word (DOCX), PowerPoint (PPTX).

All endpoints accept LaTeX content and return downloadable documents.
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import tempfile

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.latex.compiler import compile_to_pdf_with_log
from app.pipeline.agents.tikz_validator import sanitize_latex_body, strip_tikz_and_plots
from app.rate_limit import limiter
from app.latex.preamble import wrap_with_preamble
from app.validators import ensure_latex_size

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# LaTeX helpers
# ---------------------------------------------------------------------------
_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _escape_latex(value: str) -> str:
    """Escape LaTeX special characters so user input can't break compilation."""
    if not value:
        return ""
    out = []
    for ch in value:
        out.append(_LATEX_ESCAPES.get(ch, ch))
    return "".join(out)


# Matches \begin{losning}...\end{losning} and Norwegian solution headers
_SOLUTION_ENV_PATTERN = re.compile(
    r"\\begin\{losning\}.*?\\end\{losning\}",
    re.DOTALL,
)
_SOLUTION_SECTION_PATTERN = re.compile(
    r"\\section\*?\{\s*L[øo]sning(?:sforslag)?\s*\}.*?(?=\\section|\\end\{document\}|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_SOLUTION_SUBSECTION_PATTERN = re.compile(
    r"\\subsection\*?\{\s*L[øo]sning(?:sforslag)?\s*\}.*?(?=\\subsection|\\section|\\end\{document\}|\Z)",
    re.DOTALL | re.IGNORECASE,
)


def _strip_solutions(latex: str) -> str:
    """Remove solution boxes and solution sections (lærerkopi → elevkopi)."""
    latex = _SOLUTION_ENV_PATTERN.sub("", latex)
    latex = _SOLUTION_SECTION_PATTERN.sub("", latex)
    latex = _SOLUTION_SUBSECTION_PATTERN.sub("", latex)
    return latex

router = APIRouter(prefix="/export", tags=["export"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class PdfExportRequest(BaseModel):
    latex_content: str = Field(..., min_length=10)
    include_solutions: bool = True
    include_cover: bool = False
    cover_school: str = ""
    cover_teacher: str = ""
    cover_subject: str = "Matematikk"
    cover_topic: str = ""
    print_optimized: bool = False
    include_qr: bool = False
    # Design + accessibility (Track B/D)
    theme: str = "default"
    accessible: bool = False
    dyslexia: bool = False
    high_contrast: bool = False
    student_mode: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "latex_content": "\\section{Test}...",
                "include_cover": True,
                "cover_school": "Oslo Skole",
                "cover_teacher": "Kari Nordmann",
            }
        }


class DocxExportRequest(BaseModel):
    latex_content: str = Field(..., min_length=10)
    title: str = "Oppgaveark"
    include_solutions: bool = True


class PptxExportRequest(BaseModel):
    latex_content: str = Field(..., min_length=10)
    title: str = "Matematikk"
    solutions_as: str = Field(
        "speaker_notes",
        description="'speaker_notes' or 'hidden_slides'",
    )


class ExportFileResponse(BaseModel):
    success: bool
    content_base64: str = ""
    filename: str = ""
    mime_type: str = ""
    errors: list[str] = []


# ---------------------------------------------------------------------------
# Cover page LaTeX
# ---------------------------------------------------------------------------
def _build_cover_page(
    school: str,
    teacher: str,
    subject: str,
    topic: str,
) -> str:
    """Generate a LaTeX cover page. All user-supplied fields are LaTeX-escaped."""
    safe_subject = _escape_latex(subject) or "Matematikk"
    safe_topic = _escape_latex(topic)
    safe_school = _escape_latex(school)
    safe_teacher = _escape_latex(teacher)

    return rf"""
\thispagestyle{{empty}}
\begin{{center}}
\vspace*{{3cm}}

{{\Huge\bfseries\sffamily {safe_subject}}}

\vspace{{1cm}}

{{\LARGE\sffamily {safe_topic}}}

\vspace{{2cm}}

{{\large {safe_school}}}

\vspace{{0.5cm}}

{{\large {safe_teacher}}}

\vspace{{1cm}}

{{\large \today}}

\vspace*{{\fill}}

{{\small Generert av MateMaTeX AI}}

\end{{center}}
\newpage
"""


_PRINT_COLOR_NAMES = ("Blue", "Green", "Orange", "Purple", "Teal", "Gray")


def _make_print_optimized(latex: str) -> str:
    """Convert to grayscale print-friendly version (no colored backgrounds/frames)."""
    replacements: dict[str, str] = {}
    for name in _PRINT_COLOR_NAMES:
        replacements[f"colback=light{name}"] = "colback=white"
        replacements[f"colback=main{name}"] = "colback=black!10"
        replacements[f"colframe=main{name}"] = "colframe=black!60"
        replacements[f"colframe=light{name}"] = "colframe=black!40"
        # \color{...} usages in titleformat, headers etc.
        replacements[f"\\color{{main{name}}}"] = "\\color{black}"
        replacements[f"\\color{{light{name}}}"] = "\\color{black!70}"
    for old, new in replacements.items():
        latex = latex.replace(old, new)
    return latex


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------
@router.post("/pdf", response_model=ExportFileResponse, summary="Export to PDF with optional cover page and print optimization")
@limiter.limit("15/minute")
async def export_pdf(
    request: Request,
    req: PdfExportRequest,
    user_id: str = Depends(get_current_user),
) -> ExportFileResponse:
    """
    Export LaTeX content to PDF.

    Options:
    - Cover page with school name, teacher, date, subject, topic
    - Print-optimized variant (grayscale, no background colors)
    - QR codes for digital solutions
    """
    ensure_latex_size(req.latex_content)
    content = req.latex_content

    # Honour the "elevkopi" toggle by stripping solutions BEFORE wrapping.
    # Only do this if the supplied content includes solution blocks/sections;
    # otherwise we'd modify the document for no reason.
    if not req.include_solutions:
        content = _strip_solutions(content)

    if req.print_optimized:
        content = _make_print_optimized(content)

    # Build full document
    body_parts: list[str] = []
    if req.include_cover:
        body_parts.append(_build_cover_page(
            school=req.cover_school,
            teacher=req.cover_teacher,
            subject=req.cover_subject,
            topic=req.cover_topic,
        ))

    content, sanitize_notes = sanitize_latex_body(content)
    if sanitize_notes:
        logger.info("export_pdf_sanitized", fixes=sanitize_notes)

    body_parts.append(content)
    full_body = "\n".join(body_parts)

    if r"\documentclass" not in full_body:
        full_doc = wrap_with_preamble(
            full_body,
            theme=req.theme,
            student_mode=req.student_mode,
            accessible=req.accessible,
            dyslexia=req.dyslexia,
            high_contrast=req.high_contrast or req.print_optimized,
        )
    else:
        full_doc = full_body

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "export.pdf")
        pdf_path, log_excerpt = await asyncio.to_thread(
            compile_to_pdf_with_log, full_doc, out_path
        )

        # If TikZ still breaks pdflatex, strip figures and retry once.
        if not pdf_path and log_excerpt and (
            "tikzpicture" in log_excerpt.lower()
            or "undefined control sequence" in log_excerpt.lower()
        ):
            logger.warning("export_pdf_retry_without_tikz", user_id=user_id)
            stripped_body = strip_tikz_and_plots(content)
            retry_parts: list[str] = []
            if req.include_cover:
                retry_parts.append(
                    _build_cover_page(
                        school=req.cover_school,
                        teacher=req.cover_teacher,
                        subject=req.cover_subject,
                        topic=req.cover_topic,
                    )
                )
            retry_parts.append(stripped_body)
            retry_full = "\n".join(retry_parts)
            retry_doc = (
                wrap_with_preamble(
                    retry_full,
                    student_mode=req.student_mode,
                )
                if r"\documentclass" not in retry_full
                else retry_full
            )
            pdf_path, log_excerpt = compile_to_pdf_with_log(retry_doc, out_path)

        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            return ExportFileResponse(
                success=True,
                content_base64=base64.b64encode(pdf_bytes).decode(),
                filename="matematikk.pdf",
                mime_type="application/pdf",
            )

        log_tail = (log_excerpt or "").strip().splitlines()[-25:]
        errors = ["PDF-kompilering feilet."]
        if log_tail:
            errors.append("Siste linjer fra pdflatex-loggen:")
            errors.extend(log_tail)
        logger.warning("export_pdf_failed", log_tail="\n".join(log_tail))
        return ExportFileResponse(success=False, errors=errors)


# ---------------------------------------------------------------------------
# DOCX Export
# ---------------------------------------------------------------------------
@router.post("/docx", response_model=ExportFileResponse, summary="Export to Word (DOCX)")
@limiter.limit("15/minute")
async def export_docx(
    request: Request,
    req: DocxExportRequest,
    user_id: str = Depends(get_current_user),
) -> ExportFileResponse:
    """
    Export LaTeX content to Word document.

    Uses python-docx to build the document programmatically for
    maximum control over formatting. Math is rendered as OMML.
    """
    ensure_latex_size(req.latex_content)
    try:
        from app.export.word import latex_to_docx

        docx_bytes = await asyncio.to_thread(
            lambda: latex_to_docx(
                req.latex_content,
                title=req.title,
                include_solutions=req.include_solutions,
            )
        )

        return ExportFileResponse(
            success=True,
            content_base64=base64.b64encode(docx_bytes).decode(),
            filename="matematikk.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as e:
        logger.error("docx_export_failed", error=str(e))
        return ExportFileResponse(
            success=False,
            errors=[str(e)],
        )


# ---------------------------------------------------------------------------
# PPTX Export
# ---------------------------------------------------------------------------
@router.post("/pptx", response_model=ExportFileResponse, summary="Export to PowerPoint (PPTX)")
@limiter.limit("15/minute")
async def export_pptx(
    request: Request,
    req: PptxExportRequest,
    user_id: str = Depends(get_current_user),
) -> ExportFileResponse:
    """
    Export exercises as a PowerPoint presentation.

    Each exercise becomes its own slide. Solutions are placed as
    speaker notes or hidden slides, depending on the request.
    """
    ensure_latex_size(req.latex_content)
    try:
        from app.export.powerpoint import latex_to_pptx

        pptx_bytes = await asyncio.to_thread(
            lambda: latex_to_pptx(
                req.latex_content,
                title=req.title,
                solutions_as=req.solutions_as,
            )
        )

        return ExportFileResponse(
            success=True,
            content_base64=base64.b64encode(pptx_bytes).decode(),
            filename="matematikk.pptx",
            mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    except Exception as e:
        logger.error("pptx_export_failed", error=str(e))
        return ExportFileResponse(
            success=False,
            errors=[str(e)],
        )
