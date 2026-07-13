"""
Fallback agent node — Returns a stripped-down, guaranteed-to-compile document if all else fails.
"""

from __future__ import annotations

import base64
import re
from datetime import datetime

import structlog

from app.config import get_config
from app.latex.preamble import wrap_with_style
from app.models.state import AgentRole, AgentStep, PipelineState
from app.verification.latex_checker import LatexChecker

logger = structlog.get_logger()


def run_latex_fallback(state: PipelineState) -> PipelineState:
    """
    Fallback agent that strips problematic LaTeX (like TikZ) to ensure the user gets *something*.

    Reads: state.full_document or state.edited_latex_body
    Writes: state.full_document, state.steps
    """
    step = AgentStep(agent=AgentRole.LATEX_FALLBACK)
    state.current_agent = AgentRole.LATEX_FALLBACK

    logger.warning(
        "latex_fallback_start",
        job_id=state.job_id,
        msg="Max retries reached. Stripping complex formatting for fallback document.",
    )

    try:
        body = state.edited_latex_body or state.raw_latex_body

        body = re.sub(
            r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}",
            "% [Figur fjernet pga. kompileringsfeil]",
            body,
            flags=re.DOTALL,
        )
        body = re.sub(
            r"\\begin\{axis\}.*?\\end\{axis\}",
            "% [Graf fjernet pga. kompileringsfeil]",
            body,
            flags=re.DOTALL,
        )
        # Unwrap simple \textcolor{color}{text} to plain text. The old greedy
        # pattern could swallow valid content mid-paragraph.
        body = re.sub(r"\\textcolor\{[^{}]*\}\{([^{}]*)\}", r"\1", body)

        fallback_warning = r"""
\begin{tcolorbox}[colback=red!5!white,colframe=red!75!black,title=Kompileringsadvarsel]
Dette dokumentet inneholdt avansert grafikk (f.eks. TikZ-figurer) som feilet under generering.
For å sikre at du likevel får oppgavene og teksten, har systemet fjernet problematiske figurer.
\end{tcolorbox}
"""
        body = fallback_warning + "\n" + body

        state.final_latex_body = body
        state.edited_latex_body = body
        state.full_document = ""
        state.used_latex_fallback = True

        full_doc = wrap_with_style(body, state.request.pdf_style)
        config = get_config()
        checker = LatexChecker(pdflatex_path=config.pdflatex_path)
        result = checker.check(full_doc)

        state.latex_compilation = result
        state.latex_compilation.used_fallback = True
        if result.success:
            state.full_document = full_doc
            from app.pipeline.agents.latex_validator import _persist_pdf

            if result.pdf_bytes:
                try:
                    state.pdf_path = _persist_pdf(state.job_id, result.pdf_bytes)
                    state.pdf_base64 = base64.b64encode(result.pdf_bytes).decode("ascii")
                except OSError as persist_err:
                    state.pdf_path = ""
                    state.pdf_base64 = ""
                    logger.warning("latex_fallback_pdf_persist_failed", error=str(persist_err))
            step.output_summary = "Laget forenklet fallback-dokument (verifisert)"
            logger.info("latex_fallback_complete", job_id=state.job_id)
        else:
            state.latex_compilation.success = False
            step.error = f"Fallback compilation failed: {result.errors[:2]}"
            logger.warning("latex_fallback_still_failed", job_id=state.job_id, errors=result.errors[:3])

    except Exception as e:
        step.error = str(e)
        logger.error("latex_fallback_failed", job_id=state.job_id, error=str(e))

    finally:
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        state.steps.append(step)

    return state
