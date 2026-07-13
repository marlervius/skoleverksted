"""Tests for config.py — defaults and env-var overrides."""
import importlib
import os
import pytest


def _reload_config():
    import config
    importlib.reload(config)
    return config


def test_defaults():
    cfg = _reload_config()
    assert cfg.AGENT_TIMEOUT_SECONDS == 300
    assert cfg.SSE_HEARTBEAT_SECONDS == 30
    assert cfg.CACHE_TTL_SECONDS == 86400 * 7
    assert cfg.GREP_CACHE_TTL_SECONDS == 60 * 60 * 12
    assert cfg.JOB_TTL_SECONDS == 60 * 60
    assert cfg.JOB_CLEANUP_INTERVAL_SECONDS == 5 * 60
    assert cfg.MAX_IMAGE_BASE64_BYTES == 7 * 1024 * 1024
    assert cfg.MAX_PARALLEL_AGENT_TASKS == 5
    assert cfg.RATE_LIMIT_GENERATE == "5/minute"
    assert cfg.RATE_LIMIT_GREP == "30/minute"


def test_cors_default():
    cfg = _reload_config()
    assert "http://localhost:3000" in cfg.ALLOWED_ORIGINS


def test_env_int_override(monkeypatch):
    monkeypatch.setenv("AGENT_TIMEOUT_SECONDS", "60")
    cfg = _reload_config()
    assert cfg.AGENT_TIMEOUT_SECONDS == 60


def test_env_int_invalid_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("AGENT_TIMEOUT_SECONDS", "not_a_number")
    cfg = _reload_config()
    assert cfg.AGENT_TIMEOUT_SECONDS == 300


def test_env_int_empty_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("AGENT_TIMEOUT_SECONDS", "")
    cfg = _reload_config()
    assert cfg.AGENT_TIMEOUT_SECONDS == 300


def test_env_list_override(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com,https://staging.example.com")
    cfg = _reload_config()
    assert "https://app.example.com" in cfg.ALLOWED_ORIGINS
    assert "https://staging.example.com" in cfg.ALLOWED_ORIGINS
    assert len(cfg.ALLOWED_ORIGINS) == 2


def test_env_list_empty_uses_default(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    cfg = _reload_config()
    assert "http://localhost:3000" in cfg.ALLOWED_ORIGINS


def test_rate_limit_override(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_GENERATE", "10/minute")
    cfg = _reload_config()
    assert cfg.RATE_LIMIT_GENERATE == "10/minute"
