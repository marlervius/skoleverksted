"""
Organization tools for MateMaTeX.
Provides folders and tags for organizing content.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict, field


# Storage paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
FOLDERS_FILE = DATA_DIR / "folders.json"
TAGS_FILE = DATA_DIR / "tags.json"


@dataclass
class Folder:
    """Represents a folder for organizing content."""
    id: str
    name: str
    description: str
    color: str  # Hex color
    icon: str  # Emoji
    parent_id: Optional[str]  # For nested folders
    created_at: str
    item_count: int = 0


@dataclass
class Tag:
    """Represents a tag for categorizing content."""
    id: str
    name: str
    color: str  # Hex color
    usage_count: int = 0


@dataclass
class ContentItem:
    """Represents an item that can be organized."""
    id: str
    type: str  # "favorite", "exercise", "history"
    folder_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)


def ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# FOLDER MANAGEMENT
# ============================================================================

def load_folders() -> list[Folder]:
    """Load all folders from file."""
    ensure_data_dir()
    
    if not FOLDERS_FILE.exists():
        return []
    
    try:
        with open(FOLDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Folder(**folder) for folder in data]
    except (json.JSONDecodeError, IOError, TypeError):
        return []


def save_folders(folders: list[Folder]) -> bool:
    """Save folders to file."""
    ensure_data_dir()
    
    try:
        data = [asdict(folder) for folder in folders]
        with open(FOLDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def create_folder(
    name: str,
    description: str = "",
    color: str = "#f0b429",
    icon: str = "📁",
    parent_id: Optional[str] = None
) -> Folder:
    """Create a new folder."""
    folder_id = f"folder_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(load_folders())}"
    
    folder = Folder(
        id=folder_id,
        name=name,
        description=description,
        color=color,
        icon=icon,
        parent_id=parent_id,
        created_at=datetime.now().isoformat(),
        item_count=0
    )
    
    folders = load_folders()
    folders.append(folder)
    save_folders(folders)
    
    return folder


def get_folder(folder_id: str) -> Optional[Folder]:
    """Get a folder by ID."""
    folders = load_folders()
    for folder in folders:
        if folder.id == folder_id:
            return folder
    return None


def update_folder(
    folder_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None
) -> Optional[Folder]:
    """Update a folder."""
    folders = load_folders()
    
    for i, folder in enumerate(folders):
        if folder.id == folder_id:
            if name is not None:
                folder.name = name
            if description is not None:
                folder.description = description
            if color is not None:
                folder.color = color
            if icon is not None:
                folder.icon = icon
            
            folders[i] = folder
            save_folders(folders)
            return folder
    
    return None


def delete_folder(folder_id: str) -> bool:
    """Delete a folder."""
    folders = load_folders()
    
    for i, folder in enumerate(folders):
        if folder.id == folder_id:
            folders.pop(i)
            save_folders(folders)
            return True
    
    return False


def get_child_folders(parent_id: Optional[str] = None) -> list[Folder]:
    """Get folders that are children of the specified parent."""
    folders = load_folders()
    return [f for f in folders if f.parent_id == parent_id]


def get_folder_path(folder_id: str) -> list[Folder]:
    """Get the full path from root to the specified folder."""
    path = []
    current = get_folder(folder_id)
    
    while current:
        path.insert(0, current)
        if current.parent_id:
            current = get_folder(current.parent_id)
        else:
            break
    
    return path


def increment_folder_count(folder_id: str) -> None:
    """Increment the item count for a folder."""
    folders = load_folders()
    
    for i, folder in enumerate(folders):
        if folder.id == folder_id:
            folder.item_count += 1
            folders[i] = folder
            save_folders(folders)
            return


def decrement_folder_count(folder_id: str) -> None:
    """Decrement the item count for a folder."""
    folders = load_folders()
    
    for i, folder in enumerate(folders):
        if folder.id == folder_id:
            folder.item_count = max(0, folder.item_count - 1)
            folders[i] = folder
            save_folders(folders)
            return


# ============================================================================
# TAG MANAGEMENT
# ============================================================================

def load_tags() -> list[Tag]:
    """Load all tags from file."""
    ensure_data_dir()
    
    if not TAGS_FILE.exists():
        # Return default tags
        return [
            Tag(id="tag_algebra", name="Algebra", color="#3b82f6", usage_count=0),
            Tag(id="tag_geometry", name="Geometri", color="#10b981", usage_count=0),
            Tag(id="tag_statistics", name="Statistikk", color="#f59e0b", usage_count=0),
            Tag(id="tag_functions", name="Funksjoner", color="#8b5cf6", usage_count=0),
            Tag(id="tag_equations", name="Likninger", color="#ec4899", usage_count=0),
            Tag(id="tag_fractions", name="Brøk", color="#06b6d4", usage_count=0),
        ]
    
    try:
        with open(TAGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Tag(**tag) for tag in data]
    except (json.JSONDecodeError, IOError, TypeError):
        return []


def save_tags(tags: list[Tag]) -> bool:
    """Save tags to file."""
    ensure_data_dir()
    
    try:
        data = [asdict(tag) for tag in tags]
        with open(TAGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def create_tag(name: str, color: str = "#6b7280") -> Tag:
    """Create a new tag."""
    tag_id = f"tag_{name.lower().replace(' ', '_')}_{len(load_tags())}"
    
    tag = Tag(
        id=tag_id,
        name=name,
        color=color,
        usage_count=0
    )
    
    tags = load_tags()
    tags.append(tag)
    save_tags(tags)
    
    return tag


def get_tag(tag_id: str) -> Optional[Tag]:
    """Get a tag by ID."""
    tags = load_tags()
    for tag in tags:
        if tag.id == tag_id:
            return tag
    return None


def get_tag_by_name(name: str) -> Optional[Tag]:
    """Get a tag by name."""
    tags = load_tags()
    for tag in tags:
        if tag.name.lower() == name.lower():
            return tag
    return None


def update_tag(
    tag_id: str,
    name: Optional[str] = None,
    color: Optional[str] = None
) -> Optional[Tag]:
    """Update a tag."""
    tags = load_tags()
    
    for i, tag in enumerate(tags):
        if tag.id == tag_id:
            if name is not None:
                tag.name = name
            if color is not None:
                tag.color = color
            
            tags[i] = tag
            save_tags(tags)
            return tag
    
    return None


def delete_tag(tag_id: str) -> bool:
    """Delete a tag."""
    tags = load_tags()
    
    for i, tag in enumerate(tags):
        if tag.id == tag_id:
            tags.pop(i)
            save_tags(tags)
            return True
    
    return False


def increment_tag_usage(tag_id: str) -> None:
    """Increment usage count for a tag."""
    tags = load_tags()
    
    for i, tag in enumerate(tags):
        if tag.id == tag_id:
            tag.usage_count += 1
            tags[i] = tag
            save_tags(tags)
            return


def get_popular_tags(limit: int = 10) -> list[Tag]:
    """Get most used tags."""
    tags = load_tags()
    tags.sort(key=lambda t: t.usage_count, reverse=True)
    return tags[:limit]


def search_tags(query: str) -> list[Tag]:
    """Search tags by name."""
    tags = load_tags()
    query_lower = query.lower()
    return [t for t in tags if query_lower in t.name.lower()]


# ============================================================================
# UI HELPERS
# ============================================================================

def render_folder_badge(folder: Folder) -> str:
    """Render a folder as an HTML badge."""
    return f"""
    <span style="
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.25rem 0.5rem;
        background: {folder.color}20;
        border: 1px solid {folder.color}40;
        border-radius: 6px;
        font-size: 0.75rem;
        color: {folder.color};
    ">
        {folder.icon} {folder.name}
    </span>
    """


def render_tag_badge(tag: Tag) -> str:
    """Render a tag as an HTML badge."""
    return f"""
    <span style="
        display: inline-flex;
        align-items: center;
        padding: 0.2rem 0.5rem;
        background: {tag.color}20;
        border-radius: 12px;
        font-size: 0.7rem;
        color: {tag.color};
    ">
        {tag.name}
    </span>
    """


def render_tags_row(tag_ids: list[str]) -> str:
    """Render multiple tags in a row."""
    tags = [get_tag(tid) for tid in tag_ids]
    tags = [t for t in tags if t is not None]
    
    if not tags:
        return ""
    
    badges = " ".join([render_tag_badge(t) for t in tags])
    return f'<div style="display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.25rem;">{badges}</div>'


# Color options for UI
FOLDER_COLORS = [
    "#f0b429",  # Gold
    "#10b981",  # Green
    "#3b82f6",  # Blue
    "#8b5cf6",  # Purple
    "#ec4899",  # Pink
    "#f59e0b",  # Orange
    "#06b6d4",  # Cyan
    "#ef4444",  # Red
]

FOLDER_ICONS = [
    "📁", "📂", "📚", "📖", "📝", "📋", 
    "🎯", "⚡", "🔥", "💡", "🎓", "📊"
]

TAG_COLORS = [
    "#3b82f6",  # Blue
    "#10b981",  # Green
    "#f59e0b",  # Orange
    "#8b5cf6",  # Purple
    "#ec4899",  # Pink
    "#06b6d4",  # Cyan
    "#ef4444",  # Red
    "#6b7280",  # Gray
]
