"""
Usage Dashboard for MateMaTeX.
Track and display statistics about generated content.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from collections import Counter


# Storage
DATA_DIR = Path(__file__).parent.parent.parent / "data"
STATS_FILE = DATA_DIR / "usage_stats.json"


@dataclass
class UsageStats:
    """Overall usage statistics."""
    total_generations: int
    total_exercises: int
    total_pages_estimated: int
    favorite_topics: list[tuple[str, int]]
    favorite_grades: list[tuple[str, int]]
    generations_by_day: dict[str, int]
    generations_by_week: dict[str, int]
    material_types: dict[str, int]
    avg_exercises_per_generation: float
    streak_days: int
    last_generation: Optional[str]
    first_generation: Optional[str]


@dataclass
class DailyStats:
    """Statistics for a single day."""
    date: str
    generations: int
    exercises: int
    topics: list[str]
    grades: list[str]


def ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_raw_stats() -> dict:
    """Load raw statistics from file."""
    ensure_data_dir()
    
    if not STATS_FILE.exists():
        return {
            "generations": [],
            "daily": {},
        }
    
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"generations": [], "daily": {}}


def save_raw_stats(stats: dict) -> bool:
    """Save raw statistics to file."""
    ensure_data_dir()
    
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def record_generation(
    topic: str,
    grade: str,
    material_type: str,
    num_exercises: int
) -> None:
    """Record a new generation for statistics."""
    stats = load_raw_stats()
    
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    
    # Add generation record
    generation = {
        "timestamp": now.isoformat(),
        "date": today,
        "topic": topic,
        "grade": grade,
        "material_type": material_type,
        "num_exercises": num_exercises,
    }
    stats["generations"].append(generation)
    
    # Update daily stats
    if today not in stats["daily"]:
        stats["daily"][today] = {
            "generations": 0,
            "exercises": 0,
            "topics": [],
            "grades": [],
        }
    
    stats["daily"][today]["generations"] += 1
    stats["daily"][today]["exercises"] += num_exercises
    
    if topic not in stats["daily"][today]["topics"]:
        stats["daily"][today]["topics"].append(topic)
    if grade not in stats["daily"][today]["grades"]:
        stats["daily"][today]["grades"].append(grade)
    
    save_raw_stats(stats)


def get_usage_stats() -> UsageStats:
    """Calculate and return usage statistics."""
    raw = load_raw_stats()
    generations = raw.get("generations", [])
    
    if not generations:
        return UsageStats(
            total_generations=0,
            total_exercises=0,
            total_pages_estimated=0,
            favorite_topics=[],
            favorite_grades=[],
            generations_by_day={},
            generations_by_week={},
            material_types={},
            avg_exercises_per_generation=0,
            streak_days=0,
            last_generation=None,
            first_generation=None,
        )
    
    # Count totals
    total_generations = len(generations)
    total_exercises = sum(g.get("num_exercises", 0) for g in generations)
    total_pages_estimated = total_exercises // 3  # Rough estimate
    
    # Count topics and grades
    topic_counter = Counter(g.get("topic", "") for g in generations)
    grade_counter = Counter(g.get("grade", "") for g in generations)
    material_counter = Counter(g.get("material_type", "") for g in generations)
    
    favorite_topics = topic_counter.most_common(5)
    favorite_grades = grade_counter.most_common(5)
    
    # Generations by day (last 30 days)
    today = datetime.now().date()
    generations_by_day = {}
    for i in range(30):
        day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        count = sum(1 for g in generations if g.get("date") == day)
        if count > 0:
            generations_by_day[day] = count
    
    # Generations by week (last 12 weeks)
    generations_by_week = {}
    for i in range(12):
        week_start = today - timedelta(days=today.weekday() + 7 * i)
        week_end = week_start + timedelta(days=6)
        week_key = f"Uke {week_start.isocalendar()[1]}"
        
        count = sum(
            1 for g in generations
            if g.get("date") and week_start.strftime("%Y-%m-%d") <= g.get("date") <= week_end.strftime("%Y-%m-%d")
        )
        if count > 0:
            generations_by_week[week_key] = count
    
    # Calculate streak
    streak_days = 0
    check_date = today
    daily = raw.get("daily", {})
    
    while check_date.strftime("%Y-%m-%d") in daily:
        streak_days += 1
        check_date -= timedelta(days=1)
    
    # Average exercises
    avg_exercises = total_exercises / total_generations if total_generations > 0 else 0
    
    # First and last generation
    sorted_gens = sorted(generations, key=lambda g: g.get("timestamp", ""))
    first_gen = sorted_gens[0].get("timestamp") if sorted_gens else None
    last_gen = sorted_gens[-1].get("timestamp") if sorted_gens else None
    
    return UsageStats(
        total_generations=total_generations,
        total_exercises=total_exercises,
        total_pages_estimated=total_pages_estimated,
        favorite_topics=favorite_topics,
        favorite_grades=favorite_grades,
        generations_by_day=generations_by_day,
        generations_by_week=generations_by_week,
        material_types=dict(material_counter),
        avg_exercises_per_generation=round(avg_exercises, 1),
        streak_days=streak_days,
        last_generation=last_gen,
        first_generation=first_gen,
    )


def get_dashboard_html(stats: UsageStats) -> str:
    """Generate HTML for the usage dashboard."""
    
    # Format dates
    last_gen_str = ""
    if stats.last_generation:
        try:
            dt = datetime.fromisoformat(stats.last_generation)
            last_gen_str = dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            last_gen_str = "Ukjent"
    
    # Top topics
    topics_html = ""
    for topic, count in stats.favorite_topics[:5]:
        topics_html += f"""
        <div style="display: flex; justify-content: space-between; padding: 0.25rem 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
            <span style="color: #e2e8f0; font-size: 0.85rem;">{topic[:25]}{'...' if len(topic) > 25 else ''}</span>
            <span style="color: #f0b429; font-weight: 500;">{count}</span>
        </div>
        """
    
    # Material types
    material_html = ""
    material_icons = {"kapittel": "📖", "arbeidsark": "📝", "prøve": "📋", "lekseark": "📚"}
    for mat_type, count in stats.material_types.items():
        icon = material_icons.get(mat_type, "📄")
        material_html += f"""
        <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.25rem 0;">
            <span>{icon}</span>
            <span style="color: #e2e8f0; font-size: 0.85rem; flex: 1;">{mat_type.capitalize()}</span>
            <span style="color: #9090a0;">{count}</span>
        </div>
        """
    
    return f"""
    <div style="
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
    ">
        <h3 style="color: #f0b429; margin-top: 0; margin-bottom: 1.5rem; font-size: 1.1rem;">
            📊 Bruksdashboard
        </h3>
        
        <!-- Stats grid -->
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem;">
            <div style="text-align: center; padding: 1rem; background: rgba(240,180,41,0.1); border-radius: 12px;">
                <div style="font-size: 1.75rem; font-weight: 700; color: #f0b429;">{stats.total_generations}</div>
                <div style="color: #9090a0; font-size: 0.75rem;">Genereringer</div>
            </div>
            <div style="text-align: center; padding: 1rem; background: rgba(16,185,129,0.1); border-radius: 12px;">
                <div style="font-size: 1.75rem; font-weight: 700; color: #10b981;">{stats.total_exercises}</div>
                <div style="color: #9090a0; font-size: 0.75rem;">Oppgaver</div>
            </div>
            <div style="text-align: center; padding: 1rem; background: rgba(59,130,246,0.1); border-radius: 12px;">
                <div style="font-size: 1.75rem; font-weight: 700; color: #3b82f6;">{stats.total_pages_estimated}</div>
                <div style="color: #9090a0; font-size: 0.75rem;">~Sider</div>
            </div>
            <div style="text-align: center; padding: 1rem; background: rgba(139,92,246,0.1); border-radius: 12px;">
                <div style="font-size: 1.75rem; font-weight: 700; color: #8b5cf6;">{stats.streak_days}🔥</div>
                <div style="color: #9090a0; font-size: 0.75rem;">Dager på rad</div>
            </div>
        </div>
        
        <!-- Two columns -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
            <!-- Top topics -->
            <div>
                <h4 style="color: #e2e8f0; font-size: 0.9rem; margin-bottom: 0.75rem;">🎯 Topp emner</h4>
                {topics_html if topics_html else '<p style="color: #606070; font-size: 0.85rem;">Ingen data ennå</p>'}
            </div>
            
            <!-- Material types -->
            <div>
                <h4 style="color: #e2e8f0; font-size: 0.9rem; margin-bottom: 0.75rem;">📄 Materialtyper</h4>
                {material_html if material_html else '<p style="color: #606070; font-size: 0.85rem;">Ingen data ennå</p>'}
            </div>
        </div>
        
        <!-- Footer -->
        <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.1); display: flex; justify-content: space-between; align-items: center;">
            <span style="color: #606070; font-size: 0.75rem;">
                Snitt: {stats.avg_exercises_per_generation} oppgaver/generering
            </span>
            <span style="color: #606070; font-size: 0.75rem;">
                Sist: {last_gen_str}
            </span>
        </div>
    </div>
    """


def get_activity_chart_data(stats: UsageStats) -> dict:
    """Get data for activity chart (last 30 days)."""
    today = datetime.now().date()
    data = []
    
    for i in range(30):
        day = today - timedelta(days=29-i)
        day_str = day.strftime("%Y-%m-%d")
        count = stats.generations_by_day.get(day_str, 0)
        data.append({
            "date": day.strftime("%d.%m"),
            "count": count,
        })
    
    return {"days": data}


def get_achievements(stats: UsageStats) -> list[dict]:
    """Get achievements/badges based on usage."""
    achievements = []
    
    # First generation
    if stats.total_generations >= 1:
        achievements.append({
            "id": "first_gen",
            "name": "Første steg",
            "description": "Laget din første generering",
            "icon": "🎉",
            "unlocked": True,
        })
    
    # 10 generations
    if stats.total_generations >= 10:
        achievements.append({
            "id": "gen_10",
            "name": "Flittig bruker",
            "description": "10 genereringer",
            "icon": "⭐",
            "unlocked": True,
        })
    
    # 50 generations
    if stats.total_generations >= 50:
        achievements.append({
            "id": "gen_50",
            "name": "Superbruker",
            "description": "50 genereringer",
            "icon": "🏆",
            "unlocked": True,
        })
    
    # 100 exercises
    if stats.total_exercises >= 100:
        achievements.append({
            "id": "ex_100",
            "name": "Oppgavemester",
            "description": "100 oppgaver generert",
            "icon": "📝",
            "unlocked": True,
        })
    
    # 7 day streak
    if stats.streak_days >= 7:
        achievements.append({
            "id": "streak_7",
            "name": "Uke-streak",
            "description": "7 dager på rad",
            "icon": "🔥",
            "unlocked": True,
        })
    
    # Multiple topics
    if len(stats.favorite_topics) >= 5:
        achievements.append({
            "id": "diverse",
            "name": "Allsidig",
            "description": "Brukt 5+ forskjellige emner",
            "icon": "🎨",
            "unlocked": True,
        })
    
    return achievements


def render_achievements_html(achievements: list[dict]) -> str:
    """Render achievements as HTML badges."""
    if not achievements:
        return '<p style="color: #606070; font-size: 0.85rem;">Ingen badges ennå - fortsett å bruke appen!</p>'
    
    badges_html = ""
    for ach in achievements:
        badges_html += f"""
        <div style="
            display: inline-flex;
            flex-direction: column;
            align-items: center;
            padding: 0.75rem;
            background: rgba(240,180,41,0.1);
            border-radius: 12px;
            margin: 0.25rem;
            min-width: 80px;
        ">
            <span style="font-size: 1.5rem;">{ach['icon']}</span>
            <span style="color: #f0b429; font-size: 0.7rem; font-weight: 500; margin-top: 0.25rem;">{ach['name']}</span>
        </div>
        """
    
    return f'<div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">{badges_html}</div>'
