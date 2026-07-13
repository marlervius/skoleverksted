"""
Layout quality analysis (Track E).

Parses a TeX engine .log and turns the raw warnings into a structured,
scored :class:`LayoutReport`. This is observability-only — it never modifies
the document — so it is safe to run on every successful compile.

The preamble already applies preventive line-breaking settings
(``\\emergencystretch`` etc.), so most documents score highly; this report
surfaces the residual issues a teacher might want to know about (a stubbornly
wide table, an oversized figure, an undefined reference).
"""

from __future__ import annotations

import re

from app.models.state import LayoutIssue, LayoutReport

# "Overfull \hbox (12.34pt too wide) in paragraph at lines 40--42"
_OVERFULL_HBOX = re.compile(r"Overfull \\hbox \(([\d.]+)pt too wide\)(.*)")
_UNDERFULL_HBOX = re.compile(r"Underfull \\hbox \(badness (\d+)\)(.*)")
_OVERFULL_VBOX = re.compile(r"Overfull \\vbox \(([\d.]+)pt too high\)(.*)")
_FLOAT_TOO_LARGE = re.compile(r"Float too large for page by ([\d.]+)pt")
_UNDEFINED_REF = re.compile(r"Reference `([^']+)' on page \d+ undefined")
_CITE_UNDEFINED = re.compile(r"Citation `([^']+)' on page \d+ undefined")
_MULTIPLY_DEFINED = re.compile(r"Label `([^']+)' multiply defined")
_MISSING_CHAR = re.compile(r"Missing character: There is no (.+?) in font")

# Overfull boxes below this width are visually negligible and ignored.
_OVERFULL_IGNORE_PT = 2.0
# Above this, the overflow is likely visible (wide table/figure/long word).
_OVERFULL_SERIOUS_PT = 15.0


def analyze_log(log_text: str | None, warnings: list[str] | None = None) -> LayoutReport:
    """Build a :class:`LayoutReport` from a compilation log."""
    report = LayoutReport()
    text = log_text or ""

    issues: list[LayoutIssue] = []

    for m in _OVERFULL_HBOX.finditer(text):
        pt = float(m.group(1))
        if pt < _OVERFULL_IGNORE_PT:
            continue
        report.overfull_count += 1
        report.max_overflow_pt = max(report.max_overflow_pt, pt)
        issues.append(
            LayoutIssue(
                kind="overfull_hbox",
                severity="warning" if pt >= _OVERFULL_SERIOUS_PT else "info",
                detail=f"Linje stikker {pt:.1f}pt utenfor margen{m.group(2).strip()}",
                overflow_pt=pt,
            )
        )

    for m in _OVERFULL_VBOX.finditer(text):
        pt = float(m.group(1))
        report.max_overflow_pt = max(report.max_overflow_pt, pt)
        issues.append(
            LayoutIssue(
                kind="overfull_vbox",
                severity="warning",
                detail=f"Innhold er {pt:.1f}pt for høyt for siden",
                overflow_pt=pt,
            )
        )

    for m in _FLOAT_TOO_LARGE.finditer(text):
        pt = float(m.group(1))
        report.max_overflow_pt = max(report.max_overflow_pt, pt)
        issues.append(
            LayoutIssue(
                kind="oversized_float",
                severity="warning",
                detail=f"Figur/tabell er {pt:.1f}pt for stor for siden — vurder \\resizebox eller mindre skalering",
                overflow_pt=pt,
            )
        )

    for m in _UNDERFULL_HBOX.finditer(text):
        badness = int(m.group(1))
        if badness < 5000:  # only flag really loose lines
            continue
        report.underfull_count += 1
        issues.append(
            LayoutIssue(
                kind="underfull_hbox",
                severity="info",
                detail=f"Løs linje (badness {badness})",
            )
        )

    refs = {m.group(1) for m in _UNDEFINED_REF.finditer(text)}
    refs |= {m.group(1) for m in _CITE_UNDEFINED.finditer(text)}
    report.undefined_references = len(refs)
    for ref in sorted(refs):
        issues.append(
            LayoutIssue(
                kind="undefined_reference",
                severity="warning",
                detail=f"Udefinert referanse: `{ref}`",
            )
        )

    for ref in {m.group(1) for m in _MULTIPLY_DEFINED.finditer(text)}:
        issues.append(
            LayoutIssue(
                kind="multiply_defined",
                severity="warning",
                detail=f"Etikett definert flere ganger: `{ref}`",
            )
        )

    missing = {m.group(1) for m in _MISSING_CHAR.finditer(text)}
    if missing:
        issues.append(
            LayoutIssue(
                kind="missing_font",
                severity="warning",
                detail=f"{len(missing)} tegn mangler i valgt skrift",
            )
        )

    # Score: start at 100 and deduct by severity, capped per category so a
    # single noisy document can't go far negative.
    score = 100
    score -= min(40, report.overfull_count * 4)
    score -= min(20, sum(8 for i in issues if i.kind == "oversized_float"))
    score -= min(20, report.undefined_references * 5)
    score -= min(10, report.underfull_count * 1)
    if report.max_overflow_pt >= _OVERFULL_SERIOUS_PT:
        score -= 10
    report.score = max(0, score)

    report.issues = issues[:40]
    report.summary = _summarize(report)
    return report


def _summarize(report: LayoutReport) -> str:
    if not report.issues:
        return "Ingen layout-problemer oppdaget."
    parts: list[str] = []
    if report.overfull_count:
        parts.append(f"{report.overfull_count} linje(r) utenfor margen")
    floats = sum(1 for i in report.issues if i.kind == "oversized_float")
    if floats:
        parts.append(f"{floats} for stor(e) figur/tabell")
    if report.undefined_references:
        parts.append(f"{report.undefined_references} udefinert(e) referanse(r)")
    if report.underfull_count:
        parts.append(f"{report.underfull_count} løs(e) linje(r)")
    return "; ".join(parts) if parts else "Mindre layout-merknader."
