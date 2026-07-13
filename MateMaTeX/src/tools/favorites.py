"""
Favorites System for MateMaTeX.
Save and manage favorite generations.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict


# Storage directory
FAVORITES_DIR = Path(__file__).parent.parent.parent / "data" / "favorites"


@dataclass
class Favorite:
    """Represents a saved favorite."""
    id: str
    name: str
    topic: str
    grade_level: str
    material_type: str
    created_at: str
    last_accessed: str
    access_count: int
    tags: list[str]
    notes: str
    latex_content: str
    pdf_path: Optional[str]
    rating: int  # 1-5 stars
    is_pinned: bool


def ensure_favorites_dir():
    """Ensure the favorites directory exists."""
    FAVORITES_DIR.mkdir(parents=True, exist_ok=True)


def get_favorites_file() -> Path:
    """Get path to favorites JSON file."""
    ensure_favorites_dir()
    return FAVORITES_DIR / "favorites.json"


def load_favorites() -> list[Favorite]:
    """
    Load all favorites from file.
    
    Returns:
        List of Favorite objects.
    """
    favorites_file = get_favorites_file()
    
    if not favorites_file.exists():
        return []
    
    try:
        with open(favorites_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return [Favorite(**f) for f in data]
    except (json.JSONDecodeError, IOError, TypeError):
        return []


def save_favorites(favorites: list[Favorite]) -> bool:
    """
    Save favorites to file.
    
    Args:
        favorites: List of Favorite objects.
    
    Returns:
        True if successful.
    """
    favorites_file = get_favorites_file()
    
    try:
        data = [asdict(f) for f in favorites]
        with open(favorites_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def add_favorite(
    name: str,
    topic: str,
    grade_level: str,
    material_type: str,
    latex_content: str,
    pdf_path: Optional[str] = None,
    tags: Optional[list[str]] = None,
    notes: str = "",
    rating: int = 3
) -> Favorite:
    """
    Add a new favorite.
    
    Args:
        name: Display name for the favorite.
        topic: Math topic.
        grade_level: Grade level.
        material_type: Type of material.
        latex_content: The LaTeX source code.
        pdf_path: Optional path to PDF file.
        tags: Optional tags for categorization.
        notes: Optional notes.
        rating: Star rating (1-5).
    
    Returns:
        The created Favorite object.
    """
    favorite_id = f"fav_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    now = datetime.now().isoformat()
    
    favorite = Favorite(
        id=favorite_id,
        name=name,
        topic=topic,
        grade_level=grade_level,
        material_type=material_type,
        created_at=now,
        last_accessed=now,
        access_count=0,
        tags=tags or [],
        notes=notes,
        latex_content=latex_content,
        pdf_path=pdf_path,
        rating=min(max(rating, 1), 5),
        is_pinned=False
    )
    
    favorites = load_favorites()
    favorites.insert(0, favorite)  # Add at beginning
    save_favorites(favorites)
    
    return favorite


def get_favorite(favorite_id: str) -> Optional[Favorite]:
    """
    Get a favorite by ID and update access count.
    
    Args:
        favorite_id: Favorite ID.
    
    Returns:
        Favorite object or None.
    """
    favorites = load_favorites()
    
    for i, f in enumerate(favorites):
        if f.id == favorite_id:
            # Update access info
            f.last_accessed = datetime.now().isoformat()
            f.access_count += 1
            favorites[i] = f
            save_favorites(favorites)
            return f
    
    return None


def update_favorite(
    favorite_id: str,
    name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    notes: Optional[str] = None,
    rating: Optional[int] = None,
    is_pinned: Optional[bool] = None
) -> Optional[Favorite]:
    """
    Update a favorite.
    
    Args:
        favorite_id: Favorite ID.
        name: New name (optional).
        tags: New tags (optional).
        notes: New notes (optional).
        rating: New rating (optional).
        is_pinned: New pinned status (optional).
    
    Returns:
        Updated Favorite or None.
    """
    favorites = load_favorites()
    
    for i, f in enumerate(favorites):
        if f.id == favorite_id:
            if name is not None:
                f.name = name
            if tags is not None:
                f.tags = tags
            if notes is not None:
                f.notes = notes
            if rating is not None:
                f.rating = min(max(rating, 1), 5)
            if is_pinned is not None:
                f.is_pinned = is_pinned
            
            favorites[i] = f
            save_favorites(favorites)
            return f
    
    return None


def delete_favorite(favorite_id: str) -> bool:
    """
    Delete a favorite.
    
    Args:
        favorite_id: Favorite ID.
    
    Returns:
        True if deleted.
    """
    favorites = load_favorites()
    
    for i, f in enumerate(favorites):
        if f.id == favorite_id:
            favorites.pop(i)
            save_favorites(favorites)
            return True
    
    return False


def toggle_pin(favorite_id: str) -> Optional[bool]:
    """
    Toggle pinned status of a favorite.
    
    Args:
        favorite_id: Favorite ID.
    
    Returns:
        New pinned status or None if not found.
    """
    favorites = load_favorites()
    
    for i, f in enumerate(favorites):
        if f.id == favorite_id:
            f.is_pinned = not f.is_pinned
            favorites[i] = f
            save_favorites(favorites)
            return f.is_pinned
    
    return None


def get_pinned_favorites() -> list[Favorite]:
    """Get all pinned favorites."""
    return [f for f in load_favorites() if f.is_pinned]


def get_recent_favorites(limit: int = 5) -> list[Favorite]:
    """Get recently accessed favorites."""
    favorites = load_favorites()
    favorites.sort(key=lambda f: f.last_accessed, reverse=True)
    return favorites[:limit]


def get_top_rated_favorites(limit: int = 5) -> list[Favorite]:
    """Get top-rated favorites."""
    favorites = load_favorites()
    favorites.sort(key=lambda f: (f.rating, f.access_count), reverse=True)
    return favorites[:limit]


def get_most_used_favorites(limit: int = 5) -> list[Favorite]:
    """Get most frequently used favorites."""
    favorites = load_favorites()
    favorites.sort(key=lambda f: f.access_count, reverse=True)
    return favorites[:limit]


def search_favorites(query: str) -> list[Favorite]:
    """
    Search favorites by name, topic, or tags.
    
    Args:
        query: Search query.
    
    Returns:
        Matching favorites.
    """
    query_lower = query.lower()
    favorites = load_favorites()
    
    results = []
    for f in favorites:
        if (query_lower in f.name.lower() or
            query_lower in f.topic.lower() or
            query_lower in f.notes.lower() or
            any(query_lower in tag.lower() for tag in f.tags)):
            results.append(f)
    
    return results


def get_favorites_by_grade(grade_level: str) -> list[Favorite]:
    """Get favorites for a specific grade level."""
    return [f for f in load_favorites() if grade_level.lower() in f.grade_level.lower()]


def get_favorites_by_tag(tag: str) -> list[Favorite]:
    """Get favorites with a specific tag."""
    tag_lower = tag.lower()
    return [f for f in load_favorites() if any(tag_lower in t.lower() for t in f.tags)]


def get_all_tags() -> list[str]:
    """Get all unique tags from favorites."""
    tags = set()
    for f in load_favorites():
        tags.update(f.tags)
    return sorted(list(tags))


def get_favorites_stats() -> dict:
    """
    Get statistics about favorites.
    
    Returns:
        Dictionary with stats.
    """
    favorites = load_favorites()
    
    if not favorites:
        return {
            "total": 0,
            "pinned": 0,
            "avg_rating": 0,
            "total_accesses": 0,
            "by_grade": {},
            "by_type": {},
        }
    
    by_grade = {}
    by_type = {}
    
    for f in favorites:
        by_grade[f.grade_level] = by_grade.get(f.grade_level, 0) + 1
        by_type[f.material_type] = by_type.get(f.material_type, 0) + 1
    
    return {
        "total": len(favorites),
        "pinned": sum(1 for f in favorites if f.is_pinned),
        "avg_rating": sum(f.rating for f in favorites) / len(favorites),
        "total_accesses": sum(f.access_count for f in favorites),
        "by_grade": by_grade,
        "by_type": by_type,
    }


def render_star_rating(rating: int) -> str:
    """
    Render star rating as string.
    
    Args:
        rating: Rating 1-5.
    
    Returns:
        Star string.
    """
    filled = "⭐" * rating
    empty = "☆" * (5 - rating)
    return filled + empty


def format_favorite_card(favorite: Favorite) -> str:
    """
    Format a favorite as a display card.
    
    Args:
        favorite: Favorite object.
    
    Returns:
        Formatted string.
    """
    pin = "📌 " if favorite.is_pinned else ""
    stars = render_star_rating(favorite.rating)
    tags = " ".join(f"#{t}" for t in favorite.tags[:3]) if favorite.tags else ""
    
    return f"""{pin}**{favorite.name}**
{stars} | {favorite.topic} | {favorite.grade_level}
{tags}
_Brukt {favorite.access_count} ganger_"""
