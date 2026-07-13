"""Tests for job_manager.py — job lifecycle, cleanup, cache key, safe_filename."""
import asyncio
import time
import threading
import pytest

from job_manager import (
    cleanup_stale_jobs,
    compute_cache_key,
    get_job,
    pop_job,
    register_job,
    safe_filename,
    _jobs,
    _jobs_lock,
)


# ── Job lifecycle ─────────────────────────────────────────────────────────────

def test_register_creates_job():
    job_id, queue = register_job()
    job = get_job(job_id)
    assert job is not None
    assert not job.done
    assert job.error is None
    assert job.pdf is None


def test_get_unknown_job_returns_none():
    assert get_job("nonexistent-id") is None


def test_pop_removes_job():
    job_id, _ = register_job()
    popped = pop_job(job_id)
    assert popped is not None
    assert get_job(job_id) is None


def test_pop_unknown_returns_none():
    assert pop_job("nonexistent-id") is None


def test_register_returns_unique_ids():
    id1, _ = register_job()
    id2, _ = register_job()
    assert id1 != id2


# ── Stale job cleanup ─────────────────────────────────────────────────────────

def test_cleanup_removes_old_jobs():
    job_id, _ = register_job()
    with _jobs_lock:
        _jobs[job_id].created_at = time.time() - 99_999
    removed = cleanup_stale_jobs()
    assert removed >= 1
    assert get_job(job_id) is None


def test_cleanup_preserves_fresh_jobs():
    job_id, _ = register_job()
    cleanup_stale_jobs()
    assert get_job(job_id) is not None
    pop_job(job_id)  # tidy up


# ── safe_filename ─────────────────────────────────────────────────────────────

def test_safe_filename_ends_with_pdf():
    assert safe_filename("leksjon", "Fotosyntese", "VG1").endswith(".pdf")


def test_safe_filename_contains_prefix_and_topic():
    result = safe_filename("leksjon", "Fotosyntese", "VG1")
    assert "leksjon" in result
    assert "Fotosyntese" in result


def test_safe_filename_strips_special_chars():
    result = safe_filename("prove", "Tema: mørke!", "VG2")
    assert ":" not in result
    assert "!" not in result


def test_safe_filename_long_topic_truncated():
    long_topic = "A" * 200
    result = safe_filename("leksjon", long_topic, "VG1")
    # Should not blow up and result should be reasonable length
    assert len(result) < 300


# ── compute_cache_key ─────────────────────────────────────────────────────────

def test_cache_key_deterministic():
    class FakePayload:
        def model_dump(self):
            return {"topic": "Fotosyntese", "level": "VG1"}

    key1 = compute_cache_key("pdf_lesson", FakePayload())
    key2 = compute_cache_key("pdf_lesson", FakePayload())
    assert key1 == key2


def test_cache_key_differs_by_prefix():
    class FakePayload:
        def model_dump(self):
            return {"topic": "Fotosyntese", "level": "VG1"}

    key1 = compute_cache_key("pdf_lesson", FakePayload())
    key2 = compute_cache_key("pdf_diff", FakePayload())
    assert key1 != key2


def test_cache_key_differs_by_content():
    class PayloadA:
        def model_dump(self):
            return {"topic": "Fotosyntese", "level": "VG1"}

    class PayloadB:
        def model_dump(self):
            return {"topic": "Celleånding", "level": "VG1"}

    assert compute_cache_key("pdf_lesson", PayloadA()) != compute_cache_key("pdf_lesson", PayloadB())
