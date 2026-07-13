"""
Global Search for MateMaTeX.
Search across all content types.
"""

import re
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Represents a search result."""
    id: str
    type: str  # "favorite", "exercise", "history", "template"
    title: str
    snippet: str
    relevance_score: float
    created_at: str
    metadata: dict


def normalize_text(text: str) -> str:
    """Normalize text for searching."""
    # Convert to lowercase
    text = text.lower()
    # Remove LaTeX commands
    text = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', text)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    # Remove special characters
    text = re.sub(r'[^\w\s]', ' ', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def calculate_relevance(query: str, text: str, title: str = "") -> float:
    """Calculate relevance score for a search result."""
    query_lower = query.lower()
    text_lower = text.lower()
    title_lower = title.lower()
    
    score = 0.0
    
    # Exact match in title (highest score)
    if query_lower in title_lower:
        score += 10.0
        if title_lower.startswith(query_lower):
            score += 5.0
    
    # Exact match in content
    if query_lower in text_lower:
        score += 5.0
        # Count occurrences
        count = text_lower.count(query_lower)
        score += min(count, 5) * 0.5
    
    # Word matches
    query_words = query_lower.split()
    for word in query_words:
        if len(word) > 2:  # Skip short words
            if word in title_lower:
                score += 2.0
            if word in text_lower:
                score += 1.0
    
    return score


def extract_snippet(text: str, query: str, max_length: int = 150) -> str:
    """Extract a relevant snippet from text around the query match."""
    query_lower = query.lower()
    text_lower = text.lower()
    
    # Find the position of the query in text
    pos = text_lower.find(query_lower)
    
    if pos == -1:
        # No exact match, return beginning of text
        return text[:max_length] + "..." if len(text) > max_length else text
    
    # Calculate snippet boundaries
    start = max(0, pos - 50)
    end = min(len(text), pos + len(query) + 100)
    
    snippet = text[start:end]
    
    # Clean up snippet
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    
    return snippet


def search_favorites(query: str) -> list[SearchResult]:
    """Search in favorites."""
    results = []
    
    try:
        from src.tools import load_favorites
        favorites = load_favorites()
        
        for fav in favorites:
            content = f"{fav.name} {fav.topic} {fav.latex_content}"
            normalized = normalize_text(content)
            
            if query.lower() in normalized or query.lower() in fav.name.lower():
                score = calculate_relevance(query, content, fav.name)
                
                if score > 0:
                    results.append(SearchResult(
                        id=fav.id,
                        type="favorite",
                        title=fav.name,
                        snippet=extract_snippet(fav.latex_content, query),
                        relevance_score=score,
                        created_at=fav.created_at,
                        metadata={
                            "topic": fav.topic,
                            "grade": fav.grade_level,
                            "rating": fav.rating,
                            "is_pinned": fav.is_pinned,
                        }
                    ))
    except Exception:
        pass
    
    return results


def search_exercises(query: str) -> list[SearchResult]:
    """Search in exercise bank."""
    results = []
    
    try:
        from src.tools import load_exercises
        exercises = load_exercises()
        
        for ex in exercises:
            content = f"{ex.title} {ex.topic} {ex.latex_content}"
            normalized = normalize_text(content)
            
            if query.lower() in normalized or query.lower() in ex.title.lower():
                score = calculate_relevance(query, content, ex.title)
                
                if score > 0:
                    results.append(SearchResult(
                        id=ex.id,
                        type="exercise",
                        title=ex.title,
                        snippet=extract_snippet(ex.latex_content, query),
                        relevance_score=score,
                        created_at=ex.created_at,
                        metadata={
                            "topic": ex.topic,
                            "grade": ex.grade_level,
                            "difficulty": ex.difficulty,
                            "usage_count": ex.usage_count,
                        }
                    ))
    except Exception:
        pass
    
    return results


def search_history(query: str) -> list[SearchResult]:
    """Search in generation history."""
    results = []
    
    try:
        from src.storage import load_history, get_tex_content
        history = load_history()
        
        for entry in history:
            topic = entry.get("topic", "")
            grade = entry.get("grade", "")
            entry_id = entry.get("id", "")
            
            # Get LaTeX content if available
            tex_content = get_tex_content(entry_id) or ""
            
            content = f"{topic} {grade} {tex_content}"
            normalized = normalize_text(content)
            
            if query.lower() in normalized or query.lower() in topic.lower():
                score = calculate_relevance(query, content, topic)
                
                if score > 0:
                    results.append(SearchResult(
                        id=entry_id,
                        type="history",
                        title=topic,
                        snippet=extract_snippet(tex_content or topic, query),
                        relevance_score=score,
                        created_at=entry.get("timestamp", ""),
                        metadata={
                            "grade": grade,
                            "material_type": entry.get("material_type", ""),
                        }
                    ))
    except Exception:
        pass
    
    return results


def search_templates(query: str) -> list[SearchResult]:
    """Search in custom templates."""
    results = []
    
    try:
        from src.tools import load_custom_templates
        templates = load_custom_templates()
        
        for tmpl in templates:
            content = f"{tmpl.name} {tmpl.description}"
            normalized = normalize_text(content)
            
            if query.lower() in normalized or query.lower() in tmpl.name.lower():
                score = calculate_relevance(query, content, tmpl.name)
                
                if score > 0:
                    results.append(SearchResult(
                        id=tmpl.id,
                        type="template",
                        title=f"{tmpl.emoji} {tmpl.name}",
                        snippet=tmpl.description,
                        relevance_score=score,
                        created_at=tmpl.created_at,
                        metadata={
                            "usage_count": tmpl.usage_count,
                        }
                    ))
    except Exception:
        pass
    
    return results


def global_search(
    query: str,
    search_favorites_flag: bool = True,
    search_exercises_flag: bool = True,
    search_history_flag: bool = True,
    search_templates_flag: bool = True,
    limit: int = 20
) -> list[SearchResult]:
    """
    Search across all content types.
    
    Args:
        query: Search query.
        search_favorites_flag: Include favorites in search.
        search_exercises_flag: Include exercises in search.
        search_history_flag: Include history in search.
        search_templates_flag: Include templates in search.
        limit: Maximum number of results.
    
    Returns:
        List of search results sorted by relevance.
    """
    if not query or len(query) < 2:
        return []
    
    all_results = []
    
    if search_favorites_flag:
        all_results.extend(search_favorites(query))
    
    if search_exercises_flag:
        all_results.extend(search_exercises(query))
    
    if search_history_flag:
        all_results.extend(search_history(query))
    
    if search_templates_flag:
        all_results.extend(search_templates(query))
    
    # Sort by relevance score
    all_results.sort(key=lambda r: r.relevance_score, reverse=True)
    
    return all_results[:limit]


def get_type_icon(result_type: str) -> str:
    """Get icon for result type."""
    icons = {
        "favorite": "⭐",
        "exercise": "📝",
        "history": "📜",
        "template": "🎨",
    }
    return icons.get(result_type, "📄")


def get_type_label(result_type: str) -> str:
    """Get Norwegian label for result type."""
    labels = {
        "favorite": "Favoritt",
        "exercise": "Oppgave",
        "history": "Historikk",
        "template": "Mal",
    }
    return labels.get(result_type, "Ukjent")


def render_search_result_html(result: SearchResult) -> str:
    """Render a search result as HTML."""
    icon = get_type_icon(result.type)
    type_label = get_type_label(result.type)
    
    # Format date
    try:
        dt = datetime.fromisoformat(result.created_at)
        date_str = dt.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        date_str = ""
    
    return f"""
    <div style="
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
        cursor: pointer;
        transition: background 0.2s ease;
    " onmouseover="this.style.background='rgba(255,255,255,0.06)'" 
       onmouseout="this.style.background='rgba(255,255,255,0.03)'">
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
            <span style="font-size: 1rem;">{icon}</span>
            <span style="color: #f0b429; font-weight: 500; font-size: 0.9rem;">{result.title}</span>
            <span style="
                background: rgba(240, 180, 41, 0.2);
                color: #f0b429;
                padding: 0.1rem 0.4rem;
                border-radius: 4px;
                font-size: 0.65rem;
            ">{type_label}</span>
        </div>
        <p style="color: #9090a0; font-size: 0.8rem; margin: 0.25rem 0; line-height: 1.4;">
            {result.snippet}
        </p>
        <div style="color: #606070; font-size: 0.7rem; margin-top: 0.25rem;">
            {date_str}
        </div>
    </div>
    """


def get_search_suggestions(query: str, limit: int = 5) -> list[str]:
    """Get search suggestions based on query."""
    suggestions = []
    
    # Common math topics
    topics = [
        "Brøk", "Prosent", "Algebra", "Geometri", "Funksjoner",
        "Likninger", "Ulikheter", "Statistikk", "Sannsynlighet",
        "Trigonometri", "Derivasjon", "Integrasjon", "Vektorer",
        "Pytagoras", "Areal", "Volum", "Omkrets", "Vinkler",
    ]
    
    query_lower = query.lower()
    
    for topic in topics:
        if query_lower in topic.lower() and topic.lower() != query_lower:
            suggestions.append(topic)
            if len(suggestions) >= limit:
                break
    
    return suggestions
