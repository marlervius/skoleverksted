"""
Persistent storage for MateMaTeX.
Handles saving and loading history, settings, and generated content.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


# Storage directory
STORAGE_DIR = Path(__file__).parent.parent / "data"
HISTORY_FILE = STORAGE_DIR / "history.json"
SETTINGS_FILE = STORAGE_DIR / "settings.json"


def ensure_storage_dir():
    """Ensure the storage directory exists."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def load_history() -> list[dict]:
    """
    Load generation history from file.
    
    Returns:
        List of history entries, newest first.
    """
    ensure_storage_dir()
    
    if not HISTORY_FILE.exists():
        return []
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        return history
    except (json.JSONDecodeError, IOError):
        return []


def save_history(history: list[dict]) -> bool:
    """
    Save generation history to file.
    
    Args:
        history: List of history entries.
    
    Returns:
        True if successful, False otherwise.
    """
    ensure_storage_dir()
    
    try:
        # Keep only the last 50 entries
        history = history[:50]
        
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def add_to_history(
    topic: str,
    grade: str,
    material_type: str,
    tex_content: str,
    pdf_path: Optional[str] = None,
    settings: Optional[dict] = None
) -> dict:
    """
    Add a new entry to history.
    
    Args:
        topic: The math topic.
        grade: Grade level.
        material_type: Type of material generated.
        tex_content: The LaTeX content.
        pdf_path: Path to generated PDF (if any).
        settings: Generation settings used.
    
    Returns:
        The new history entry.
    """
    history = load_history()
    
    # Create unique ID (UUID avoids collisions on rapid generations)
    entry_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    
    # Save LaTeX content to file
    tex_file = STORAGE_DIR / f"{entry_id}.tex"
    try:
        with open(tex_file, "w", encoding="utf-8") as f:
            f.write(tex_content)
    except IOError:
        tex_file = None
    
    entry = {
        "id": entry_id,
        "topic": topic,
        "grade": grade,
        "material_type": material_type,
        "timestamp": datetime.now().isoformat(),
        "tex_file": str(tex_file) if tex_file else None,
        "pdf_path": pdf_path,
        "settings": settings or {},
    }
    
    # Add to beginning of list
    history.insert(0, entry)
    save_history(history)
    
    return entry


def get_history_entry(entry_id: str) -> Optional[dict]:
    """
    Get a specific history entry by ID.
    
    Args:
        entry_id: The entry ID.
    
    Returns:
        The history entry or None.
    """
    history = load_history()
    
    for entry in history:
        if entry.get("id") == entry_id:
            return entry
    
    return None


def get_tex_content(entry_id: str) -> Optional[str]:
    """
    Get the LaTeX content for a history entry.
    
    Args:
        entry_id: The entry ID.
    
    Returns:
        The LaTeX content or None.
    """
    entry = get_history_entry(entry_id)
    
    if not entry:
        return None
    
    tex_file = entry.get("tex_file")
    if not tex_file or not Path(tex_file).exists():
        return None
    
    try:
        with open(tex_file, "r", encoding="utf-8") as f:
            return f.read()
    except IOError:
        return None


def delete_history_entry(entry_id: str) -> bool:
    """
    Delete a history entry and its associated files.
    
    Args:
        entry_id: The entry ID.
    
    Returns:
        True if successful.
    """
    history = load_history()
    
    # Find and remove entry
    for i, entry in enumerate(history):
        if entry.get("id") == entry_id:
            # Delete associated files
            tex_file = entry.get("tex_file")
            if tex_file and Path(tex_file).exists():
                try:
                    Path(tex_file).unlink()
                except IOError:
                    pass
            
            # Remove from list
            history.pop(i)
            save_history(history)
            return True
    
    return False


def clear_history() -> bool:
    """
    Clear all history entries.
    
    Returns:
        True if successful.
    """
    ensure_storage_dir()
    
    # Delete all .tex files in storage
    for tex_file in STORAGE_DIR.glob("*.tex"):
        try:
            tex_file.unlink()
        except IOError:
            pass
    
    # Clear history file
    return save_history([])


def load_settings() -> dict:
    """
    Load user settings.
    
    Returns:
        Settings dictionary.
    """
    ensure_storage_dir()
    
    defaults = {
        "language": "no",  # no = Norwegian, en = English
        "theme": "dark",
        "default_grade": "10. trinn",
        "default_exercises": 10,
        "auto_save": True,
    }
    
    if not SETTINGS_FILE.exists():
        return defaults
    
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
        # Merge with defaults for any missing keys
        return {**defaults, **settings}
    except (json.JSONDecodeError, IOError):
        return defaults


def save_settings(settings: dict) -> bool:
    """
    Save user settings.
    
    Args:
        settings: Settings dictionary.
    
    Returns:
        True if successful.
    """
    ensure_storage_dir()
    
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False
