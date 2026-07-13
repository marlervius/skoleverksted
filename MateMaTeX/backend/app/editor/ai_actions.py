"""
AI-assisted editor actions.

Each action takes a LaTeX selection + full context and returns
replacement LaTeX using the model-agnostic LLM interface.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.rate_limit import limiter

from app.models.llm import get_llm

logger = structlog.get_logger()

router = APIRouter(prefix="/editor", tags=["editor"])


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------
class EditorActionRequest(BaseModel):
    """Input for all AI editor actions."""
    latex_selection: str = Field(
        ...,
        description="The selected LaTeX text to transform",
        min_length=1,
        max_length=20_000,
    )
    full_context: str = Field(
        "",
        description="The surrounding LaTeX document for context",
        max_length=100_000,
    )
    extra_instructions: str = Field(
        "",
        description="Optional additional instructions for the AI",
        max_length=2_000,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "latex_selection": "Finn $x$ når $2x + 3 = 7$.",
                "full_context": "\\section{Algebra}\\n...",
                "extra_instructions": "",
            }
        }


class EditorActionResponse(BaseModel):
    """AI-generated replacement LaTeX."""
    success: bool
    replacement_latex: str = ""
    explanation: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# System prompts for each action
# ---------------------------------------------------------------------------
_BASE_SYSTEM = (
    "Du er en ekspert i matematikk-didaktikk og LaTeX. "
    "Returner KUN den erstattende LaTeX-koden — ingen forklaringer, "
    "ingen \\documentclass, ingen preamble. Behold alle eksisterende "
    "LaTeX-miljøer (tcolorbox, align, etc.)."
)

_SIMPLIFY_PROMPT = (
    f"{_BASE_SYSTEM}\n\n"
    "OPPGAVE: Forenkle den markerte teksten. Behold all matematikk "
    "identisk, men gjør språket enklere (kortere setninger, vanlige ord). "
    "Matematiske uttrykk og formler skal IKKE endres."
)

_ILLUSTRATION_PROMPT = (
    f"{_BASE_SYSTEM}\n\n"
    "OPPGAVE: Lag en TikZ- eller PGFPlots-illustrasjon som passer til "
    "den markerte konteksten. Bruk prosjektets farger: mainBlue (#2563eb), "
    "mainGreen (#16a34a), mainOrange (#ea580c). Returner et komplett "
    "\\begin{{tikzpicture}} ... \\end{{tikzpicture}} miljø."
)

_VARIANT_PROMPT = (
    f"{_BASE_SYSTEM}\n\n"
    "OPPGAVE: Lag en alternativ versjon av oppgaven. Endre tallene "
    "og/eller konteksten, men behold den matematiske strukturen og "
    "vanskelighetsgraden. Sørg for at den nye varianten har korrekt "
    "løsning."
)

_HINT_PROMPT = (
    f"{_BASE_SYSTEM}\n\n"
    "OPPGAVE: Generer tre progressive hint til oppgaven:\n"
    "1. DYTT: En vag retningsindikasjon (1 setning)\n"
    "2. STEG: Det første konkrete steget (1-2 setninger)\n"
    "3. NESTEN-LØSNING: Mesteparten av løsningen, mangler siste steg\n\n"
    "Formater hvert hint som en egen \\begin{{hintbox}}{{Hint N}} ... \\end{{hintbox}} "
    "blokk. Bruk LaTeX-matematikk for alle uttrykk."
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/simplify",
    response_model=EditorActionResponse,
    summary="Simplify selected text (keep math, simpler language)",
)
@limiter.limit("10/minute")
async def simplify(request: Request, req: EditorActionRequest, user_id: str = Depends(get_current_user)) -> EditorActionResponse:
    """Simplify the selected LaTeX text while keeping math intact."""
    return await _run_action(_SIMPLIFY_PROMPT, req)


@router.post(
    "/add-illustration",
    response_model=EditorActionResponse,
    summary="Generate TikZ/PGFPlots illustration for context",
)
@limiter.limit("10/minute")
async def add_illustration(request: Request, req: EditorActionRequest, user_id: str = Depends(get_current_user)) -> EditorActionResponse:
    """Generate a TikZ or PGFPlots illustration matching the selected context."""
    return await _run_action(_ILLUSTRATION_PROMPT, req)


@router.post(
    "/variant",
    response_model=EditorActionResponse,
    summary="Generate an alternative version of an exercise",
)
@limiter.limit("10/minute")
async def create_variant(request: Request, req: EditorActionRequest, user_id: str = Depends(get_current_user)) -> EditorActionResponse:
    """Create a new variant of the selected exercise with different numbers/context."""
    return await _run_action(_VARIANT_PROMPT, req)


@router.post(
    "/add-hint",
    response_model=EditorActionResponse,
    summary="Generate progressive hints for an exercise",
)
@limiter.limit("10/minute")
async def add_hint(request: Request, req: EditorActionRequest, user_id: str = Depends(get_current_user)) -> EditorActionResponse:
    """Generate three progressive hints for the selected exercise."""
    return await _run_action(_HINT_PROMPT, req)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------
async def _run_action(
    system_prompt: str,
    req: EditorActionRequest,
) -> EditorActionResponse:
    """Execute an AI action and return the result."""
    try:
        llm = get_llm(temperature=0.4)

        user_prompt = f"MARKERT TEKST:\n{req.latex_selection}"
        if req.full_context:
            user_prompt += f"\n\nFULL KONTEKST (for referanse):\n{req.full_context}"
        if req.extra_instructions:
            user_prompt += f"\n\nEKSTRA INSTRUKSJONER:\n{req.extra_instructions}"

        result = await llm.ainvoke(system_prompt, user_prompt)

        logger.info(
            "editor_action_completed",
            action=system_prompt[:30],
            input_len=len(req.latex_selection),
            output_len=len(result),
        )

        return EditorActionResponse(
            success=True,
            replacement_latex=result.strip(),
        )

    except Exception as e:
        logger.error("editor_action_failed", error=str(e))
        return EditorActionResponse(
            success=False,
            error=str(e),
        )
