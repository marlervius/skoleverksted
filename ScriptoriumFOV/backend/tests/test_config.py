"""
Tests for config.py — verify defaults and types.

Run with:  pytest backend/tests/test_config.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config


def test_cache_ttl_positive():
    assert config.CACHE_TTL_SECONDS > 0


def test_google_model_is_string():
    assert isinstance(config.GOOGLE_MODEL, str)
    assert len(config.GOOGLE_MODEL) > 0


def test_max_image_bytes():
    assert config.MAX_IMAGE_BYTES == 5 * 1024 * 1024


def test_allowed_image_types():
    assert "image/jpeg" in config.ALLOWED_IMAGE_TYPES
    assert "image/png" in config.ALLOWED_IMAGE_TYPES
    assert "image/webp" in config.ALLOWED_IMAGE_TYPES


def test_pdf_thread_pool_workers_positive():
    assert config.PDF_THREAD_POOL_WORKERS >= 1


def test_typst_timeout_positive():
    assert config.TYPST_COMPILE_TIMEOUT_SECONDS > 0


def test_rate_limit_format():
    # Should look like "N/minute" or "N/second"
    assert "/" in config.RATE_LIMIT_PER_MINUTE


def test_progress_ttl_positive():
    assert config.PROGRESS_TTL_SECONDS > 0
