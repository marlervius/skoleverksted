"""Persistent collaboration data — school bank, comments, versions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from app.config import get_settings
from app.stores.fs_utils import atomic_write_json

logger = structlog.get_logger()

_school: dict[str, dict] = {}
_comments: dict[str, list[dict]] = {}
_versions: dict[str, list[dict]] = {}
_loaded = False


def _base_dir() -> Path:
    d = Path(get_settings().output_dir) / "collaboration"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_json(name: str, default: Any) -> Any:
    path = _base_dir() / f"{name}.json"
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("collab_load_failed", file=name, error=str(e))
        return default


def _save_json(name: str, data: Any) -> None:
    atomic_write_json(_base_dir() / f"{name}.json", data)


def _ensure_loaded() -> None:
    global _loaded, _school, _comments, _versions
    if _loaded:
        return
    _school = _load_json("school_exercises", {})
    _comments = _load_json("comments", {})
    _versions = _load_json("versions", {})
    _loaded = True


def school_exercises() -> dict[str, dict]:
    _ensure_loaded()
    return _school


def save_school_exercises() -> None:
    _ensure_loaded()
    _save_json("school_exercises", _school)


def comments_for(generation_id: str) -> list[dict]:
    _ensure_loaded()
    return _comments.get(generation_id, [])


def add_comment(generation_id: str, comment: dict) -> None:
    _ensure_loaded()
    _comments.setdefault(generation_id, []).append(comment)
    _save_json("comments", _comments)


def all_comments(generation_id: str) -> list[dict]:
    _ensure_loaded()
    return list(_comments.get(generation_id, []))


def versions_for(generation_id: str) -> list[dict]:
    _ensure_loaded()
    return list(_versions.get(generation_id, []))


def add_version(generation_id: str, version: dict) -> None:
    _ensure_loaded()
    _versions.setdefault(generation_id, []).append(version)
    _save_json("versions", _versions)


def all_versions(generation_id: str) -> list[dict]:
    _ensure_loaded()
    return list(_versions.get(generation_id, []))
