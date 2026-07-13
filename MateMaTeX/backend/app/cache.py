"""
Semantic caching for the MateMaTeX 2.0 pipeline.

Implements:
- Agent-level caching: reuse pedagogue plans when only difficulty changes
- Semantic similarity: find >90% similar previous requests
- Token cost estimation before generation
- Cache invalidation by TTL and manual clear
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from app.models.state import GenerationRequest

logger = structlog.get_logger()

# Cache storage directory
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"


@dataclass
class CacheEntry:
    """A cached result for an agent."""
    key: str
    agent: str
    result: str
    request_hash: str
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int = 3600  # 1 hour default
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


class SemanticCache:
    """
    Agent-level semantic cache.

    Caching strategy:
    - Pedagogue plans are cached by (grade, topic, material_type).
      If only difficulty/num_exercises changes, the plan is reused.
    - Author output is cached by (plan_hash, content_options).
    - Full pipeline results are cached by the full request hash.

    Similarity matching:
    - Exact match by hash (fast path)
    - Near-match by comparing individual fields (finds >90% similar requests)
    """

    def __init__(self, cache_dir: Path | None = None):
        self._dir = cache_dir or CACHE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._memory: dict[str, CacheEntry] = {}
        self._load_from_disk()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_pedagogue_plan(self, request: GenerationRequest) -> str | None:
        """
        Get a cached pedagogue plan if available.
        Plans are keyed by (grade, topic, material_type) — NOT by difficulty/num_exercises.
        """
        key = self._pedagogue_key(request)
        return self._get(key, "pedagogue")

    def set_pedagogue_plan(self, request: GenerationRequest, plan: str) -> None:
        """Cache a pedagogue plan."""
        key = self._pedagogue_key(request)
        self._set(key, "pedagogue", plan, request)

    def get_author_output(self, plan_hash: str, request: GenerationRequest) -> str | None:
        """Get cached author output for a specific plan + options combination."""
        key = self._author_key(plan_hash, request)
        return self._get(key, "author")

    def set_author_output(
        self, plan_hash: str, request: GenerationRequest, output: str
    ) -> None:
        """Cache author output."""
        key = self._author_key(plan_hash, request)
        self._set(key, "author", output, request)

    def get_full_result(self, request: GenerationRequest) -> str | None:
        """Get a cached full pipeline result (exact match)."""
        key = self._full_key(request)
        return self._get(key, "full")

    def set_full_result(self, request: GenerationRequest, result: str) -> None:
        """Cache a full pipeline result."""
        key = self._full_key(request)
        self._set(key, "full", result, request, ttl=7200)  # 2 hours

    def find_similar(self, request: GenerationRequest) -> list[tuple[float, CacheEntry]]:
        """
        Find cached entries that are >90% similar to the request.

        Returns list of (similarity_score, CacheEntry) sorted by score descending.
        """
        matches: list[tuple[float, CacheEntry]] = []
        request_dict = request.model_dump()

        for entry in self._memory.values():
            if entry.is_expired or entry.agent != "full":
                continue

            score = self._similarity_score(request_dict, entry.request_hash)
            if score >= 0.9:
                matches.append((score, entry))

        matches.sort(key=lambda x: x[0], reverse=True)
        return matches[:5]

    def clear(self) -> int:
        """Clear all cached entries. Returns count of entries removed."""
        count = len(self._memory)
        self._memory.clear()
        # Clear disk
        for f in self._dir.glob("*.json"):
            f.unlink(missing_ok=True)
        logger.info("cache_cleared", entries_removed=count)
        return count

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = len(self._memory)
        expired = sum(1 for e in self._memory.values() if e.is_expired)
        by_agent: dict[str, int] = {}
        for e in self._memory.values():
            by_agent[e.agent] = by_agent.get(e.agent, 0) + 1

        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "by_agent": by_agent,
            "total_hits": sum(e.hit_count for e in self._memory.values()),
        }

    # ------------------------------------------------------------------
    # Token cost estimation
    # ------------------------------------------------------------------
    @staticmethod
    def estimate_tokens(request: GenerationRequest) -> dict[str, int]:
        """
        Estimate token usage and cost BEFORE generation.

        Returns dict with estimated input/output tokens and approximate cost.
        """
        # Base estimates by material type
        base = {
            "arbeidsark": {"input": 2000, "output": 3000},
            "kapittel": {"input": 3000, "output": 6000},
            "prøve": {"input": 2000, "output": 4000},
            "differensiert": {"input": 2500, "output": 5000},
        }.get(request.material_type, {"input": 2000, "output": 3000})

        # Scale by options
        multiplier = 1.0
        if request.include_theory:
            multiplier += 0.3
        if request.include_examples:
            multiplier += 0.2
        if request.include_graphs:
            multiplier += 0.3
        if request.include_solutions:
            multiplier += 0.2

        # Scale by exercises
        exercise_factor = request.num_exercises / 10.0

        total_output = int(base["output"] * multiplier * exercise_factor)
        total_input = int(base["input"] * multiplier)

        # 3 agents + potential retries
        total_input *= 3
        total_output *= 3

        return {
            "estimated_input_tokens": total_input,
            "estimated_output_tokens": total_output,
            "estimated_total_tokens": total_input + total_output,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _pedagogue_key(self, request: GenerationRequest) -> str:
        """
        Pedagogue cache key: grade + topic + material_type + language level,
        plus user steering (competency goals, extra instructions). Difficulty
        and exercise count are deliberately excluded so plans can be reused,
        but ignoring the user's explicit instructions would serve wrong plans.
        """
        goals = "|".join(sorted(request.competency_goals))
        raw = (
            f"pedagogue:v2:{request.grade}:{request.topic}:{request.material_type}"
            f":{request.language_level}:{goals}:{request.extra_instructions}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _author_key(self, plan_hash: str, request: GenerationRequest) -> str:
        """Author cache key: plan + full content options."""
        opts = json.dumps({
            "difficulty": request.difficulty,
            "num_exercises": request.num_exercises,
            "include_theory": request.include_theory,
            "include_examples": request.include_examples,
            "include_graphs": request.include_graphs,
            "include_solutions": request.include_solutions,
            "language_level": request.language_level,
        }, sort_keys=True)
        raw = f"author:{plan_hash}:{opts}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _full_key(self, request: GenerationRequest) -> str:
        """Full result cache key: entire request."""
        raw = request.model_dump_json()
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _get(self, key: str, agent: str) -> str | None:
        entry = self._memory.get(key)
        if entry is None or entry.is_expired or entry.agent != agent:
            return None
        entry.hit_count += 1
        logger.debug("cache_hit", key=key, agent=agent, hits=entry.hit_count)
        return entry.result

    def _set(
        self,
        key: str,
        agent: str,
        result: str,
        request: GenerationRequest,
        ttl: int = 3600,
    ) -> None:
        entry = CacheEntry(
            key=key,
            agent=agent,
            result=result,
            request_hash=request.model_dump_json(),
            ttl_seconds=ttl,
        )
        self._memory[key] = entry
        self._save_to_disk(entry)
        logger.debug("cache_set", key=key, agent=agent)

    def _similarity_score(self, request_dict: dict, stored_request_json: str) -> float:
        """Compute similarity between two requests (0.0 to 1.0)."""
        try:
            stored = json.loads(stored_request_json)
        except json.JSONDecodeError:
            return 0.0

        # Compare key fields
        fields_and_weights = {
            "grade": 0.25,
            "topic": 0.30,
            "material_type": 0.15,
            "language_level": 0.10,
            "difficulty": 0.05,
            "include_theory": 0.05,
            "include_examples": 0.05,
            "include_exercises": 0.05,
        }

        score = 0.0
        for field_name, weight in fields_and_weights.items():
            if request_dict.get(field_name) == stored.get(field_name):
                score += weight

        return score

    def _save_to_disk(self, entry: CacheEntry) -> None:
        """Persist a cache entry to disk."""
        try:
            path = self._dir / f"{entry.key}.json"
            path.write_text(
                json.dumps({
                    "key": entry.key,
                    "agent": entry.agent,
                    "result": entry.result,
                    "request_hash": entry.request_hash,
                    "created_at": entry.created_at,
                    "ttl_seconds": entry.ttl_seconds,
                    "hit_count": entry.hit_count,
                }, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("cache_save_failed", error=str(e))

    def _load_from_disk(self) -> None:
        """Load cache entries from disk."""
        for path in self._dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                entry = CacheEntry(**data)
                if not entry.is_expired:
                    self._memory[entry.key] = entry
            except Exception:
                pass  # Skip corrupted entries


# Singleton
_cache_instance: SemanticCache | None = None


def get_cache() -> SemanticCache:
    """Get the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SemanticCache()
    return _cache_instance
