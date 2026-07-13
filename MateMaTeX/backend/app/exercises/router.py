"""
Exercise bank API — CRUD, search, export, import, variant generation.

All endpoints are grouped under the `exercises` tag in OpenAPI docs.
"""

from __future__ import annotations

import hashlib
import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.rate_limit import limiter

from app.exercises.parser import (
    Difficulty,
    ParsedExercise,
    exercises_to_latex,
    parse_exercises,
)
from app.latex.compiler import compile_to_pdf
from app.latex.preamble import wrap_with_preamble

logger = structlog.get_logger()

router = APIRouter(prefix="/exercises", tags=["exercises"])


from app.stores import exercise_store as store


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class ExerciseOut(BaseModel):
    """Exercise as returned by the API."""
    id: str
    title: str
    number: int = 0
    latex_content: str
    solution: str = ""
    hints: list[str] = []
    difficulty: str = "middels"
    exercise_type: str = "standard"
    keywords: list[str] = []
    has_figure: bool = False
    sub_parts: list[str] = []
    topic: str = ""
    grade_level: str = ""
    source_generation_id: str = ""
    times_used: int = 0
    user_rating: int | None = None
    created_at: str = ""


class ExerciseUpdate(BaseModel):
    """Fields that can be updated on an exercise."""
    title: str | None = None
    topic: str | None = None
    grade_level: str | None = None
    difficulty: str | None = None
    user_rating: int | None = Field(None, ge=1, le=5)
    keywords: list[str] | None = None
    latex_content: str | None = Field(None, max_length=100_000)
    solution: str | None = Field(None, max_length=50_000)


class ExerciseListResponse(BaseModel):
    exercises: list[ExerciseOut]
    total: int
    page: int
    page_size: int


class IngestRequest(BaseModel):
    """Request to ingest exercises from a generation's LaTeX output."""
    latex_content: str = Field(..., max_length=500_000)
    topic: str = ""
    grade_level: str = ""
    generation_id: str = ""


class IngestResponse(BaseModel):
    ingested: int
    exercise_ids: list[str]


class ExportRequest(BaseModel):
    exercise_ids: list[str]
    format: Literal["pdf", "docx"] = "pdf"
    include_solutions: bool = True
    title: str = "Oppgaveark"


class ExportResponse(BaseModel):
    success: bool
    content_base64: str = ""
    filename: str = ""
    errors: list[str] = []


class VariantRequest(BaseModel):
    """Request to generate a variant of an exercise."""
    instructions: str = ""


class SearchResponse(BaseModel):
    exercises: list[ExerciseOut]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parsed_to_dict(
    ex: ParsedExercise,
    *,
    topic: str = "",
    grade_level: str = "",
    generation_id: str = "",
) -> dict:
    """Convert a ParsedExercise to a storable dict."""
    return {
        "id": ex.id,
        "title": ex.title,
        "number": ex.number,
        "latex_content": ex.latex_content,
        "solution": ex.solution,
        "hints": ex.hints,
        "difficulty": ex.difficulty.value,
        "exercise_type": ex.exercise_type,
        "keywords": ex.keywords,
        "has_figure": ex.has_figure,
        "sub_parts": ex.sub_parts,
        "topic": topic,
        "grade_level": grade_level,
        "source_generation_id": generation_id,
        "times_used": 0,
        "user_rating": None,
        "created_at": datetime.now().isoformat(),
        "deleted": False,
    }


def _dict_to_out(d: dict) -> ExerciseOut:
    return ExerciseOut(**{k: v for k, v in d.items() if k not in ("deleted", "owner_id", "db_id")})


def _user_owns(d: dict, user_id: str) -> bool:
    """
    Ownership check for a single exercise.

    Legacy exercises without an owner stay accessible, as does any access in the
    shared-key / no-auth modes where every caller resolves to the same identity.
    Real per-user identities (Supabase UUID) must match the stored owner.
    """
    owner = d.get("owner_id")
    if not owner:
        return True
    if user_id in ("anonymous", "api-user"):
        return True
    return owner == user_id


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/ingest", response_model=IngestResponse, summary="Parse LaTeX and ingest exercises into the bank")
@limiter.limit("20/minute")
async def ingest_exercises(
    request: Request,
    req: IngestRequest,
    user_id: str = Depends(get_current_user),
) -> IngestResponse:
    """Parse LaTeX content and store individual exercises in the bank."""
    parsed = parse_exercises(req.latex_content)
    ids = []

    for ex in parsed:
        d = _parsed_to_dict(
            ex,
            topic=req.topic,
            grade_level=req.grade_level,
            generation_id=req.generation_id,
        )
        d["owner_id"] = user_id
        await store.save(d, user_id=user_id)
        ids.append(d["id"])

    logger.info("exercises_ingested", count=len(ids), topic=req.topic)
    return IngestResponse(ingested=len(ids), exercise_ids=ids)


@router.get(
    "",
    response_model=ExerciseListResponse,
    summary="List exercises with filtering and pagination",
    responses={
        200: {
            "description": "Paginated exercise list",
        }
    },
)
async def list_exercises(
    topic: str | None = Query(None, description="Filter by topic"),
    grade_level: str | None = Query(None, description="Filter by grade level"),
    exercise_type: str | None = Query(None, description="Filter by exercise type"),
    difficulty: str | None = Query(None, description="Filter by difficulty"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
) -> ExerciseListResponse:
    """List exercises with optional filtering and pagination."""
    results = await store.list_active(user_id=user_id)

    # Apply filters
    if topic:
        results = [r for r in results if topic.lower() in r.get("topic", "").lower()]
    if grade_level:
        results = [r for r in results if grade_level.lower() in r.get("grade_level", "").lower()]
    if exercise_type:
        results = [r for r in results if r.get("exercise_type") == exercise_type]
    if difficulty:
        results = [r for r in results if r.get("difficulty") == difficulty]

    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    page_results = results[start:end]

    return ExerciseListResponse(
        exercises=[_dict_to_out(d) for d in page_results],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Full-text + semantic search",
    responses={
        200: {"description": "Search results sorted by relevance"},
    },
)
async def search_exercises(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
) -> SearchResponse:
    """
    Combined full-text + keyword search across exercises.

    In production, this uses PostgreSQL tsvector + pgvector cosine similarity.
    This in-memory implementation does keyword matching as a placeholder.
    """
    q_lower = q.lower()
    scored: list[tuple[float, dict]] = []

    for d in await store.list_active(user_id=user_id):

        score = 0.0
        # Title match
        if q_lower in d.get("title", "").lower():
            score += 3.0
        # Topic match
        if q_lower in d.get("topic", "").lower():
            score += 2.0
        # Content match
        if q_lower in d.get("latex_content", "").lower():
            score += 1.0
        # Keyword match
        for kw in d.get("keywords", []):
            if q_lower in kw.lower():
                score += 1.5

        if score > 0:
            scored.append((score, d))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]

    return SearchResponse(
        exercises=[_dict_to_out(d) for _, d in top],
        total=len(scored),
    )


@router.get(
    "/{exercise_id}",
    response_model=ExerciseOut,
    summary="Get a single exercise",
)
async def get_exercise(exercise_id: str, user_id: str = Depends(get_current_user)) -> ExerciseOut:
    d = await store.get(exercise_id)
    if not d or d.get("deleted") or not _user_owns(d, user_id):
        raise HTTPException(404, "Exercise not found")
    return _dict_to_out(d)


@router.put(
    "/{exercise_id}",
    response_model=ExerciseOut,
    summary="Update exercise metadata",
)
async def update_exercise(exercise_id: str, update: ExerciseUpdate, user_id: str = Depends(get_current_user)) -> ExerciseOut:
    d = await store.get(exercise_id)
    if not d or d.get("deleted") or not _user_owns(d, user_id):
        raise HTTPException(404, "Exercise not found")

    payload = update.model_dump(exclude_unset=True)
    new_latex = payload.pop("latex_content", None)
    if new_latex is not None:
        from app.verification.math_checker import MathChecker

        verification = await asyncio.to_thread(MathChecker().verify, new_latex)
        if verification.claims_incorrect > 0:
            raise HTTPException(
                422,
                "Oppgaven ble ikke lagret — SymPy fant feil i fasiten.",
            )
        d["latex_content"] = new_latex

    for field, value in payload.items():
        d[field] = value
    await store.save(d, user_id=user_id)
    return _dict_to_out(d)


@router.delete(
    "/{exercise_id}",
    summary="Soft-delete an exercise",
)
async def delete_exercise(exercise_id: str, user_id: str = Depends(get_current_user)):
    d = await store.get(exercise_id)
    if not d or d.get("deleted") or not _user_owns(d, user_id):
        raise HTTPException(404, "Exercise not found")
    if not await store.soft_delete(exercise_id):
        raise HTTPException(404, "Exercise not found")
    return {"deleted": True}


@router.get(
    "/{exercise_id}/similar",
    response_model=list[ExerciseOut],
    summary="Find similar exercises (by content overlap)",
)
async def find_similar(exercise_id: str, limit: int = Query(5, ge=1, le=20), user_id: str = Depends(get_current_user)):
    """
    Find exercises most similar to the given one.

    In production, uses pgvector cosine similarity on embeddings.
    Placeholder: keyword overlap scoring.
    """
    target = await store.get(exercise_id)
    if not target or not _user_owns(target, user_id):
        raise HTTPException(404, "Exercise not found")

    target_kw = set(target.get("keywords", []))

    scored: list[tuple[float, dict]] = []
    for d in await store.list_active(user_id=user_id):
        if d["id"] == exercise_id:
            continue
        overlap = len(target_kw & set(d.get("keywords", [])))
        if overlap > 0:
            scored.append((overlap, d))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [_dict_to_out(d) for _, d in scored[:limit]]


@router.post("/{exercise_id}/variant", response_model=ExerciseOut, summary="Generate an AI variant of an exercise")
@limiter.limit("15/minute")
async def generate_variant(
    request: Request,
    exercise_id: str,
    req: VariantRequest,
    user_id: str = Depends(get_current_user),
) -> ExerciseOut:
    """Generate a new variant of an existing exercise using AI."""
    target = await store.get(exercise_id)
    if not target or not _user_owns(target, user_id):
        raise HTTPException(404, "Exercise not found")

    from app.models.llm import get_llm

    llm = get_llm(temperature=0.8)

    system_prompt = (
        "Du er en matematikklærer som lager varianter av oppgaver. "
        "Behold den matematiske strukturen, men endre tallene og/eller "
        "konteksten. Returner KUN LaTeX-koden for oppgaven, "
        "uten \\documentclass eller preamble."
    )
    user_prompt = (
        f"Lag en variant av denne oppgaven:\n\n"
        f"{target['latex_content']}\n\n"
        f"{f'Ekstra instruksjoner: {req.instructions}' if req.instructions else ''}"
    )

    variant_latex = await asyncio.to_thread(llm.invoke, system_prompt, user_prompt)
    from app.verification.math_checker import MathChecker

    verification = await asyncio.to_thread(MathChecker().verify, variant_latex)
    if verification.claims_incorrect > 0:
        logger.warning(
            "variant_blocked_incorrect_fasit",
            original_id=exercise_id,
            incorrect=verification.claims_incorrect,
        )
        raise HTTPException(
            422,
            "Varianten ble ikke lagret fordi fasitkontrollen fant matematiske feil.",
        )

    variant_id = uuid.uuid4().hex[:12]
    variant = {
        **target,
        "id": variant_id,
        "latex_content": variant_latex,
        "title": f"{target['title']} (variant)",
        "created_at": datetime.now().isoformat(),
        "times_used": 0,
        "user_rating": None,
        "source_generation_id": target.get("source_generation_id", ""),
        "owner_id": user_id,
    }
    await store.save(variant, user_id=user_id)

    logger.info("variant_generated", original_id=exercise_id, variant_id=variant_id)
    return _dict_to_out(variant)


@router.post("/export", response_model=ExportResponse, summary="Export selected exercises to PDF or Word")
@limiter.limit("15/minute")
async def export_exercises(
    request: Request,
    req: ExportRequest,
    user_id: str = Depends(get_current_user),
) -> ExportResponse:
    """Export selected exercises as a compiled PDF or Word document."""
    import base64

    exercises = []
    for eid in req.exercise_ids:
        d = await store.get(eid)
        if d and not d.get("deleted") and _user_owns(d, user_id):
            exercises.append(
                ParsedExercise(
                    id=d["id"],
                    title=d["title"],
                    number=d.get("number", 0),
                    latex_content=d["latex_content"],
                    solution=d.get("solution", ""),
                    difficulty=Difficulty(d.get("difficulty", "middels")),
                )
            )

    if not exercises:
        raise HTTPException(400, "No valid exercises found")

    body = exercises_to_latex(
        exercises,
        title=req.title,
        include_solutions=req.include_solutions,
    )
    full_doc = wrap_with_preamble(body)

    if req.format == "pdf":
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "export.pdf")
            pdf_path = await asyncio.to_thread(compile_to_pdf, full_doc, out_path)
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                return ExportResponse(
                    success=True,
                    content_base64=base64.b64encode(pdf_bytes).decode(),
                    filename="oppgaver.pdf",
                )
            else:
                return ExportResponse(
                    success=False,
                    errors=["PDF compilation failed"],
                )
    elif req.format == "docx":
        try:
            from app.export.word import latex_to_docx

            docx_bytes = await asyncio.to_thread(latex_to_docx, full_doc, req.title)
            return ExportResponse(
                success=True,
                content_base64=base64.b64encode(docx_bytes).decode(),
                filename="oppgaver.docx",
            )
        except ImportError:
            return ExportResponse(
                success=False,
                errors=["Word export not yet available"],
            )

    return ExportResponse(success=False, errors=[f"Unsupported format: {req.format}"])
