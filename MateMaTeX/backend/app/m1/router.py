"""M1 empirical fasit coverage — read-only API for the frontend."""

from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter

from m1.scorer import report_json, resolve_m1_csv_path

logger = structlog.get_logger()

router = APIRouter(prefix="/m1", tags=["m1"])


@router.get("/report")
async def get_m1_report():
    """
    Poengvektet SymPy-dekning fra M1-skjema (CSV).

    Uses m1_skjema.csv when populated; otherwise the documented example dataset.
    """
    csv_path = resolve_m1_csv_path()
    data = report_json(str(csv_path))
    data["is_example"] = csv_path.name == "m1_skjema_eksempel.csv"
    logger.info("m1_report_served", source=str(csv_path), is_example=data["is_example"])
    return data
