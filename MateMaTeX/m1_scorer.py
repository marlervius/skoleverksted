#!/usr/bin/env python3
"""Launcher for M1-scorer (repo root). Se M1-testprotokoll.md."""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from m1.scorer import answer_check, report  # noqa: E402,F401

if __name__ == "__main__":
    if len(sys.argv) > 1:
        report(sys.argv[1])
    else:
        print("Bruk: python m1_scorer.py m1_skjema.csv")
        print("Eksempel: python m1_scorer.py m1_skjema_eksempel.csv")
