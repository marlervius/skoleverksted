"""
Differentiation generator — produces three difficulty levels from standard output.

Takes the final LaTeX output from the pipeline and generates:
- Grunnleggende (basic): simpler numbers, more intermediate steps, extra hints
- Standard: the original content
- Avansert (advanced): harder numbers, fewer steps, composite/proof tasks

Uses a single LLM call with structured JSON output, then parses into
three separate LaTeX documents. All three are SymPy-verified.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.rate_limit import limiter
from app.validators import ensure_latex_size

from app.models.llm import get_llm

logger = structlog.get_logger()

router = APIRouter(prefix="/differentiation", tags=["differentiation"])


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class LevelQuality:
    score: int = 100
    passed: bool = True
    math_verified: bool = False
    issue_count: int = 0
    summary: str = ""


@dataclass
class DifferentiatedOutput:
    """Three-level differentiated content."""
    basic_latex: str = ""
    standard_latex: str = ""
    advanced_latex: str = ""
    basic_verified: bool = False
    standard_verified: bool = False
    advanced_verified: bool = False
    basic_quality: LevelQuality = field(default_factory=LevelQuality)
    standard_quality: LevelQuality = field(default_factory=LevelQuality)
    advanced_quality: LevelQuality = field(default_factory=LevelQuality)


class DifferentiateRequest(BaseModel):
    """Request to differentiate existing LaTeX content."""
    latex_content: str = Field(
        ...,
        min_length=10,
        description="The standard-level LaTeX content to differentiate",
    )
    topic: str = Field("", description="Math topic for context")
    grade: str = Field("", description="Grade level for context")

    class Config:
        json_schema_extra = {
            "example": {
                "latex_content": "\\begin{taskbox}{Oppgave 1}\nLøs $2x + 3 = 7$\n\\end{taskbox}",
                "topic": "Algebra",
                "grade": "8. trinn",
            }
        }


class LevelQualityOut(BaseModel):
    score: int = 100
    passed: bool = True
    math_verified: bool = False
    issue_count: int = 0
    summary: str = ""


class DifferentiateResponse(BaseModel):
    success: bool
    basic_latex: str = ""
    standard_latex: str = ""
    advanced_latex: str = ""
    basic_exercise_count: int = 0
    standard_exercise_count: int = 0
    advanced_exercise_count: int = 0
    basic_quality: LevelQualityOut | None = None
    standard_quality: LevelQualityOut | None = None
    advanced_quality: LevelQualityOut | None = None
    errors: list[str] = []


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_DIFFERENTIATION_SYSTEM = """Du er en ekspert matematikklærer som differensierer undervisningsmateriell.

Du får et sett med matematikkoppgaver på standard nivå. Du skal lage TRE versjoner:

## GRUNNLEGGENDE
- Enklere tall (helst heltall, små tall)
- Vis flere mellomregninger og steg
- Legg til "Tips:"-bokser med hint
- Fjern de vanskeligste oppgavene (behold 60-70% av antallet)
- Legg til et løst eksempel FØR oppgavene

## STANDARD
- Behold originalen uendret

## AVANSERT
- Vanskeligere tall (desimaler, brøker, store tall)
- Fjern mellomregninger — elever må finne ut selv
- Legg til sammensatte oppgaver som kombinerer flere konsepter
- Legg til bevisoppgaver eller "forklar hvorfor"-oppgaver
- Legg til 1-2 ekstra utfordringsoppgaver

VIKTIG:
- All matematikk SKAL være korrekt på ALLE tre nivåer
- Behold alle LaTeX-miljøer (taskbox, tcolorbox, align, etc.)
- Returner som JSON med nøklene "basic", "standard", "advanced"
- Hver verdi er den KOMPLETTE LaTeX-kroppen (uten preamble/documentclass)
- Bruk NØYAKTIG samme LaTeX-konvensjoner som input"""


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def _quality_out(level: str, content: str, verified: bool, grade: str, topic: str) -> LevelQuality:
    from app.latex.text_sanitize import sanitize_latex_body
    from app.models.state import GenerationRequest
    from app.verification.content_quality import evaluate_content_quality

    content = sanitize_latex_body(content)
    diff_req = GenerationRequest(
        grade=grade or "8. trinn",
        topic=topic or "Matematikk",
        material_type="differensiert",
        num_exercises=6,
    )
    q = evaluate_content_quality(content, diff_req)
    summary_parts: list[str] = []
    if not verified:
        summary_parts.append("SymPy fant mulige fasitfeil")
    if not q.passed:
        summary_parts.append(f"innholdsscore {q.score}/100")
    if q.issues:
        summary_parts.append(f"{len(q.issues)} kvalitetsmerknader")
    return LevelQuality(
        score=q.score,
        passed=q.passed and verified,
        math_verified=verified,
        issue_count=len(q.issues),
        summary="; ".join(summary_parts) if summary_parts else "OK",
    )


def _level_quality_out(q: LevelQuality) -> LevelQualityOut:
    return LevelQualityOut(**q.__dict__)


async def differentiate_content(
    latex_content: str,
    topic: str = "",
    grade: str = "",
) -> DifferentiatedOutput:
    """
    Generate three difficulty levels from standard LaTeX content.

    Uses one LLM call with structured JSON output.
    """
    from app.latex.text_sanitize import sanitize_latex_body

    latex_content = sanitize_latex_body(latex_content)
    llm = get_llm(temperature=0.3)

    user_prompt = f"STANDARD-NIVÅ INNHOLD:\n\n{latex_content}"
    if topic:
        user_prompt += f"\n\nEMNE: {topic}"
    if grade:
        user_prompt += f"\n\nTRINN: {grade}"

    user_prompt += (
        "\n\nReturner JSON med nøklene 'basic', 'standard', 'advanced'. "
        "Hver verdi er komplett LaTeX-kropp."
    )

    result = await llm.ainvoke(_DIFFERENTIATION_SYSTEM, user_prompt)

    # Parse JSON from response
    output = DifferentiatedOutput(standard_latex=latex_content)

    try:
        # Try to extract JSON from the response
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            output.basic_latex = sanitize_latex_body(data.get("basic", ""))
            output.standard_latex = sanitize_latex_body(data.get("standard", latex_content))
            output.advanced_latex = sanitize_latex_body(data.get("advanced", ""))
        else:
            logger.warning("differentiation_no_json", response_preview=result[:200])
    except json.JSONDecodeError as e:
        logger.error("differentiation_json_parse_error", error=str(e))

    # Verify math in all three levels
    try:
        from app.verification.math_checker import MathChecker

        checker = MathChecker()
        for level, content in [
            ("basic", output.basic_latex),
            ("standard", output.standard_latex),
            ("advanced", output.advanced_latex),
        ]:
            if content:
                verification = await asyncio.to_thread(checker.verify, content)
                setattr(output, f"{level}_verified", verification.all_correct)
                if not verification.all_correct:
                    logger.warning(
                        f"differentiation_{level}_math_errors",
                        errors=verification.claims_incorrect,
                    )
    except Exception as e:
        logger.warning("differentiation_verification_skipped", error=str(e))

    try:
        for level, content in [
            ("basic", output.basic_latex),
            ("standard", output.standard_latex),
            ("advanced", output.advanced_latex),
        ]:
            if content:
                verified = getattr(output, f"{level}_verified", False)
                q = _quality_out(level, content, verified, grade, topic)
                setattr(output, f"{level}_quality", q)
                if not q.passed:
                    logger.warning(
                        "differentiation_quality_gaps",
                        level=level,
                        score=q.score,
                        issues=q.issue_count,
                    )
    except Exception as e:
        logger.warning("differentiation_quality_skipped", error=str(e))

    logger.info(
        "differentiation_completed",
        basic_len=len(output.basic_latex),
        standard_len=len(output.standard_latex),
        advanced_len=len(output.advanced_latex),
    )

    return output


def differentiate_content_sync(
    latex_content: str,
    topic: str = "",
    grade: str = "",
) -> DifferentiatedOutput:
    """Synchronous variant for use inside the LangGraph pipeline."""
    llm = get_llm(temperature=0.3)

    user_prompt = f"STANDARD-NIVÅ INNHOLD:\n\n{latex_content}"
    if topic:
        user_prompt += f"\n\nEMNE: {topic}"
    if grade:
        user_prompt += f"\n\nTRINN: {grade}"
    user_prompt += (
        "\n\nReturner JSON med nøklene 'basic', 'standard', 'advanced'. "
        "Hver verdi er komplett LaTeX-kropp."
    )

    result = llm.invoke(_DIFFERENTIATION_SYSTEM, user_prompt)
    output = DifferentiatedOutput(standard_latex=latex_content)

    try:
        json_match = re.search(r"\{[\s\S]*\}", result)
        if json_match:
            data = json.loads(json_match.group())
            output.basic_latex = data.get("basic", "")
            output.standard_latex = data.get("standard", latex_content)
            output.advanced_latex = data.get("advanced", "")
    except json.JSONDecodeError as e:
        logger.error("differentiation_sync_json_error", error=str(e))

    try:
        from app.verification.math_checker import MathChecker

        checker = MathChecker()
        for level, content in [
            ("basic", output.basic_latex),
            ("standard", output.standard_latex),
            ("advanced", output.advanced_latex),
        ]:
            if content:
                verification = checker.verify(content)
                setattr(output, f"{level}_verified", verification.all_correct)
    except Exception as e:
        logger.warning("differentiation_sync_verify_skipped", error=str(e))

    return output


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=DifferentiateResponse, summary="Generate three difficulty levels from standard content")
@limiter.limit("10/minute")
async def differentiate(
    request: Request,
    req: DifferentiateRequest,
    user_id: str = Depends(get_current_user),
) -> DifferentiateResponse:
    """
    Generate basic, standard, and advanced versions of the given LaTeX content.

    Uses AI to adapt exercises for different ability levels while
    maintaining mathematical correctness (verified with SymPy).
    """
    ensure_latex_size(req.latex_content)
    try:
        output = await differentiate_content(
            req.latex_content,
            topic=req.topic,
            grade=req.grade,
        )

        def _count_exercises(latex: str) -> int:
            return latex.count(r"\begin{taskbox}")

        return DifferentiateResponse(
            success=True,
            basic_latex=output.basic_latex,
            standard_latex=output.standard_latex,
            advanced_latex=output.advanced_latex,
            basic_exercise_count=_count_exercises(output.basic_latex),
            standard_exercise_count=_count_exercises(output.standard_latex),
            advanced_exercise_count=_count_exercises(output.advanced_latex),
            basic_quality=_level_quality_out(output.basic_quality)
            if output.basic_latex
            else None,
            standard_quality=_level_quality_out(output.standard_quality)
            if output.standard_latex
            else None,
            advanced_quality=_level_quality_out(output.advanced_quality)
            if output.advanced_latex
            else None,
        )
    except Exception as e:
        logger.error("differentiation_failed", error=str(e))
        return DifferentiateResponse(success=False, errors=[str(e)])
