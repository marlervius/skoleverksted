"""PostgreSQL persistence for exercises (optional — falls back to file store)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import structlog

from app.config import get_settings

logger = structlog.get_logger()

_EXERCISE_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def db_id_for(local_id: str) -> uuid.UUID:
    """Deterministic UUID for a file-store exercise id."""
    return uuid.uuid5(_EXERCISE_NS, f"matematex-exercise:{local_id}")


def resolve_user_id(user_id: str) -> uuid.UUID | None:
    """Return a UUID suitable for FK writes, or None to skip DB."""
    if is_uuid(user_id):
        return uuid.UUID(user_id)
    settings = get_settings()
    if settings.dev_user_uuid and is_uuid(settings.dev_user_uuid):
        return uuid.UUID(settings.dev_user_uuid)
    return None


async def db_available() -> bool:
    settings = get_settings()
    if not settings.database_url:
        return False
    try:
        from app.db import get_pool

        await get_pool()
        return True
    except Exception as e:
        logger.debug("exercise_db_unavailable", error=str(e))
        return False


def _row_to_dict(row: Any) -> dict:
    hints = row["hints"]
    if isinstance(hints, str):
        hints = json.loads(hints)
    keywords = row["keywords"] or []
    sub_parts = row["sub_parts"] or []
    content_hash = row["content_hash"] or ""
    if content_hash.startswith("local:"):
        local_id = content_hash[6:]
    else:
        local_id = str(row["id"]).replace("-", "")[:12]
    return {
        "id": local_id,
        "db_id": str(row["id"]),
        "title": row["title"],
        "number": 0,
        "latex_content": row["latex_content"],
        "solution": row["solution"] or "",
        "hints": list(hints) if hints else [],
        "difficulty": row["difficulty"],
        "exercise_type": row["exercise_type"],
        "keywords": list(keywords),
        "has_figure": row["has_figure"],
        "sub_parts": list(sub_parts),
        "topic": row["topic"] or "",
        "grade_level": row["grade_level"] or "",
        "source_generation_id": str(row["source_generation_id"] or row["generation_id"] or ""),
        "times_used": row["times_used"] or row["use_count"] or 0,
        "user_rating": row["user_rating"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else "",
        "owner_id": str(row["user_id"]),
        "deleted": row["deleted_at"] is not None,
    }


async def save(exercise: dict, *, user_id: str) -> dict | None:
    uid = resolve_user_id(user_id)
    if uid is None or not await db_available():
        return None

    from app.db import get_pool

    pool = await get_pool()
    local_id = exercise["id"]
    row_id = db_id_for(local_id)

    gen_id = exercise.get("source_generation_id") or exercise.get("generation_id") or ""
    generation_id = uuid.UUID(gen_id) if gen_id and is_uuid(gen_id) else None

    hints = json.dumps(exercise.get("hints") or [])
    keywords = exercise.get("keywords") or []
    sub_parts = exercise.get("sub_parts") or []

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO exercises (
                id, user_id, generation_id, source_generation_id,
                title, topic, grade_level, difficulty, exercise_type,
                latex_content, solution, hints, keywords,
                has_figure, sub_parts, times_used, user_rating,
                content_hash, deleted_at, created_at
            ) VALUES (
                $1, $2, $3, $3,
                $4, $5, $6, $7, $8,
                $9, $10, $11::jsonb, $12,
                $13, $14, $15, $16,
                $17, NULL, COALESCE($18::timestamptz, now())
            )
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                topic = EXCLUDED.topic,
                grade_level = EXCLUDED.grade_level,
                difficulty = EXCLUDED.difficulty,
                exercise_type = EXCLUDED.exercise_type,
                latex_content = EXCLUDED.latex_content,
                solution = EXCLUDED.solution,
                hints = EXCLUDED.hints,
                keywords = EXCLUDED.keywords,
                has_figure = EXCLUDED.has_figure,
                sub_parts = EXCLUDED.sub_parts,
                times_used = EXCLUDED.times_used,
                user_rating = EXCLUDED.user_rating,
                content_hash = EXCLUDED.content_hash,
                deleted_at = EXCLUDED.deleted_at,
                updated_at = now()
            """,
            row_id,
            uid,
            generation_id,
            exercise.get("title", "Oppgave"),
            exercise.get("topic", ""),
            exercise.get("grade_level", ""),
            exercise.get("difficulty", "middels"),
            exercise.get("exercise_type", "standard"),
            exercise["latex_content"],
            exercise.get("solution", ""),
            hints,
            keywords,
            exercise.get("has_figure", False),
            sub_parts,
            exercise.get("times_used", 0),
            exercise.get("user_rating"),
            f"local:{local_id}",
            exercise.get("created_at") or None,
        )
    logger.debug("exercise_db_saved", local_id=local_id, db_id=str(row_id))
    return exercise


async def get(exercise_id: str) -> dict | None:
    if not await db_available():
        return None

    from app.db import get_pool

    pool = await get_pool()
    row_id = db_id_for(exercise_id) if not is_uuid(exercise_id) else uuid.UUID(exercise_id)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM exercises
            WHERE id = $1 OR content_hash = $2
            LIMIT 1
            """,
            row_id,
            f"local:{exercise_id}",
        )
    if not row or row["deleted_at"] is not None:
        return None
    return _row_to_dict(row)


async def list_active(*, user_id: str | None = None) -> list[dict]:
    if not await db_available():
        return []

    from app.db import get_pool

    pool = await get_pool()
    uid = resolve_user_id(user_id) if user_id else None

    async with pool.acquire() as conn:
        if not uid:
            return []
        rows = await conn.fetch(
            """
            SELECT * FROM exercises
            WHERE deleted_at IS NULL AND user_id = $1
            ORDER BY created_at DESC
            """,
            uid,
        )
    return [_row_to_dict(r) for r in rows]


async def soft_delete(exercise_id: str) -> bool:
    if not await db_available():
        return False

    from app.db import get_pool

    pool = await get_pool()
    row_id = db_id_for(exercise_id) if not is_uuid(exercise_id) else uuid.UUID(exercise_id)

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE exercises SET deleted_at = now(), updated_at = now()
            WHERE (id = $1 OR content_hash = $2) AND deleted_at IS NULL
            """,
            row_id,
            f"local:{exercise_id}",
        )
    return result.endswith("1")
