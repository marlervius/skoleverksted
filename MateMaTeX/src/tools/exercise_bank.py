"""
Exercise Bank for MateMaTeX.
Save and manage individual exercises for reuse.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict


# Storage directory
EXERCISES_DIR = Path(__file__).parent.parent.parent / "data" / "exercises"


@dataclass
class Exercise:
    """Represents a single exercise."""
    id: str
    title: str
    topic: str
    grade_level: str
    difficulty: str  # "lett", "middels", "vanskelig"
    latex_content: str
    solution: Optional[str]
    tags: list[str]
    created_at: str
    usage_count: int
    source: str  # "generated", "imported", "manual"


def ensure_exercises_dir():
    """Ensure the exercises directory exists."""
    EXERCISES_DIR.mkdir(parents=True, exist_ok=True)


def get_exercises_file() -> Path:
    """Get path to exercises JSON file."""
    ensure_exercises_dir()
    return EXERCISES_DIR / "exercise_bank.json"


def load_exercises() -> list[Exercise]:
    """Load all exercises from file."""
    exercises_file = get_exercises_file()
    
    if not exercises_file.exists():
        return []
    
    try:
        with open(exercises_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Exercise(**e) for e in data]
    except (json.JSONDecodeError, IOError, TypeError):
        return []


def save_exercises(exercises: list[Exercise]) -> bool:
    """Save exercises to file."""
    exercises_file = get_exercises_file()
    
    try:
        data = [asdict(e) for e in exercises]
        with open(exercises_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def extract_exercises_from_latex(latex_content: str) -> list[dict]:
    """
    Extract individual exercises from LaTeX content.
    
    Args:
        latex_content: The LaTeX source code.
    
    Returns:
        List of exercise dictionaries.
    """
    exercises = []
    
    # Pattern for taskbox environments
    taskbox_pattern = r'\\begin\{taskbox\}\{([^}]*)\}(.*?)\\end\{taskbox\}'
    matches = re.finditer(taskbox_pattern, latex_content, re.DOTALL)
    
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        content = match.group(2).strip()
        
        # Try to extract solution if present
        solution = None
        solution_match = re.search(r'\\textbf\{Løsning[:\s]*\}(.*?)(?=\\end|$)', content, re.DOTALL)
        if solution_match:
            solution = solution_match.group(1).strip()
        
        # Determine difficulty based on content analysis
        difficulty = "middels"
        content_lower = content.lower()
        if any(term in content_lower for term in ["bevis", "utled", "generali", "kompleks"]):
            difficulty = "vanskelig"
        elif any(term in content_lower for term in ["enkel", "grunnleggende", "finn"]):
            difficulty = "lett"
        
        exercises.append({
            "title": title or f"Oppgave {i + 1}",
            "content": content,
            "solution": solution,
            "difficulty": difficulty,
            "full_latex": match.group(0),
        })
    
    # Also try to find enumerate/itemize based exercises
    if not exercises:
        item_pattern = r'\\item\s+(.*?)(?=\\item|\\end\{enumerate\}|\\end\{itemize\}|$)'
        item_matches = re.finditer(item_pattern, latex_content, re.DOTALL)
        
        for i, match in enumerate(item_matches):
            content = match.group(1).strip()
            if len(content) > 20:  # Only substantial items
                exercises.append({
                    "title": f"Oppgave {i + 1}",
                    "content": content,
                    "solution": None,
                    "difficulty": "middels",
                    "full_latex": f"\\item {content}",
                })
    
    return exercises


def add_exercise(
    title: str,
    topic: str,
    grade_level: str,
    latex_content: str,
    difficulty: str = "middels",
    solution: Optional[str] = None,
    tags: Optional[list[str]] = None,
    source: str = "manual"
) -> Exercise:
    """
    Add a new exercise to the bank.
    
    Args:
        title: Exercise title.
        topic: Math topic.
        grade_level: Grade level.
        latex_content: The LaTeX code.
        difficulty: Difficulty level.
        solution: Optional solution.
        tags: Optional tags.
        source: Where the exercise came from.
    
    Returns:
        The created Exercise.
    """
    exercise_id = f"ex_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(load_exercises())}"
    
    exercise = Exercise(
        id=exercise_id,
        title=title,
        topic=topic,
        grade_level=grade_level,
        difficulty=difficulty,
        latex_content=latex_content,
        solution=solution,
        tags=tags or [],
        created_at=datetime.now().isoformat(),
        usage_count=0,
        source=source
    )
    
    exercises = load_exercises()
    exercises.insert(0, exercise)
    save_exercises(exercises)
    
    return exercise


def add_exercises_from_latex(
    latex_content: str,
    topic: str,
    grade_level: str
) -> list[Exercise]:
    """
    Extract and add all exercises from LaTeX content.
    
    Args:
        latex_content: The LaTeX source code.
        topic: Math topic.
        grade_level: Grade level.
    
    Returns:
        List of created Exercise objects.
    """
    extracted = extract_exercises_from_latex(latex_content)
    created = []
    
    for ex in extracted:
        exercise = add_exercise(
            title=ex["title"],
            topic=topic,
            grade_level=grade_level,
            latex_content=ex["full_latex"],
            difficulty=ex["difficulty"],
            solution=ex["solution"],
            source="generated"
        )
        created.append(exercise)
    
    return created


def get_exercise(exercise_id: str) -> Optional[Exercise]:
    """Get an exercise by ID and increment usage count."""
    exercises = load_exercises()
    
    for i, e in enumerate(exercises):
        if e.id == exercise_id:
            e.usage_count += 1
            exercises[i] = e
            save_exercises(exercises)
            return e
    
    return None


def delete_exercise(exercise_id: str) -> bool:
    """Delete an exercise."""
    exercises = load_exercises()
    
    for i, e in enumerate(exercises):
        if e.id == exercise_id:
            exercises.pop(i)
            save_exercises(exercises)
            return True
    
    return False


def update_exercise(
    exercise_id: str,
    title: Optional[str] = None,
    latex_content: Optional[str] = None,
    solution: Optional[str] = None,
    tags: Optional[list[str]] = None,
    difficulty: Optional[str] = None
) -> Optional[Exercise]:
    """Update an exercise."""
    exercises = load_exercises()
    
    for i, e in enumerate(exercises):
        if e.id == exercise_id:
            if title is not None:
                e.title = title
            if latex_content is not None:
                e.latex_content = latex_content
            if solution is not None:
                e.solution = solution
            if tags is not None:
                e.tags = tags
            if difficulty is not None:
                e.difficulty = difficulty
            
            exercises[i] = e
            save_exercises(exercises)
            return e
    
    return None


def search_exercises(
    query: Optional[str] = None,
    topic: Optional[str] = None,
    grade_level: Optional[str] = None,
    difficulty: Optional[str] = None,
    tags: Optional[list[str]] = None
) -> list[Exercise]:
    """
    Search exercises with filters.
    
    Args:
        query: Text search query.
        topic: Filter by topic.
        grade_level: Filter by grade.
        difficulty: Filter by difficulty.
        tags: Filter by tags.
    
    Returns:
        Matching exercises.
    """
    exercises = load_exercises()
    results = []
    
    for e in exercises:
        # Text search
        if query:
            query_lower = query.lower()
            if not (query_lower in e.title.lower() or 
                    query_lower in e.latex_content.lower() or
                    query_lower in e.topic.lower()):
                continue
        
        # Topic filter
        if topic and topic.lower() not in e.topic.lower():
            continue
        
        # Grade filter
        if grade_level and grade_level.lower() not in e.grade_level.lower():
            continue
        
        # Difficulty filter
        if difficulty and e.difficulty != difficulty:
            continue
        
        # Tags filter
        if tags and not any(t in e.tags for t in tags):
            continue
        
        results.append(e)
    
    return results


def get_exercises_by_topic(topic: str) -> list[Exercise]:
    """Get exercises for a specific topic."""
    return search_exercises(topic=topic)


def get_exercises_by_difficulty(difficulty: str) -> list[Exercise]:
    """Get exercises by difficulty level."""
    return search_exercises(difficulty=difficulty)


def get_popular_exercises(limit: int = 10) -> list[Exercise]:
    """Get most used exercises."""
    exercises = load_exercises()
    exercises.sort(key=lambda e: e.usage_count, reverse=True)
    return exercises[:limit]


def get_recent_exercises(limit: int = 10) -> list[Exercise]:
    """Get recently added exercises."""
    exercises = load_exercises()
    exercises.sort(key=lambda e: e.created_at, reverse=True)
    return exercises[:limit]


def get_all_topics() -> list[str]:
    """Get all unique topics from exercises."""
    topics = set()
    for e in load_exercises():
        topics.add(e.topic)
    return sorted(list(topics))


def get_all_tags() -> list[str]:
    """Get all unique tags from exercises."""
    tags = set()
    for e in load_exercises():
        tags.update(e.tags)
    return sorted(list(tags))


def get_exercise_stats() -> dict:
    """Get statistics about the exercise bank."""
    exercises = load_exercises()
    
    if not exercises:
        return {
            "total": 0,
            "by_difficulty": {},
            "by_topic": {},
            "total_usage": 0,
        }
    
    by_difficulty = {}
    by_topic = {}
    
    for e in exercises:
        by_difficulty[e.difficulty] = by_difficulty.get(e.difficulty, 0) + 1
        by_topic[e.topic] = by_topic.get(e.topic, 0) + 1
    
    return {
        "total": len(exercises),
        "by_difficulty": by_difficulty,
        "by_topic": by_topic,
        "total_usage": sum(e.usage_count for e in exercises),
    }


def create_worksheet_from_exercises(
    exercise_ids: list[str],
    title: str = "Oppgaveark"
) -> str:
    """
    Create a LaTeX worksheet from selected exercises.
    
    Args:
        exercise_ids: List of exercise IDs to include.
        title: Worksheet title.
    
    Returns:
        Combined LaTeX content.
    """
    parts = [
        f"\\section*{{{title}}}",
        "",
    ]
    
    for i, ex_id in enumerate(exercise_ids):
        exercise = get_exercise(ex_id)
        if exercise:
            parts.append(f"% Oppgave {i + 1}: {exercise.title}")
            parts.append(exercise.latex_content)
            parts.append("")
    
    return "\n".join(parts)


def get_difficulty_emoji(difficulty: str) -> str:
    """Get emoji for difficulty level."""
    return {
        "lett": "🟢",
        "middels": "🟡",
        "vanskelig": "🔴"
    }.get(difficulty, "⚪")


def format_exercise_preview(exercise: Exercise, max_length: int = 100) -> str:
    """Format an exercise for preview display."""
    # Clean LaTeX for display
    preview = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', exercise.latex_content)
    preview = re.sub(r'\\[a-zA-Z]+', '', preview)
    preview = re.sub(r'\s+', ' ', preview).strip()
    
    if len(preview) > max_length:
        preview = preview[:max_length] + "..."
    
    emoji = get_difficulty_emoji(exercise.difficulty)
    return f"{emoji} **{exercise.title}** - {preview}"
