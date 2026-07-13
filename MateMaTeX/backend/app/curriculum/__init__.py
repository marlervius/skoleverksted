"""LK20 curriculum data — ported from the v1 src/curriculum.py."""

from .lk20 import (
    get_grade_boundaries,
    format_boundaries_for_prompt,
    get_topics_for_grade,
    get_competency_goals,
    get_language_level_instructions,
    LANGUAGE_LEVELS,
)
from .topic_coverage import (
    format_coverage_for_prompt,
    get_topic_coverage_spec,
)

__all__ = [
    "get_grade_boundaries",
    "format_boundaries_for_prompt",
    "get_topics_for_grade",
    "get_competency_goals",
    "get_language_level_instructions",
    "format_coverage_for_prompt",
    "get_topic_coverage_spec",
    "LANGUAGE_LEVELS",
]
