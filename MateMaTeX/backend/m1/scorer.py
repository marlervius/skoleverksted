"""
M1-scorer for MateMaTeX — referanseimplementasjon.

To formaal:
  1) answer_check(): robust SymPy-ekvivalenssjekk (true_answer vs kandidat),
     som skiller VERIFIED / MISMATCH / UNCERTAIN.
  2) aggregate(): leser et utfylt skaaringsskjema (CSV) og regner ut
     poengvektet groenn dekning per nivaa + per emne.

Standalone. Avhenger kun av sympy. Ikke koblet til pipelinen — bevisst,
saa tallet maales uavhengig av implementasjonen som skal haandheve det.

Se M1-testprotokoll.md i repo-roten for prosedyre.
"""
from __future__ import annotations

import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
VERIFIED, MISMATCH, UNCERTAIN = "VERIFIED", "MISMATCH", "UNCERTAIN"


def _parse(s):
    return parse_expr(str(s), transformations=TRANSFORMS, evaluate=True)


MAX_VARS = 4  # skolematematikk har sjelden >4 distinkte variabler; flere => prosa


def looks_like_prose(*exprs) -> bool:
    """Implisitt multiplikasjon sprer fri tekst til produkt av enkeltbokstaver."""
    for e in exprs:
        try:
            if len(e.free_symbols) > MAX_VARS:
                return True
        except Exception:
            return True
    return False


def numeric_agreement(a, b, symbols, trials=12, tol=1e-9):
    """Spot-sjekk numerisk paa tilfeldige punkter. Returnerer True/False/None."""
    syms = sorted(symbols, key=str)
    agree = disagree = 0
    rng = random.Random(20260618)
    for _ in range(trials):
        subs = {s: sp.Rational(rng.randint(-50, 50), rng.randint(1, 9)) for s in syms}
        try:
            va = complex(a.subs(subs))
            vb = complex(b.subs(subs))
        except Exception:
            continue
        if any(map(lambda z: z != z or abs(z) == float("inf"), [va, vb])):
            continue
        if abs(va - vb) <= tol * (1 + abs(va)):
            agree += 1
        else:
            disagree += 1
    if agree == 0 and disagree == 0:
        return None
    if disagree == 0:
        return True
    if agree == 0:
        return False
    return None


def answer_check(true_answer: str, candidate: str, mode: str = "expr") -> str:
    """
    mode:
      'expr'     - to uttrykk skal vaere identiske
      'integral' - identiske opp til konstant (df/dx like)
      'set'      - loesningsmengder (komma/semikolon-separert) skal vaere like
    """
    try:
        if mode == "set":
            def to_set(s):
                parts = str(s).replace("{", "").replace("}", "").replace(";", ",").split(",")
                return {sp.nsimplify(_parse(p)) for p in parts if p.strip()}

            return VERIFIED if to_set(true_answer) == to_set(candidate) else MISMATCH

        t, c = _parse(true_answer), _parse(candidate)
        if looks_like_prose(t, c):
            return UNCERTAIN

        if mode == "integral":
            free = t.free_symbols | c.free_symbols
            x = sorted(free, key=str)[0] if free else sp.Symbol("x")
            d = sp.simplify(sp.diff(t - c, x))
            if d == 0:
                return VERIFIED
            num = numeric_agreement(sp.diff(t, x), sp.diff(c, x), free)
            return VERIFIED if num is True else (MISMATCH if num is False else UNCERTAIN)

        diff = sp.simplify(t - c)
        if diff == 0:
            return VERIFIED
        num = numeric_agreement(t, c, t.free_symbols | c.free_symbols)
        if num is True:
            return VERIFIED
        if num is False:
            return MISMATCH
        return UNCERTAIN
    except Exception:
        return UNCERTAIN


GREEN = {"verified"}
RECOVERABLE = {"false_negative"}
RED = {"unverifiable", "mismatch"}


def aggregate(csv_path: str):
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    by_level = defaultdict(lambda: defaultdict(float))
    by_topic = defaultdict(lambda: defaultdict(float))
    for r in rows:
        if not r.get("nivaa", "").strip():
            continue
        lvl, emne = r["nivaa"].strip(), r["emne"].strip()
        p = float(r["poeng"])
        res = r["resultat"].strip().lower()
        by_level[lvl]["poeng"] += p
        by_topic[(lvl, emne)]["poeng"] += p
        for bucket, names in (("groenn", GREEN), ("fiksbar", RECOVERABLE), ("roed", RED)):
            if res in names:
                by_level[lvl][bucket] += p
                by_topic[(lvl, emne)][bucket] += p
    return by_level, by_topic


def _pct(part, whole):
    return 0.0 if whole == 0 else 100 * part / whole


def resolve_m1_csv_path() -> Path:
    """Prefer filled M1 data; fall back to the packaged example.

    Render builds with ``backend/`` as Docker context, so CSV files in the
    repository root are unavailable in production. Keep a packaged fallback
    next to this module while still preferring real root-level data locally.
    """
    root = Path(__file__).resolve().parents[2]
    package_dir = Path(__file__).resolve().parent

    for primary in (root / "m1_skjema.csv", package_dir / "m1_skjema.csv"):
        if primary.is_file():
            with primary.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            if any(r.get("nivaa", "").strip() for r in rows):
                return primary

    for example in (
        root / "m1_skjema_eksempel.csv",
        package_dir / "m1_skjema_eksempel.csv",
    ):
        if example.is_file():
            return example

    raise FileNotFoundError("M1 scoring data is not installed")


def report_json(csv_path: str) -> dict:
    """Structured M1 report for API/UI consumption."""
    by_level, by_topic = aggregate(csv_path)
    levels = []
    for lvl, d in sorted(by_level.items()):
        tot = d["poeng"]
        green = _pct(d["groenn"], tot)
        fixable = _pct(d["fiksbar"], tot)
        levels.append(
            {
                "level": lvl,
                "total_points": tot,
                "green_pct": round(green, 1),
                "fixable_pct": round(fixable, 1),
                "realistic_ceiling_pct": round(green + fixable, 1),
                "red_pct": round(_pct(d["roed"], tot), 1),
            }
        )
    topics = []
    for (lvl, emne), d in sorted(by_topic.items()):
        topics.append(
            {
                "level": lvl,
                "topic": emne,
                "total_points": d["poeng"],
                "green_pct": round(_pct(d["groenn"], d["poeng"]), 1),
            }
        )
    return {
        "source": Path(csv_path).name,
        "levels": levels,
        "topics": topics,
    }


def report(csv_path: str):
    by_level, by_topic = aggregate(csv_path)
    print("=" * 64)
    print("M1-RESULTAT — poengvektet dekning")
    print("=" * 64)
    for lvl, d in sorted(by_level.items()):
        tot = d["poeng"]
        g, f = _pct(d["groenn"], tot), _pct(d["fiksbar"], tot)
        print(f"\n{lvl}  (totalt {tot:.0f} poeng)")
        print(f"  Groenn naa (verified)        : {g:5.1f} %")
        print(f"  + fiksbar (falsk negativ)    : {f:5.1f} %")
        print(f"  = realistisk tak             : {g + f:5.1f} %")
        print(f"  Roed (uverifiserbar/feil)    : {_pct(d['roed'], tot):5.1f} %")
    print("\nPer emne (groenn naa %):")
    for (lvl, emne), d in sorted(by_topic.items()):
        print(f"  {lvl:5} {emne:28} {_pct(d['groenn'], d['poeng']):5.1f} %  ({d['poeng']:.0f} p)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        report(sys.argv[1])
    else:
        print("Bruk: python -m m1.scorer <skjema.csv>")
