"""Persistent exercise store — memory cache with disk JSON backing and optional PostgreSQL."""

from __future__ import annotations

import json
import re
from pathlib import Path

import structlog

from app.config import get_settings
from app.stores.fs_utils import atomic_write_json

logger = structlog.get_logger()

_memory: dict[str, dict] = {}
_loaded = False

_EXERCISE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _store_dir() -> Path:
    d = Path(get_settings().output_dir) / "exercise_store"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    for path in _store_dir().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("id"):
                _memory[data["id"]] = data
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("exercise_store_load_failed", path=str(path), error=str(e))
    _loaded = True


def _persist_one(exercise: dict) -> None:
    eid = exercise.get("id", "")
    if not eid or not _EXERCISE_ID_RE.match(eid):
        logger.warning("exercise_store_rejected_unsafe_id", id=eid)
        return
    path = _store_dir() / f"{eid}.json"
    atomic_write_json(path, exercise)


def _save_file(exercise: dict) -> dict:
    _ensure_loaded()
    _memory[exercise["id"]] = exercise
    try:
        _persist_one(exercise)
    except OSError as e:
        logger.warning("exercise_store_persist_failed", id=exercise["id"], error=str(e))
    return exercise


async def save(exercise: dict, *, user_id: str = "anonymous") -> dict:
    _save_file(exercise)
    try:
        from app.repositories import exercise_db

        await exercise_db.save(exercise, user_id=user_id)
    except Exception as e:
        logger.debug("exercise_db_mirror_failed", id=exercise.get("id"), error=str(e))
    return exercise


def save_sync(exercise: dict) -> dict:
    """Sync save without DB mirror (legacy callers)."""
    return _save_file(exercise)


async def get(exercise_id: str) -> dict | None:
    try:
        from app.repositories import exercise_db

        db_row = await exercise_db.get(exercise_id)
        if db_row:
            return db_row
    except Exception as e:
        logger.debug("exercise_db_get_failed", id=exercise_id, error=str(e))

    _ensure_loaded()
    d = _memory.get(exercise_id)
    if d and not d.get("deleted"):
        return d
    return None


async def list_active(*, user_id: str | None = None) -> list[dict]:
    _ensure_loaded()
    file_items = [d for d in _memory.values() if not d.get("deleted")]
    if user_id and user_id not in ("anonymous", "api-user"):
        file_items = [
            d for d in file_items
            if d.get("owner_id", user_id) == user_id or not d.get("owner_id")
        ]

    try:
        from app.repositories import exercise_db

        db_items = await exercise_db.list_active(user_id=user_id)
        if db_items:
            by_id = {d["id"]: d for d in file_items}
            for row in db_items:
                by_id[row["id"]] = row
            return list(by_id.values())
    except Exception as e:
        logger.debug("exercise_db_list_failed", error=str(e))

    return file_items


async def soft_delete(exercise_id: str) -> bool:
    deleted = False
    try:
        from app.repositories import exercise_db

        deleted = await exercise_db.soft_delete(exercise_id)
    except Exception as e:
        logger.debug("exercise_db_delete_failed", id=exercise_id, error=str(e))

    _ensure_loaded()
    d = _memory.get(exercise_id)
    if d:
        d["deleted"] = True
        try:
            _persist_one(d)
        except OSError:
            pass
        deleted = True
    return deleted
