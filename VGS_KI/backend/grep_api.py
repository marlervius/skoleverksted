"""
Grep API — Utdanningsdirektoratets åpne API for LK20-læreplanen.
Henter kompetansemål for hvert fag/trinn og cacher resultater i minnet.

Dokumentasjon: https://www.udir.no/om-udir/data/kl06-grep/
"""

import logging
import time
from typing import Optional
import requests

logger = logging.getLogger(__name__)

# ── Fagkoder for VGS i LK20 ──────────────────────────────────────────────────
# Grep-koder for læreplaner som gjelder VGS.
# Kilde: https://data.udir.no/api/kl06/laereplaner?spraak=nob
SUBJECT_TO_CURRICULUM: dict[str, list[str]] = {
    "Norsk":        ["NOR1-05"],
    "Engelsk":      ["ENG1-04"],
    "Samfunnsfag":  ["SAF1-03"],
    "Naturfag":     ["NAT1-03"],
    "Matematikk":   ["MAT1-04", "MAT1-05"],
    "Historie":     ["HIS1-03"],
    "Geografi":     ["GEO1-02"],
    "Religion":     ["REL1-02"],
    "Kroppsøving":  ["KRO1-05"],
}

GREP_BASE = "https://data.udir.no/api/kl06"
HEADERS   = {"Accept": "application/json", "User-Agent": "VGS-Laererassistent/1.0"}
TIMEOUT   = 10  # sekunder

# ── In-memory cache: { cache_key: (timestamp, data) } ───────────────────────
_cache: dict[str, tuple[float, list]] = {}
CACHE_TTL = 3600 * 12  # 12 timer


def _cached_get(url: str) -> Optional[list | dict]:
    """GET med in-memory cache."""
    now = time.time()
    if url in _cache:
        ts, data = _cache[url]
        if now - ts < CACHE_TTL:
            return data

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "json" not in content_type:
            logger.warning(
                f"Grep API returnerte uventet Content-Type ({content_type}) for {url} "
                f"— body: {resp.text[:120]!r}"
            )
            return None
        data = resp.json()
        _cache[url] = (now, data)
        return data
    except requests.RequestException as e:
        logger.warning(f"Grep API feil ({url}): {e}")
        return None
    except ValueError as e:
        logger.warning(f"Grep API ugyldig JSON ({url}): {e}")
        return None


def get_competency_goals(subject: str, level: str) -> list[dict]:
    """
    Hent kompetansemål fra Grep for et gitt fag og trinn.

    Returns:
        Liste med dicts: [{"kode": "...", "tittel": "...", "laereplan": "..."}, ...]
        Tom liste ved feil eller ukjent fag.
    """
    curriculum_codes = SUBJECT_TO_CURRICULUM.get(subject, [])
    if not curriculum_codes:
        logger.info(f"Ingen Grep-kode for fag: {subject}")
        return []

    goals: list[dict] = []
    for kode in curriculum_codes:
        url = f"{GREP_BASE}/kompetansemaal?spraak=nob&laereplan={kode}"
        data = _cached_get(url)
        if not data or not isinstance(data, list):
            continue

        for item in data:
            tittel = ""
            # Grep returnerer tittel som liste av {spraak, verdi}-objekter
            if isinstance(item.get("tittel"), list):
                for t in item["tittel"]:
                    if t.get("spraak") == "nob":
                        tittel = t.get("verdi", "")
                        break
            elif isinstance(item.get("tittel"), str):
                tittel = item["tittel"]

            if not tittel:
                continue

            goals.append({
                "kode":      item.get("kode", ""),
                "tittel":    tittel,
                "laereplan": kode,
            })

    logger.info(f"Grep: {len(goals)} kompetansemål for {subject} ({', '.join(curriculum_codes)})")
    return goals
