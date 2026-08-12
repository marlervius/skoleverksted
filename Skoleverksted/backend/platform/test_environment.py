"""Guards for the isolated local and CI test profile.

The application remains unchanged for development and production profiles.
When ``APP_ENV=test`` is selected, the default platform store must point at a
run-local directory and may not use a configured remote database. Explicit
fixture stores (``PlatformStore(path)``) remain available to unit tests.
"""

from __future__ import annotations

import os
from pathlib import Path


def _inside(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def assert_test_storage_safe() -> None:
    """Fail closed if the default store could touch non-test data."""

    if os.getenv("APP_ENV", "").strip().casefold() != "test":
        return

    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        raise RuntimeError(
            "APP_ENV=test avviser DATABASE_URL. Testkjøringen må bruke lokal, isolert lagring."
        )

    test_data = os.getenv("TEST_DATA_DIR", "").strip()
    if not test_data:
        raise RuntimeError(
            "APP_ENV=test krever TEST_DATA_DIR slik at produksjonslagring ikke kan brukes ved et uhell."
        )

    root = Path(test_data).expanduser().resolve()
    configured_db = os.getenv("SKOLEVERKSTED_DB_PATH", "").strip()
    db_path = (
        Path(configured_db).expanduser().resolve()
        if configured_db
        else (Path(os.getenv("OUTPUT_DIR", str(root))) / "platform" / "skoleverksted.sqlite3").resolve()
    )
    if not _inside(db_path, root):
        raise RuntimeError(
            "APP_ENV=test avviser en database utenfor TEST_DATA_DIR. "
            "Slett ikke eller koble til produksjonsdata fra tester."
        )
