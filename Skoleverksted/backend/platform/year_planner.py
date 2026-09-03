from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from .models import YearPlanCreate, YearPlanGenerateRequest, YearPlanPeriod


logger = logging.getLogger(__name__)


SUBJECT_SEQUENCES: dict[str, list[tuple[str, str]]] = {
    "historie": [
        ("Historiebruk og kildekritikk", "Hvordan historisk kunnskap blir til, brukes og utfordres."),
        ("Tidlige samfunn og antikken", "Makt, samfunn, kulturmøter og varige historiske spor."),
        ("Middelalderens mangfold", "Religion, statsutvikling, handel og ulike former for avhengighet."),
        ("Renessanse, reformasjon og ekspansjon", "Nye verdensbilder, troskonflikter og globale møter."),
        ("Opplysningstid og revolusjoner", "Ideer om makt og rettigheter omsatt i politisk endring."),
        ("Industrialisering og samfunnsendring", "Teknologi, arbeid, urbanisering og sosiale forskjeller."),
        ("Nasjonalisme, demokratisering og imperier", "Statsbygging, medborgerskap og konkurrerende maktprosjekter."),
        ("Norge i det lange 1800-tallet", "Politiske, økonomiske og sosiale endringer i norsk sammenheng."),
        ("Fordypning og historisk syntese", "Kildearbeid, sammenligning, faglig argumentasjon og vurdering."),
    ],
    "naturfag": [
        ("Naturvitenskapelig praksis", "Hypoteser, modeller, målinger, usikkerhet og kildekritikk."),
        ("Celler og livsprosesser", "Sammenhenger fra cellenivå til organisme."),
        ("Energi og kjemiske reaksjoner", "Energioverføring og kjemiske forklaringsmodeller."),
        ("Klima og jordsystemer", "Samspill, tilbakekoblinger og menneskelig påvirkning."),
        ("Genetikk og evolusjon", "Arv, variasjon og naturlig seleksjon."),
        ("Teknologi, risiko og bærekraft", "Vurdering av løsninger, konsekvenser og interessekonflikter."),
    ],
    "matematikk": [
        ("Tallforståelse og regnestrategier", "Regneferdigheter, overslag og strategier i praktiske situasjoner."),
        ("Brøk, desimaltall og prosent", "Sammenhenger mellom representasjoner og bruk i hverdagsøkonomi."),
        ("Måling, enheter og praktisk økonomi", "Måling, omgjøring, priser, budsjett og fornuftige estimater."),
        ("Geometri og målestokk", "Former, areal, omkrets, volum, kart og målestokk."),
        ("Algebra, mønstre og formler", "Variabler, mønstre og formler som beskriver praktiske sammenhenger."),
        ("Statistikk og sannsynlighet", "Samle inn, lese, vurdere og presentere data."),
        ("Problemløsing i hverdagen", "Velge metode, vise framgangsmåte og vurdere om svaret er rimelig."),
        ("Repetisjon og anvendelse", "Tverrgående oppgaver som knytter sammen sentrale ferdigheter."),
    ],
    "samfunnsfag": [
        ("Samfunn, identitet og tilhørighet", "Hvordan mennesker lever sammen, former identitet og deltar i fellesskap."),
        ("Demokrati og medborgerskap", "Demokratiske prosesser, deltakelse, makt og påvirkning."),
        ("Arbeidsliv, økonomi og velferd", "Arbeid, inntekt, forbruk, offentlige tjenester og økonomiske valg."),
        ("Menneskerettigheter og rettsstat", "Rettigheter, plikter, lover og beskyttelse mot diskriminering."),
        ("Kultur, medier og kildekritikk", "Kulturuttrykk, mediebruk, informasjon og kritisk vurdering av kilder."),
        ("Bærekraft og globale utfordringer", "Lokale og globale sammenhenger, ressurser og mulige løsninger."),
        ("Norge og verden", "Norges plass i verden, samarbeid, konflikter og samfunnsendringer."),
        ("Repetisjon og anvendelse", "Tverrgående oppgaver som knytter sammen sentrale samfunnsfaglige begreper."),
    ],
    "norsk": [
        ("Lesing og tekstforståelse", "Strategier for å tolke, sammenligne og vurdere tekster."),
        ("Sakprosa og argumentasjon", "Påstander, belegg, retorikk og kritisk kildebruk."),
        ("Muntlig kommunikasjon", "Faglig samtale, presentasjon og lytting."),
        ("Skriveprosesser", "Planlegging, respons, revisjon og språklige valg."),
        ("Litteratur i kontekst", "Tekster, perioder, identitet og samfunn."),
        ("Språk, makt og tilhørighet", "Språklig variasjon og språkets rolle i samfunnet."),
    ],
}


def _balanced_durations(total_weeks: int, count: int) -> list[int]:
    count = max(1, min(count, total_weeks))
    base, remainder = divmod(total_weeks, count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


def _academic_weeks(school_year: str, count: int) -> list[str]:
    match = re.search(r"(20\d{2})", school_year)
    first_year = int(match.group(1)) if match else 2026
    weeks = [
        *(f"{first_year}-W{week:02d}" for week in range(34, 52) if week != 40),
        *(f"{first_year + 1}-W{week:02d}" for week in range(2, 33) if week not in {8, 13, 14}),
    ]
    return weeks[:count]


def _text(value: Any, *, limit: int = 3000) -> str:
    return str(value or "").strip()[:limit]


def _strings(value: Any, *, limit: int) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        clean = _text(item, limit=500)
        if clean and clean not in result:
            result.append(clean)
        if len(result) >= limit:
            break
    return result


def _fallback_periods(request: YearPlanGenerateRequest) -> list[dict[str, Any]]:
    key = request.subject.strip().lower()
    sequence = SUBJECT_SEQUENCES.get(key)
    if not sequence:
        sequence = [
            (f"Grunnlag og sentrale begreper {index + 1}", f"Del {index + 1} i en faglig progresjon for {request.subject}.")
            for index in range(request.number_of_periods)
        ]
    periods: list[dict[str, Any]] = []
    for index in range(request.number_of_periods):
        title, overview = sequence[index % len(sequence)]
        periods.append({
            "title": title if index < len(sequence) else f"{title} – fordypning",
            "theme": title,
            "overview": overview,
            "learning_goals": [
                f"forklare sentrale sammenhenger innen {title.lower()}",
                "bruke fagbegreper presist og begrunne egne faglige vurderinger",
            ],
            "competency_goals": request.competency_goals[index::request.number_of_periods][:3],
            "key_concepts": [],
            "suggested_activities": [
                "kort inngangsaktivitet og kartlegging av forkunnskaper",
                "fagtekst eller kildemateriale med elevoppgaver",
                "oppsummerende muntlig eller skriftlig aktivitet",
            ],
            "assessment": "Underveisvurdering gjennom elevsvar, samtale og en kort avsluttende oppgave.",
        })
    return periods


def _extract_json(text: str) -> dict[str, Any]:
    clean = text.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*```$", "", clean)
    start, end = clean.find("{"), clean.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Planner returned no JSON object")
    parsed = json.loads(clean[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Planner JSON must be an object")
    return parsed


def _ai_periods(request: YearPlanGenerateRequest) -> list[dict[str, Any]]:
    from google import genai
    from google.genai import types

    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GOOGLE_API_KEY is not configured")
    goals = "\n".join(f"- {goal}" for goal in request.competency_goals) or (
        "- Ingen kompetansemål er limt inn. Lag en faglig fornuftig skisse, "
        "men ikke påstå at den er en fullstendig offisiell læreplantolkning."
    )
    prompt = f"""
Du er et planleggerteam for norsk videregående skole. Lag et realistisk,
redigerbart forslag til årsplan. Returner bare gyldig JSON.

Fag: {request.subject}
Nivå: {request.level}
Skoleår: {request.school_year}
Undervisning: {request.lessons_per_week} timer per uke, {request.lesson_minutes} minutter per time
Undervisningsuker: {request.teaching_weeks}
Antall perioder: nøyaktig {request.number_of_periods}
Lokale hensyn: {request.constraints or "Ingen oppgitt"}

Kompetansemål fra læreren:
{goals}

Krav:
- Lag en tydelig faglig progresjon og realistisk arbeidsmengde.
- Fordel de oppgitte kompetansemålene på relevante perioder uten å omskrive dem.
- Skill mellom læringsmål og kompetansemål.
- Foreslå varierte aktiviteter og vurdering, men ikke produser selve læremidlene.
- Ikke finn opp offisielle målkoder eller påstå full læreplandekning når mål mangler.
- Hver periode skal kunne stå som bestilling til en læremiddelgenerator.

JSON-format:
{{
  "periods": [
    {{
      "title": "kort periodetittel",
      "theme": "presist tema",
      "overview": "2-4 setninger om innhold og progresjon",
      "learning_goals": ["2-4 konkrete mål"],
      "competency_goals": ["ordrette mål fra lærerens liste"],
      "key_concepts": ["4-8 sentrale begreper"],
      "suggested_activities": ["2-4 aktiviteter"],
      "assessment": "kort forslag til underveis- eller sluttvurdering"
    }}
  ]
}}
"""
    client = genai.Client(api_key=key)
    try:
        response = client.models.generate_content(
            model=os.getenv("GOOGLE_MODEL", "gemini-3.8-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.25,
            ),
        )
        payload = _extract_json(getattr(response, "text", "") or "")
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    periods = payload.get("periods")
    if not isinstance(periods, list) or len(periods) < 2:
        raise ValueError("Planner returned too few periods")
    return [item for item in periods if isinstance(item, dict)]


def build_year_plan(request: YearPlanGenerateRequest) -> YearPlanCreate:
    planning_source = "fallback"
    raw_periods: list[dict[str, Any]]
    if request.use_ai:
        try:
            raw_periods = _ai_periods(request)
            planning_source = "ai"
        except Exception as exc:
            logger.warning("Årsplan-AI feilet; bruker deterministisk reserveplan: %s", exc)
            raw_periods = _fallback_periods(request)
    else:
        raw_periods = _fallback_periods(request)

    target_count = request.number_of_periods
    if len(raw_periods) < target_count:
        raw_periods.extend(_fallback_periods(request)[len(raw_periods):target_count])
    raw_periods = raw_periods[:target_count]
    durations = _balanced_durations(request.teaching_weeks, len(raw_periods))
    weeks = _academic_weeks(request.school_year, request.teaching_weeks)

    periods: list[YearPlanPeriod] = []
    cursor = 0
    for index, (item, duration) in enumerate(zip(raw_periods, durations)):
        period_weeks = weeks[cursor:cursor + duration]
        cursor += duration
        title = _text(item.get("title") or item.get("theme") or f"Periode {index + 1}", limit=180)
        requested_goals = _strings(item.get("competency_goals"), limit=30)
        verified_goals = [goal for goal in request.competency_goals if goal in requested_goals]
        periods.append(YearPlanPeriod(
            order=index,
            title=title,
            theme=_text(item.get("theme") or title, limit=240),
            week_start=period_weeks[0] if period_weeks else "",
            week_end=period_weeks[-1] if period_weeks else "",
            duration_weeks=duration,
            lesson_count=duration * request.lessons_per_week,
            overview=_text(item.get("overview")),
            learning_goals=_strings(item.get("learning_goals"), limit=12),
            competency_goals=verified_goals,
            key_concepts=_strings(item.get("key_concepts"), limit=20),
            suggested_activities=_strings(item.get("suggested_activities"), limit=15),
            assessment=_text(item.get("assessment"), limit=1200),
        ))

    title = request.title.strip() or f"{request.subject} {request.level} · {request.school_year}"
    notes = (
        "Årsplanen er et redigerbart forslag. Kontroller lokale skoledager, ferier, "
        "eksamen og læreplandekning før planen tas i bruk."
    )
    return YearPlanCreate(
        title=title,
        subject=request.subject,
        level=request.level,
        school_year=request.school_year,
        lessons_per_week=request.lessons_per_week,
        lesson_minutes=request.lesson_minutes,
        teaching_weeks=request.teaching_weeks,
        competency_goals=request.competency_goals,
        periods=periods,
        notes=notes,
        planning_source=planning_source,
    )
