from __future__ import annotations

from pathlib import Path

import pytest

from Skoleverksted.backend.platform.test_environment import assert_test_storage_safe


def test_test_profile_accepts_only_run_local_storage(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TEST_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SKOLEVERKSTED_DB_PATH", str(tmp_path / "platform.sqlite3"))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert_test_storage_safe() is None


def test_test_profile_rejects_remote_database(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TEST_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SKOLEVERKSTED_DB_PATH", str(tmp_path / "platform.sqlite3"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://production.example/skoleverksted")

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        assert_test_storage_safe()


def test_test_profile_rejects_database_outside_run_directory(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TEST_DATA_DIR", str(tmp_path / "test-data"))
    monkeypatch.setenv("SKOLEVERKSTED_DB_PATH", str(tmp_path / "production.sqlite3"))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="utenfor TEST_DATA_DIR"):
        assert_test_storage_safe()
