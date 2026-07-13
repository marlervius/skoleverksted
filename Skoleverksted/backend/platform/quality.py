from __future__ import annotations

import re

from .models import QualityCheck, QualityPassport, QualityPassportRequest


def build_quality_passport(request: QualityPassportRequest) -> QualityPassport:
    content = request.content.strip()
    word_count = len(re.findall(r"\b[\wÆØÅæøå-]+\b", content, flags=re.UNICODE))
    checks: list[QualityCheck] = []

    checks.append(QualityCheck(
        code="content_present",
        label="Innhold finnes",
        status="passed" if word_count >= 40 else "failed",
        detail=f"{word_count} ord analysert; minst 40 kreves for kvalitetsvurdering.",
    ))
    checks.append(QualityCheck(
        code="sources",
        label="Kildebelegg",
        status="passed" if request.sources else "warning",
        detail=f"{len(request.sources)} kilde(r) registrert." if request.sources else "Ingen etterprøvbare kilder er registrert.",
    ))
    if request.sources:
        citation_markers = len(re.findall(r"\[K\]|\[[0-9]+\]|kilde:", content, flags=re.IGNORECASE))
        checks.append(QualityCheck(
            code="source_traceability",
            label="Sporbare kildepåstander",
            status="passed" if citation_markers else "warning",
            detail=f"{citation_markers} kildemarkør(er) funnet." if citation_markers else "Kilder er registrert, men teksten har ingen tydelige kildemarkører.",
        ))
    checks.append(QualityCheck(
        code="competency_goals",
        label="Kompetansemål",
        status="passed" if request.competency_goals else "warning",
        detail=f"{len(request.competency_goals)} mål registrert." if request.competency_goals else "Kompetansemål er ikke koblet til produktet.",
    ))
    checks.append(QualityCheck(
        code="answer_key",
        label="Fasit",
        status=("passed" if request.has_answer_key else "warning") if request.has_answer_key is not None else "not_applicable",
        detail="Fasit er inkludert." if request.has_answer_key else "Fasit er ikke bekreftet.",
    ))
    checks.append(QualityCheck(
        code="compiled",
        label="Dokumentkontroll",
        status=("passed" if request.compiled else "failed") if request.compiled is not None else "not_applicable",
        detail="Dokumentet er kompilert." if request.compiled else "Kompilering er ikke bekreftet.",
    ))

    normalized_lines = [line.strip().lower() for line in content.splitlines() if len(line.strip()) >= 30]
    duplicate_lines = len(normalized_lines) - len(set(normalized_lines))
    checks.append(QualityCheck(
        code="duplication",
        label="Ingen utilsiktet gjentakelse",
        status="passed" if duplicate_lines == 0 else "warning",
        detail="Ingen dupliserte lengre linjer funnet." if duplicate_lines == 0 else f"{duplicate_lines} lengre linje(r) gjentas.",
    ))
    placeholders = re.findall(r"\b(?:TODO|TBD|LOREM IPSUM|IMAGE_URL:\s*none)\b", content, flags=re.IGNORECASE)
    checks.append(QualityCheck(
        code="placeholders",
        label="Ingen uferdige plassholdere",
        status="passed" if not placeholders else "failed",
        detail="Ingen kjente plassholdere funnet." if not placeholders else f"Fant {len(placeholders)} uferdig(e) plassholder(e).",
    ))

    if request.math_incorrect is not None:
        checks.append(QualityCheck(
            code="math_correctness",
            label="Matematisk korrekthet",
            status="failed" if request.math_incorrect else ("warning" if (request.math_unparseable or 0) else "passed"),
            detail=f"{request.math_incorrect} feil og {request.math_unparseable or 0} uttrykk som ikke kunne verifiseres.",
        ))

    applicable = [check for check in checks if check.status != "not_applicable"]
    weights = {"passed": 100, "warning": 55, "failed": 0}
    score = round(sum(weights[check.status] for check in applicable) / max(1, len(applicable)))
    has_failed = any(check.status == "failed" for check in applicable)
    has_warning = any(check.status == "warning" for check in applicable)
    overall = "failed" if has_failed else "needs_review" if has_warning else "passed"

    limitations: list[str] = []
    if not request.sources:
        limitations.append("Faktapåstander er ikke kontrollert mot registrerte kilder.")
    if request.math_unparseable:
        limitations.append(f"{request.math_unparseable} matematiske uttrykk krevde manuell kontroll.")
    if request.prompt_version == "unknown":
        limitations.append("Promptversjon var ikke oppgitt.")

    return QualityPassport(
        module=request.module,
        title=request.title,
        overall_status=overall,
        score=score,
        checks=checks,
        sources=request.sources,
        competency_goals=request.competency_goals,
        limitations=limitations,
        prompt_version=request.prompt_version,
    )
