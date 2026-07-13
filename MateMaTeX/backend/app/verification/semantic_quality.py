"""
LLM rubric pass for kapittel — complements rule-based content_quality.

Low temperature, warning-only: adds issues but does not block delivery alone.
"""

from __future__ import annotations

import json
import re

import structlog

from app.models.state import ContentQualityIssue, GenerationRequest

logger = structlog.get_logger()

_RUBRIC_PROMPT = """\
Du er en erfaren norsk matematikklærer. Vurder LaTeX-kapittelkroppen (uten preamble)
mot rubrikken nedenfor. Svar KUN med JSON:
{"score": 0-100, "issues": [{"code": "...", "message": "..."}]}

RUBRIKK (0–100):
- Progresjon: bygger logisk fra enkelt til avansert?
- Forklaringer: eksempler har steg-for-steg, ikke bare svar?
- Oppgaver: relevante for emne og trinn?
- Språk: konsistent norsk, passende for {grade}?
- Didaktikk: læringsmål, utforsk, vanlige feil — meningsfylt?

code skal være: weak_progression | thin_explanations | weak_exercises | language | didactics
Gi maks 5 issues. score < 70 betyr tydelige svakheter.
"""


def evaluate_semantic_quality(
    latex_body: str,
    request: GenerationRequest,
) -> tuple[int, list[ContentQualityIssue]]:
    """Return (score, issues). On failure returns (100, [])."""
    body = (latex_body or "").strip()
    if request.material_type != "kapittel" or len(body) < 500:
        return 100, []

    try:
        from app.config import get_settings
        from app.models.llm import LLMInterface

        if not get_settings().google_api_key:
            return 100, []

        sample = body[:12_000]
        llm = LLMInterface(temperature=0.1)
        prompt = _RUBRIC_PROMPT.format(grade=request.grade)
        raw = llm.invoke(
            "Du returnerer kun gyldig JSON uten markdown.",
            f"{prompt}\n\nEMNE: {request.topic}\nTRINN: {request.grade}\n\nKROPP:\n{sample}",
        )
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return 100, []
        data = json.loads(match.group())
        score = max(0, min(100, int(data.get("score", 100))))
        issues: list[ContentQualityIssue] = []
        for item in data.get("issues", [])[:5]:
            issues.append(
                ContentQualityIssue(
                    code=str(item.get("code", "semantic")),
                    severity="warning",
                    message=str(item.get("message", "")),
                )
            )
        logger.info(
            "semantic_quality_complete",
            score=score,
            issues=len(issues),
            topic=request.topic,
        )
        return score, issues
    except Exception as e:
        logger.warning("semantic_quality_skipped", error=str(e))
        return 100, []
