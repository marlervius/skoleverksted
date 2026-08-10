"""TeachingPackage domain rules and deterministic first-draft generation."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable

from .compendium import _source_quality_notes
from .models import (
    ArtifactSpec,
    CompendiumSource,
    QualityPassportRequest,
    TeachingArtifact,
    TeachingArtifactType,
    TeachingPackage,
    TeachingPackagePlan,
    TruthSource,
    YearPlan,
    YearPlanPeriod,
    utc_now,
)
from .quality import build_quality_passport


ARTIFACT_TITLES: dict[TeachingArtifactType, str] = {
    "presentation": "Presentasjon",
    "student_sheet": "Læringsark og elevtekst",
    "exercise_sheet": "Oppgaveark",
    "answer_key": "Fasit",
    "teacher_guide": "Lærerveiledning",
}


def content_digest(content: str) -> str:
    return hashlib.sha256(content.replace("\r\n", "\n").strip().encode("utf-8")).hexdigest()


def _source_models(sources: Iterable[TruthSource]) -> list[TruthSource]:
    return list(sources)[:50]


def _period_snapshot(plan: YearPlan, period: YearPlanPeriod) -> dict[str, object]:
    return {
        "year_plan_id": plan.id,
        "period_id": period.id,
        "year_plan_title": plan.title,
        "school_year": plan.school_year,
        "subject": plan.subject,
        "level": plan.level,
        "period": period.model_dump(mode="json"),
        "captured_at": utc_now(),
    }


def _specs(types: Iterable[TeachingArtifactType]) -> list[ArtifactSpec]:
    seen: set[str] = set()
    result: list[ArtifactSpec] = []
    for index, artifact_type in enumerate(types):
        if artifact_type in seen:
            continue
        seen.add(artifact_type)
        result.append(
            ArtifactSpec(
                artifact_type=artifact_type,
                title=ARTIFACT_TITLES[artifact_type],
                required=True,
                order=index,
            )
        )
    if not result:
        raise ValueError("Velg minst ett artefaktformat.")
    return result


def build_package_from_period(
    plan: YearPlan,
    period: YearPlanPeriod,
    *,
    artifact_types: Iterable[TeachingArtifactType],
    audience: str = "Elever",
    source_brief: str = "",
    sources: Iterable[TruthSource] = (),
    title: str | None = None,
    project_id: str | None = None,
) -> TeachingPackage:
    source_models = _source_models(sources)
    specs = _specs(artifact_types)
    package_title = title or period.theme or period.title
    package_id = hashlib.sha256(
        f"{plan.id}:{period.id}:{package_title}:{utc_now()}".encode("utf-8")
    ).hexdigest()[:32]
    plan_payload = TeachingPackagePlan(
        theme=period.theme or period.title,
        period_title=period.title,
        subject=plan.subject,
        level=plan.level,
        audience=audience,
        lesson_count=period.lesson_count,
        lesson_minutes=plan.lesson_minutes,
        duration_weeks=period.duration_weeks,
        competency_goals=list(dict.fromkeys([*plan.competency_goals, *period.competency_goals]))[:30],
        learning_goals=period.learning_goals[:20],
        key_concepts=period.key_concepts[:30],
        suggested_activities=period.suggested_activities[:20],
        assessment=period.assessment,
        teacher_notes=period.teacher_notes,
        overview=period.overview,
        source_brief=source_brief,
        sources=source_models,
        artifact_specs=specs,
        period_snapshot=_period_snapshot(plan, period),
    )
    artifacts = [
        TeachingArtifact(
            id=hashlib.sha256(f"{package_id}:{spec.artifact_type}".encode("utf-8")).hexdigest()[:32],
            package_id=package_id,
            artifact_type=spec.artifact_type,
            required=spec.required,
            title=f"{package_title} – {spec.title}",
            order=spec.order,
            package_revision=1,
        )
        for spec in specs
    ]
    package = TeachingPackage(
        id=package_id,
        year_plan_id=plan.id,
        period_id=period.id,
        project_id=project_id,
        subject=plan.subject,
        level=plan.level,
        title=package_title,
        audience=audience,
        source_brief=source_brief,
        sources=source_models,
        artifact_types=[spec.artifact_type for spec in specs],
        plan=plan_payload,
        artifacts=artifacts,
    )
    return with_revision_digest(package)


def with_revision_digest(package: TeachingPackage) -> TeachingPackage:
    manifest = {
        "id": package.id,
        "package_revision": package.package_revision,
        "artifacts": [
            {
                "id": artifact.id,
                "type": artifact.artifact_type,
                "content_revision": artifact.content_revision,
                "package_revision": artifact.package_revision,
                "files": [file.model_dump(mode="json") for file in artifact.files],
            }
            for artifact in sorted(package.artifacts, key=lambda item: item.order)
        ],
    }
    package.revision_digest = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return package


def _goals(package: TeachingPackage) -> str:
    return "\n".join(f"- {goal}" for goal in package.plan.learning_goals) or "- Forklar hva elevene skal kunne etter økten."


def _concepts(package: TeachingPackage) -> str:
    return ", ".join(package.plan.key_concepts) or "begreper, sammenhenger og kildebruk"


def _source_note(package: TeachingPackage) -> str:
    if package.plan.sources:
        return "\n".join(f"- {source.title}: {source.url}" for source in package.plan.sources)
    return "- Ingen konkrete kilder er registrert ennå. Legg inn kilder før godkjenning."


def draft_content(package: TeachingPackage, artifact_type: TeachingArtifactType) -> str:
    """Create a coherent, source-aware scaffold shared by every artifact."""
    title = package.title
    theme = package.plan.theme
    overview = package.plan.overview or f"Arbeid med {theme} gjennom forklaring, kildearbeid og elevaktivitet."
    goals = _goals(package)
    concepts = _concepts(package)
    activities = "\n".join(f"- {item}" for item in package.plan.suggested_activities) or "- Kort inngangsspørsmål\n- Kilde- eller begrepsarbeid\n- Oppsummering og exit ticket"
    sources = _source_note(package)
    if artifact_type == "presentation":
        return f"""# {title}
## Tittel og inngangsspørsmål
Hva forbinder du med {theme}? Skriv ned én idé og ett spørsmål.
## Læringsmål
{goals}
## Aktiver forkunnskaper
Del et eksempel fra før. Hva vet klassen allerede, og hva må undersøkes?
## Faglig forklaring
{overview} Begrepene {concepts} brukes for å strukturere arbeidet.
## Begreper
Forklar {concepts} med egne ord, og vis hvordan minst to av dem henger sammen.
## Kilde eller eksempel
Les den oppgitte kilden med spørsmålet: Hva dokumenterer kilden, og hva dokumenterer den ikke?
## Samtale og refleksjon
Hvilken forklaring er best begrunnet? Hvilken påstand trenger mer dokumentasjon?
## Elevaktivitet
{activities}
## Oppsummering
Formuler tre setninger: én sikker observasjon, én sammenheng og én åpen problemstilling.
## Exit ticket
Skriv ett begrep du kan forklare, én kilde du vil undersøke, og ett spørsmål du fortsatt har.
"""
    if artifact_type == "student_sheet":
        return f"""# {title}
## Dette skal du lære
{goals}
## Faglig ramme
{overview}

Når du arbeider med {theme}, skal du skille mellom det en kilde faktisk viser, og det du tolker. Bruk begrepene {concepts} aktivt i svarene dine.
## Arbeidsmåte
1. Les teksten og marker sentrale begreper.
2. Skriv en kort forklaring med egne ord.
3. Finn støtte i kildene og noter hva som fortsatt er usikkert.
## Kilder
{sources}
"""
    if artifact_type == "exercise_sheet":
        return f"""# {title}
## Før du begynner
Bruk læringsarket og kildene. Svar med hele setninger når oppgaven ber om forklaring.
## Oppgaver
1. Forklar med egne ord hva {theme} handler om.
2. Definer begrepene {concepts} og bruk minst to av dem i samme eksempel.
3. Velg én kilde. Skriv hva kilden kan brukes til, og hva den ikke kan dokumentere alene.
4. Sammenlign to perspektiver eller eksempler fra perioden. Vis både en likhet og en forskjell.
5. Skriv et kort, begrunnet svar på spørsmålet: Hva er den viktigste sammenhengen i temaet?
## Egenvurdering
Jeg kan forklare målene: ___   Jeg kan bruke kilder: ___   Jeg trenger mer hjelp med: ___
"""
    if artifact_type == "answer_key":
        return f"""# {title}
## Veiledende svar
1. Et godt svar forklarer {theme} presist, bruker minst ett relevant eksempel og skiller mellom observasjon og tolkning.
2. Begrepene {concepts} skal defineres faglig, men med elevens egne ord. Begrepene må brukes i en sammenheng, ikke bare listes.
3. Kilden skal knyttes til en konkret påstand. Et godt svar nevner også en begrensning ved kilden.
4. Sammenligningen skal ha minst én tydelig likhet, én forskjell og en forklaring på hvorfor forskjellen er relevant.
5. Begrunnelsen skal bygge på tekst eller kilde. Alternative svar kan godtas når de er faglig og kildebasert begrunnet.
## Vurderingsnotat
Fasiten er veiledende. Læreren må bruke periode, kompetansemål og elevens begrunnelse i vurderingen.
"""
    return f"""# {title}
## Før timen
Les gjennom læringsmål, kilder og oppgaver. Velg hvilke deler som passer til {package.plan.lesson_count} undervisningstimer på {package.plan.lesson_minutes} minutter.
## Forslag til gjennomføring
1. Start med inngangsspørsmålet og aktiver forkunnskaper.
2. Gi en kort faglig forklaring og la elevene arbeide med begrepene {concepts}.
3. La elevene løse oppgavene individuelt eller i par, og be dem vise kildegrunnlaget.
4. Samle opp med en kort samtale og exit ticket.
## Differensiering og vurdering
Tilpass tekstmengde, støttespørsmål og krav til kildebruk til elevgruppen. Bruk fasiten som samtalegrunnlag, ikke som eneste vurderingskriterium.
## Begrensninger og kilder
Kildene må leses av læreren før bruk. Uavklarte faktapåstander skal stå som lærerreview og ikke presenteres som sikre.
{sources}
"""


def build_quality(package: TeachingPackage, artifact: TeachingArtifact, *, compiled: bool) -> object:
    return build_quality_passport(
        QualityPassportRequest(
            module="teaching-package",
            title=artifact.title,
            content=artifact.content_markdown,
            sources=[source.url for source in artifact.sources or package.plan.sources],
            competency_goals=package.plan.competency_goals,
            has_answer_key=artifact.artifact_type == "answer_key" or any(
                item.artifact_type == "answer_key" for item in package.artifacts
            ),
            compiled=compiled,
            prompt_version="teaching-package-deterministic-v1",
        )
    )


def source_notes(sources: Iterable[TruthSource]) -> list[str]:
    return _source_quality_notes([
        CompendiumSource(
            title=source.title,
            url=source.url,
            publisher=source.publisher,
            origin=source.origin,
            fetch_status=source.fetch_status,
        )
        for source in sources
    ])


def can_approve_artifact(artifact: TeachingArtifact) -> list[str]:
    reasons: list[str] = []
    if not artifact.content_markdown.strip():
        reasons.append("Artefaktet har ikke innhold.")
    if not artifact.truth_passport:
        reasons.append("Faktapasset mangler. Kjør faktapasset på nytt.")
    elif artifact.truth_passport.version != "2.0":
        reasons.append("Faktapasset er fra en eldre kvalitetsmodell. Kjør faktapasset på nytt.")
    elif artifact.truth_passport.status != "verified":
        reasons.append(
            f"Faktapasset er ikke grønt ({artifact.truth_passport.verified_claims} av "
            f"{artifact.truth_passport.total_claims} påstander verifisert)."
        )
    elif artifact.truth_passport.content_revision != artifact.content_revision:
        reasons.append("Faktapasset gjelder en eldre innholdsrevisjon. Kjør på nytt.")
    if not artifact.quality_passport:
        reasons.append("Kvalitetspasset mangler.")
    elif artifact.quality_passport.overall_status == "failed":
        reasons.append("Kvalitetspasset har en blokkert kontroll.")
    if artifact.source_quality_notes:
        reasons.append("Kildesjekken har åpne merknader: " + "; ".join(artifact.source_quality_notes[:3]))
    if artifact.generation_token or artifact.status == "generating":
        reasons.append("Artefaktet er fortsatt under generering.")
    if not artifact.files:
        reasons.append("Det finnes ingen ferdig fil for artefaktet.")
    if artifact.approved_revision and artifact.approved_revision != artifact.content_revision:
        reasons.append("Tidligere godkjenning gjelder ikke denne innholdsrevisjonen.")
    return reasons


def can_approve_package(package: TeachingPackage) -> list[str]:
    reasons: list[str] = []
    required = [artifact for artifact in package.artifacts if artifact.required]
    if not required:
        reasons.append("Pakken mangler obligatoriske artefakter.")
    for artifact in required:
        for reason in can_approve_artifact(artifact):
            reasons.append(f"{artifact.title}: {reason}")
        if artifact.status != "approved":
            reasons.append(f"{artifact.title}: artefaktet er ikke lærer-godkjent.")
        if artifact.package_revision != package.package_revision:
            reasons.append(f"{artifact.title}: tilhører en eldre pakkerevisjon.")
    if any(
        artifact.status in {"planned", "generating"}
        or artifact.generation_token
        for artifact in package.artifacts
    ):
        reasons.append("Pakken har fortsatt aktive eller uferdige artefaktjobber.")
    return list(dict.fromkeys(reasons))


def can_approve_package_with_exceptions(package: TeachingPackage) -> list[str]:
    """Validate mechanics while making the responsibility decision explicit.

    This path deliberately does not call the source-approval gate. It still
    requires a current, renderable artifact and an idle job, so responsibility
    approval cannot unlock stale or half-built files.
    """
    reasons: list[str] = []
    required = [artifact for artifact in package.artifacts if artifact.required]
    if not required:
        reasons.append("Pakken mangler obligatoriske artefakter.")
    for artifact in required:
        if not artifact.content_markdown.strip():
            reasons.append(f"{artifact.title}: artefaktet har ikke innhold.")
        if not artifact.files:
            reasons.append(f"{artifact.title}: det finnes ingen ferdig fil.")
        if artifact.generation_token or artifact.status == "generating":
            reasons.append(f"{artifact.title}: artefaktet er fortsatt under arbeid.")
        if artifact.package_revision != package.package_revision:
            reasons.append(f"{artifact.title}: tilhører en eldre pakkerevisjon.")
    return list(dict.fromkeys(reasons))


def unresolved_claims(package: TeachingPackage) -> list[str]:
    result: list[str] = []
    for artifact in package.artifacts:
        result.extend(
            f"{artifact.title}: {item.original_text}"
            for item in artifact.quarantine
            if item.status == "withheld"
        )
        quarantined_ids = {item.claim_id for item in artifact.quarantine}
        result.extend(
            f"{artifact.title}: {claim.claim}"
            for claim in (artifact.truth_passport.claims if artifact.truth_passport else [])
            if claim.status != "verified" and claim.id not in quarantined_ids
        )
    return result


def aggregate_package_status(package: TeachingPackage) -> str:
    statuses = {artifact.status for artifact in package.artifacts}
    # Package approval is a separate projection transaction. Never expose a
    # package as approved merely because all child artifacts are approved.
    if (
        package.approved_at
        and package.approved_revision == package.package_revision
        and all(artifact.status == "approved" for artifact in package.artifacts)
    ):
        return "approved"
    if any(status == "generating" for status in statuses):
        return "generating"
    if any(status in {"generation_incomplete", "verification_failed", "parse_failure", "language_quality_failed", "source_grounding_failed"} for status in statuses):
        return "needs_review"
    if any(status in {"needs_revision", "superseded", "cancelled"} for status in statuses):
        return "needs_revision"
    if any(status in {"generated", "needs_review", "reviewed_with_issues"} for status in statuses):
        return "needs_review"
    return "draft"
