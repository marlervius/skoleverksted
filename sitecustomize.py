"""Test-only isolation for third-party import-time storage.

CrewAI's dependency ``appdirs`` resolves Windows Known Folders through the
Shell API and ignores ``TEMP``/``LOCALAPPDATA`` overrides. When the explicit
test profile is active, redirect only that lookup to the run-local directory.
The module is inert in development and production profiles.
"""

from __future__ import annotations

import os
from pathlib import Path


if os.getenv("APP_ENV", "").strip().casefold() == "test":
    test_data_dir = os.getenv("TEST_DATA_DIR", "").strip()
    if test_data_dir:
        try:
            import appdirs

            isolated_base = (Path(test_data_dir).expanduser().resolve() / "third-party-data")

            def _isolated_known_folder(_: str) -> str:
                isolated_base.mkdir(parents=True, exist_ok=True)
                return str(isolated_base)

            if getattr(appdirs, "system", "") == "win32":
                appdirs._get_win_folder = _isolated_known_folder
        except ImportError:
            pass
