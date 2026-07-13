"""
Caching utilities for MateMaTeX.
Provides cached versions of frequently-used load functions to improve performance.
"""

import streamlit as st
from typing import Optional


# TTL for different cache types (in seconds)
TTL_SHORT = 30      # 30 seconds for frequently changing data
TTL_MEDIUM = 300    # 5 minutes for semi-static data  
TTL_LONG = 3600     # 1 hour for rarely changing data


@st.cache_data(ttl=TTL_SHORT, show_spinner=False)
def get_history() -> list[dict]:
    """Cached version of load_history."""
    from src.storage import load_history
    return load_history()


@st.cache_data(ttl=TTL_MEDIUM, show_spinner=False)
def get_settings() -> dict:
    """Cached version of load_settings."""
    from src.storage import load_settings
    return load_settings()


@st.cache_data(ttl=TTL_SHORT, show_spinner=False)
def get_favorites() -> list:
    """Cached version of load_favorites."""
    from src.tools import load_favorites
    return load_favorites()


@st.cache_data(ttl=TTL_SHORT, show_spinner=False)
def get_exercises() -> list:
    """Cached version of load_exercises."""
    from src.tools import load_exercises
    return load_exercises()


@st.cache_data(ttl=TTL_SHORT, show_spinner=False)
def get_folders() -> list:
    """Cached version of load_folders."""
    from src.tools import load_folders
    return load_folders()


@st.cache_data(ttl=TTL_SHORT, show_spinner=False)
def get_tags() -> list:
    """Cached version of load_tags."""
    from src.tools import load_tags
    return load_tags()


@st.cache_data(ttl=TTL_SHORT, show_spinner=False)
def get_custom_templates() -> list:
    """Cached version of load_custom_templates."""
    from src.tools import load_custom_templates
    return load_custom_templates()


@st.cache_data(ttl=TTL_LONG, show_spinner=False)
def get_curriculum_topics(grade: str) -> dict:
    """Cached version of get_topics_for_grade."""
    from src.curriculum import get_topics_for_grade
    return get_topics_for_grade(grade)


@st.cache_data(ttl=TTL_LONG, show_spinner=False)
def get_curriculum_goals(grade: str) -> list:
    """Cached version of get_competency_goals."""
    from src.curriculum import get_competency_goals
    return get_competency_goals(grade)


@st.cache_data(ttl=TTL_LONG, show_spinner=False)
def get_all_exercise_types() -> dict:
    """Cached version of get_exercise_types."""
    from src.curriculum import get_exercise_types
    return get_exercise_types()


@st.cache_data(ttl=TTL_LONG, show_spinner=False)
def get_formula_categories() -> list:
    """Cached version of get_categories."""
    from src.tools import get_categories
    return get_categories()


@st.cache_data(ttl=TTL_LONG, show_spinner=False)
def get_formulas_for_category(category: str) -> list:
    """Cached version of get_formulas_by_category."""
    from src.tools import get_formulas_by_category
    return get_formulas_by_category(category)


def invalidate_history_cache():
    """Clear the history cache after modifications."""
    get_history.clear()


def invalidate_favorites_cache():
    """Clear the favorites cache after modifications."""
    get_favorites.clear()


def invalidate_exercises_cache():
    """Clear the exercises cache after modifications."""
    get_exercises.clear()


def invalidate_folders_cache():
    """Clear the folders cache after modifications."""
    get_folders.clear()


def invalidate_tags_cache():
    """Clear the tags cache after modifications."""
    get_tags.clear()


def invalidate_templates_cache():
    """Clear the templates cache after modifications."""
    get_custom_templates.clear()


def invalidate_all_caches():
    """Clear all caches."""
    get_history.clear()
    get_settings.clear()
    get_favorites.clear()
    get_exercises.clear()
    get_folders.clear()
    get_tags.clear()
    get_custom_templates.clear()
