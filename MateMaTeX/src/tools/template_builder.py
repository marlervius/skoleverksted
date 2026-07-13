"""
Template Builder for MateMaTeX.
Create, save, and manage custom templates.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict


# Template storage directory
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "data" / "templates"


@dataclass
class CustomTemplate:
    """Represents a custom template."""
    id: str
    name: str
    emoji: str
    description: str
    created_at: str
    updated_at: str
    config: dict
    tags: list[str]
    usage_count: int = 0


# Default template configurations
DEFAULT_CONFIG = {
    "material_type": "arbeidsark",
    "include_theory": True,
    "include_examples": True,
    "include_exercises": True,
    "include_solutions": True,
    "include_graphs": True,
    "include_tips": False,
    "num_exercises": 10,
    "difficulty": "middels",
    "exercise_types": ["standard"],
}


def ensure_templates_dir():
    """Ensure the templates directory exists."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def get_templates_file() -> Path:
    """Get path to templates JSON file."""
    ensure_templates_dir()
    return TEMPLATES_DIR / "custom_templates.json"


def load_custom_templates() -> list[CustomTemplate]:
    """
    Load all custom templates.
    
    Returns:
        List of CustomTemplate objects.
    """
    templates_file = get_templates_file()
    
    if not templates_file.exists():
        return []
    
    try:
        with open(templates_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return [CustomTemplate(**t) for t in data]
    except (json.JSONDecodeError, IOError, TypeError):
        return []


def save_custom_templates(templates: list[CustomTemplate]) -> bool:
    """
    Save custom templates to file.
    
    Args:
        templates: List of CustomTemplate objects.
    
    Returns:
        True if successful.
    """
    templates_file = get_templates_file()
    
    try:
        data = [asdict(t) for t in templates]
        with open(templates_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def create_template(
    name: str,
    description: str,
    config: dict,
    emoji: str = "📄",
    tags: Optional[list[str]] = None
) -> CustomTemplate:
    """
    Create a new custom template.
    
    Args:
        name: Template name.
        description: Short description.
        config: Template configuration.
        emoji: Display emoji.
        tags: Optional tags for categorization.
    
    Returns:
        The created CustomTemplate.
    """
    # Generate unique ID
    template_id = f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Merge with defaults
    full_config = {**DEFAULT_CONFIG, **config}
    
    template = CustomTemplate(
        id=template_id,
        name=name,
        emoji=emoji,
        description=description,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        config=full_config,
        tags=tags or [],
        usage_count=0,
    )
    
    # Save to file
    templates = load_custom_templates()
    templates.append(template)
    save_custom_templates(templates)
    
    return template


def update_template(
    template_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    config: Optional[dict] = None,
    emoji: Optional[str] = None,
    tags: Optional[list[str]] = None
) -> Optional[CustomTemplate]:
    """
    Update an existing template.
    
    Args:
        template_id: Template ID to update.
        name: New name (optional).
        description: New description (optional).
        config: New config (optional).
        emoji: New emoji (optional).
        tags: New tags (optional).
    
    Returns:
        Updated template or None if not found.
    """
    templates = load_custom_templates()
    
    for i, t in enumerate(templates):
        if t.id == template_id:
            if name is not None:
                t.name = name
            if description is not None:
                t.description = description
            if config is not None:
                t.config = {**t.config, **config}
            if emoji is not None:
                t.emoji = emoji
            if tags is not None:
                t.tags = tags
            
            t.updated_at = datetime.now().isoformat()
            
            templates[i] = t
            save_custom_templates(templates)
            return t
    
    return None


def delete_template(template_id: str) -> bool:
    """
    Delete a custom template.
    
    Args:
        template_id: Template ID to delete.
    
    Returns:
        True if deleted, False if not found.
    """
    templates = load_custom_templates()
    
    for i, t in enumerate(templates):
        if t.id == template_id:
            templates.pop(i)
            save_custom_templates(templates)
            return True
    
    return False


def get_template(template_id: str) -> Optional[CustomTemplate]:
    """
    Get a template by ID.
    
    Args:
        template_id: Template ID.
    
    Returns:
        CustomTemplate or None.
    """
    templates = load_custom_templates()
    
    for t in templates:
        if t.id == template_id:
            return t
    
    return None


def increment_usage(template_id: str) -> bool:
    """
    Increment the usage count for a template.
    
    Args:
        template_id: Template ID.
    
    Returns:
        True if successful.
    """
    templates = load_custom_templates()
    
    for i, t in enumerate(templates):
        if t.id == template_id:
            t.usage_count += 1
            templates[i] = t
            save_custom_templates(templates)
            return True
    
    return False


def get_popular_templates(limit: int = 5) -> list[CustomTemplate]:
    """
    Get most used templates.
    
    Args:
        limit: Maximum number of templates.
    
    Returns:
        List of templates sorted by usage.
    """
    templates = load_custom_templates()
    templates.sort(key=lambda t: t.usage_count, reverse=True)
    return templates[:limit]


def get_recent_templates(limit: int = 5) -> list[CustomTemplate]:
    """
    Get recently created/updated templates.
    
    Args:
        limit: Maximum number of templates.
    
    Returns:
        List of templates sorted by date.
    """
    templates = load_custom_templates()
    templates.sort(key=lambda t: t.updated_at, reverse=True)
    return templates[:limit]


def search_templates(query: str) -> list[CustomTemplate]:
    """
    Search templates by name, description, or tags.
    
    Args:
        query: Search query.
    
    Returns:
        Matching templates.
    """
    query_lower = query.lower()
    templates = load_custom_templates()
    
    results = []
    for t in templates:
        if (query_lower in t.name.lower() or
            query_lower in t.description.lower() or
            any(query_lower in tag.lower() for tag in t.tags)):
            results.append(t)
    
    return results


def export_template(template_id: str) -> Optional[str]:
    """
    Export a template as JSON string.
    
    Args:
        template_id: Template ID.
    
    Returns:
        JSON string or None.
    """
    template = get_template(template_id)
    
    if not template:
        return None
    
    return json.dumps(asdict(template), ensure_ascii=False, indent=2)


def import_template(json_str: str) -> Optional[CustomTemplate]:
    """
    Import a template from JSON string.
    
    Args:
        json_str: JSON string.
    
    Returns:
        Imported template or None.
    """
    try:
        data = json.loads(json_str)
        
        # Generate new ID to avoid conflicts
        data["id"] = f"imported_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        data["created_at"] = datetime.now().isoformat()
        data["updated_at"] = datetime.now().isoformat()
        data["usage_count"] = 0
        
        template = CustomTemplate(**data)
        
        # Save to file
        templates = load_custom_templates()
        templates.append(template)
        save_custom_templates(templates)
        
        return template
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def get_template_suggestions(current_config: dict) -> list[str]:
    """
    Get suggestions for template improvements.
    
    Args:
        current_config: Current configuration.
    
    Returns:
        List of suggestion strings.
    """
    suggestions = []
    
    if current_config.get("include_exercises") and not current_config.get("include_solutions"):
        suggestions.append("Vurder å inkludere fasit for selv-evaluering")
    
    if current_config.get("include_theory") and not current_config.get("include_examples"):
        suggestions.append("Eksempler hjelper med å forstå teorien")
    
    if current_config.get("num_exercises", 0) > 15:
        suggestions.append("Mange oppgaver - vurder å dele opp i flere ark")
    
    if current_config.get("difficulty") == "vanskelig" and not current_config.get("include_tips"):
        suggestions.append("Tips kan hjelpe elever med vanskelige oppgaver")
    
    return suggestions


# Preset templates for quick start
PRESET_TEMPLATES = {
    "quick_practice": {
        "name": "Hurtigøving",
        "emoji": "⚡",
        "description": "10 raske oppgaver uten teori",
        "config": {
            "material_type": "arbeidsark",
            "include_theory": False,
            "include_examples": False,
            "include_exercises": True,
            "include_solutions": True,
            "include_graphs": False,
            "include_tips": False,
            "num_exercises": 10,
        }
    },
    "deep_learning": {
        "name": "Dybdelæring",
        "emoji": "🎓",
        "description": "Grundig gjennomgang med teori",
        "config": {
            "material_type": "kapittel",
            "include_theory": True,
            "include_examples": True,
            "include_exercises": True,
            "include_solutions": True,
            "include_graphs": True,
            "include_tips": True,
            "num_exercises": 6,
        }
    },
    "exam_simulation": {
        "name": "Eksamenssimulering",
        "emoji": "📝",
        "description": "Realistisk prøve-format",
        "config": {
            "material_type": "prøve",
            "include_theory": False,
            "include_examples": False,
            "include_exercises": True,
            "include_solutions": True,
            "include_graphs": True,
            "include_tips": False,
            "num_exercises": 12,
        }
    },
    "visual_learning": {
        "name": "Visuell læring",
        "emoji": "📊",
        "description": "Fokus på grafer og figurer",
        "config": {
            "material_type": "arbeidsark",
            "include_theory": True,
            "include_examples": True,
            "include_exercises": True,
            "include_solutions": True,
            "include_graphs": True,
            "include_tips": True,
            "num_exercises": 8,
        }
    },
}


def get_preset_templates() -> dict:
    """Get all preset templates."""
    return PRESET_TEMPLATES
