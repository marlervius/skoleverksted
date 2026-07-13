"""Persistent share-link store — memory cache with disk JSON backing."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from app.config import get_settings
from app.stores.fs_utils import atomic_write_json

logger = structlog.get_logger()

_links: dict[str, dict] = {}
_loaded = False


def _store_path() -> Path:
    d = Path(get_settings().output_dir) / "sharing"
    d.mkdir(parents=True, exist_ok=True)
    return d / "links.json"


def _ensure_loaded() -> None:
    global _loaded, _links
    if _loaded:
        return
    path = _store_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _links = data
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("sharing_store_load_failed", error=str(e))
    _loaded = True


def all_links() -> dict[str, dict]:
    _ensure_loaded()
    return _links


def get_link(token: str) -> dict | None:
    _ensure_loaded()
    return _links.get(token)


def save_link(token: str, link: dict) -> None:
    _ensure_loaded()
    _links[token] = link
    try:
        atomic_write_json(_store_path(), _links)
    except OSError as e:
        logger.warning("sharing_store_persist_failed", token=token[:8], error=str(e))
