"""
Hint engine — generates progressive hints for exercises.

Produces three levels:
1. Dytt (nudge): vague directional hint
2. Steg (step): first concrete step
3. Nesten-løsning (near-solution): most of the solution, missing last step

Also generates QR codes linking to a hint viewing page.
"""

from __future__ import annotations

import io
import json
import re

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user

from app.models.llm import get_llm

logger = structlog.get_logger()

router = APIRouter(prefix="/exercises", tags=["differentiation"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class HintSet(BaseModel):
    """Three progressive hints for an exercise."""
    nudge: str = Field("", description="Vag retningsindikasjon")
    step: str = Field("", description="Første konkrete steg")
    near_solution: str = Field("", description="Mesteparten av løsningen")


class HintRequest(BaseModel):
    exercise_latex: str = Field(
        ...,
        min_length=5,
        description="The exercise LaTeX to generate hints for",
    )
    solution: str = Field(
        "",
        description="Known solution (helps generate better hints)",
    )


class HintResponse(BaseModel):
    success: bool
    hints: HintSet = Field(default_factory=HintSet)
    error: str = ""


class QrResponse(BaseModel):
    success: bool
    qr_base64: str = ""
    url: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_HINT_SYSTEM = """Du er en matematikklærer som lager progressive hint til oppgaver.

Lag NØYAKTIG tre hint med stigende detalj:

1. **DYTT** (1 setning): En vag retningsindikasjon uten å avsløre metoden.
   Eksempel: "Tenk på hva som skjer når du flytter et ledd til andre siden."

2. **STEG** (1-2 setninger): Det første konkrete steget.
   Eksempel: "Start med å trekke fra 3 på begge sider av likhetstegnet."

3. **NESTEN-LØSNING** (2-4 setninger): Mesteparten av løsningen, men mangler siste steg.
   Vis mellomregninger med LaTeX-matematikk, men stopp rett før det endelige svaret.

REGLER:
- Bruk LaTeX-syntaks for all matematikk ($...$ for inline, \\[...\\] for display)
- Hvert hint er en streng (ikke LaTeX-miljø)
- Returner som JSON: {"nudge": "...", "step": "...", "near_solution": "..."}"""


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
async def generate_hints(
    exercise_latex: str,
    solution: str = "",
) -> HintSet:
    """Generate three progressive hints for an exercise."""
    llm = get_llm(temperature=0.3)

    user_prompt = f"OPPGAVE:\n{exercise_latex}"
    if solution:
        user_prompt += f"\n\nKJENT LØSNING:\n{solution}"

    result = await llm.ainvoke(_HINT_SYSTEM, user_prompt)

    # Parse JSON
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return HintSet(
                nudge=data.get("nudge", ""),
                step=data.get("step", ""),
                near_solution=data.get("near_solution", ""),
            )
    except json.JSONDecodeError:
        logger.warning("hint_json_parse_error", response=result[:200])

    # Fallback: try to split by numbered items
    return HintSet(nudge=result.strip())


def generate_qr_code(url: str) -> bytes:
    """Generate a QR code PNG for the given URL."""
    try:
        import qrcode
        from qrcode.image.pil import PilImage

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    except ImportError:
        logger.warning("qrcode_not_installed")
        return b""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{exercise_id}/hints",
    response_model=HintResponse,
    summary="Generate progressive hints for an exercise",
)
async def create_hints(exercise_id: str, req: HintRequest, user_id: str = Depends(get_current_user)) -> HintResponse:
    """
    Generate three progressive hints for the specified exercise.

    Returns nudge → step → near-solution with increasing detail.
    """
    try:
        hints = await generate_hints(req.exercise_latex, req.solution)

        # In production, store hints on the exercise in the database
        logger.info(
            "hints_generated",
            exercise_id=exercise_id,
            has_nudge=bool(hints.nudge),
            has_step=bool(hints.step),
            has_near_solution=bool(hints.near_solution),
        )

        return HintResponse(success=True, hints=hints)
    except Exception as e:
        logger.error("hint_generation_failed", error=str(e))
        return HintResponse(success=False, error=str(e))


@router.get(
    "/{exercise_id}/hints/qr",
    response_model=QrResponse,
    summary="Generate QR code linking to hint viewing page",
)
async def get_hint_qr(exercise_id: str, user_id: str = Depends(get_current_user)) -> QrResponse:
    """
    Generate a QR code that links to a mobile-friendly hint viewing page.

    The QR code can be embedded in printed worksheets.
    """
    import base64

    # In production, this URL would be the actual deployed frontend
    hint_url = f"/hints/{exercise_id}"

    try:
        qr_bytes = generate_qr_code(hint_url)
        if qr_bytes:
            return QrResponse(
                success=True,
                qr_base64=base64.b64encode(qr_bytes).decode(),
                url=hint_url,
            )
        else:
            return QrResponse(
                success=False,
                error="QR code generation failed (qrcode package not installed?)",
            )
    except Exception as e:
        return QrResponse(success=False, error=str(e))
