"""
Content Index for MateMaTeX.
Stores lightweight metadata (folder assignment) per content item (favorite/exercise/history/template).
"""

import json
from pathlib import Path
from typing import Optional


DATA_DIR = Path(__file__).parent.parent.parent / "data"
INDEX_FILE = DATA_DIR / "content_index.json"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_content_index() -> dict:
    """Load content index from disk."""
    _ensure_data_dir()
    if not INDEX_FILE.exists():
        return {"favorite": {}, "exercise": {}, "history": {}, "template": {}}
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure all keys exist
        for k in ("favorite", "exercise", "history", "template"):
            data.setdefault(k, {})
        return data
    except (json.JSONDecodeError, IOError, TypeError):
        return {"favorite": {}, "exercise": {}, "history": {}, "template": {}}


def save_content_index(index: dict) -> bool:
    """Save content index to disk."""
    _ensure_data_dir()
    try:
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def get_item_folder(item_type: str, item_id: str) -> Optional[str]:
    """Get folder_id for an item."""
    index = load_content_index()
    item = index.get(item_type, {}).get(item_id, {})
    return item.get("folder_id")


def set_item_folder(item_type: str, item_id: str, folder_id: Optional[str]) -> None:
    """Assign an item to a folder (or clear if folder_id is None)."""
    index = load_content_index()
    index.setdefault(item_type, {})
    index[item_type].setdefault(item_id, {})
    if folder_id:
        index[item_type][item_id]["folder_id"] = folder_id
    else:
        index[item_type][item_id].pop("folder_id", None)
    save_content_index(index)


def remove_item_from_index(item_type: str, item_id: str) -> None:
    """Remove an item from the index."""
    index = load_content_index()
    if item_type in index and item_id in index[item_type]:
        index[item_type].pop(item_id, None)
        save_content_index(index)


def get_folder_counts() -> dict[str, int]:
    """Compute folder_id -> count across all indexed item types."""
    index = load_content_index()
    counts: dict[str, int] = {}
    for item_type in ("favorite", "exercise", "history", "template"):
        for _, meta in index.get(item_type, {}).items():
            fid = meta.get("folder_id")
            if fid:
                counts[fid] = counts.get(fid, 0) + 1
    return counts


def filter_by_folder(item_type: str, item_id: str, folder_id: Optional[str]) -> bool:
    """Return True if the item matches the selected folder filter."""
    if not folder_id:
        return True
    return get_item_folder(item_type, item_id) == folder_id

