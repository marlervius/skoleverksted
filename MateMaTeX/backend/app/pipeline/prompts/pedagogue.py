"""
Pedagogue agent prompt — Plans pedagogical content structure.

Contains:
- System prompt with role and rules
- Few-shot examples of perfect output
- Explicit negative list
"""

SYSTEM_PROMPT = """\
Du er en spesialist på matematikkdidaktikk og det norske læreplanverket LK20.

DIN OPPGAVE: Lag en strukturert pedagogisk plan for matematikkinnhold. Du planlegger BARE — du skriver IKKE LaTeX eller oppgaver.

REGLER:
1. ALLTID start med å identifisere relevante LK20-kompetansemål
2. Del temaet i logiske delseksjoner (fra grunnleggende til avansert)
3. For hver seksjon: spesifiser læringsmål, nøkkelbegreper, og illustrasjonsbehov
4. ALDRI inkluder konsepter over elevens trinn
5. ALDRI lag oppgaver som er under trinnets nivå
6. Vurder differensiering (lett/middels/vanskelig)
7. Estimer tidsbruk for hver seksjon
8. Marker hvor illustrasjoner (TikZ/PGFPlots) er NØDVENDIGE vs. valgfrie
9. PEDAGOGISK KONSISTENS: Alle regneregler og metoder som brukes i oppgaver MÅ være
   forklart i teoridelen. Hvis du planlegger en oppgave om f.eks. produktregelen,
   kjerneregelen, integrasjon ved substitusjon, osv., MÅ disse reglene stå i teorien
   FØRST. Aldri inkluder oppgaver som forutsetter regler som ikke er presentert.

ALDRI:
- Skriv LaTeX-kode
- Lag oppgavetekster (det gjør forfatteren)
- Gjenta informasjon fra LK20 uten å knytte det til det spesifikke temaet
- Planlegg innhold som krever kunnskaper elevene ikke har ennå
- Inkluder oppgaver om regler (produktregel, kjerneregel, etc.) uten å planlegge
  tilhørende teori/definisjon i samme dokument

OUTPUT-FORMAT: Strukturert plan i ren tekst med tydelige seksjoner.
"""

# Few-shot examples of PERFECT pedagogue output
FEW_SHOT_EXAMPLES = [
    {
        "input": "Klassetrinn: 8. trinn | Tema: Lineære funksjoner | Type: kapittel | 8 oppgaver",
        "output": """\
# Pedagogisk plan: Lineære funksjoner (8. trinn)

## LK20-kompetansemål
- «utforske og beskrive samanhengar mellom ulike representasjonar, som tekst, tabellar, grafar og formlar»
- «bruke variablar og formlar til å uttrykkje samanhengar»

## Forutsetninger elevene har
- Kan plotte punkt i koordinatsystem (fra 7. trinn)
- Kjenner til variable og enkle uttrykk
- Kan lese av tabeller og enkle diagrammer

## Seksjon 1: Hva er en funksjon? (10 min)
**Læringsmål:** Forstå at en funksjon kobler én x-verdi til nøyaktig én y-verdi.
**Nøkkelbegreper:** funksjon, variabel, x-verdi, y-verdi, funksjonsverdi
**Illustrasjon (NØDVENDIG):** Maskinmodell — input → funksjon → output

## Seksjon 2: Lineære funksjoner: f(x) = ax + b (15 min)
**Læringsmål:** Kjenne igjen og skrive opp en lineær funksjon.
**Nøkkelbegreper:** stigningstall (a), konstantledd (b), lineær
**Illustrasjon (NØDVENDIG):** Graf av f(x)=2x+1 i koordinatsystem med tydelige a og b

## Seksjon 3: Stigningstall og konstantledd (15 min)
**Læringsmål:** Finne a og b fra graf, tabell og to punkter.
**Nøkkelbegreper:** stigning, Δy/Δx, skjæringspunkt med y-aksen
**Illustrasjon (NØDVENDIG):** To grafer med ulikt stigningstall side om side

## Oppgaver (8 stk, stigende vanskelighet)
1–2: Lett — Les av a og b fra graf
3–4: Middels — Finn funksjonsuttrykk fra tabell
5–6: Middels — Tegn graf fra funksjonsuttrykk
7: Vanskelig — Finn funksjonsuttrykk gitt to punkter
8: Vanskelig — Tekstoppgave (mobilabonnement)

## Tidsestimat totalt: 60-75 min
""",
    },
    {
        "input": "Klassetrinn: 5.-7. trinn | Tema: Brøk | Type: arbeidsark | 10 oppgaver",
        "output": """\
# Pedagogisk plan: Brøk (5.-7. trinn, arbeidsark)

## LK20-kompetansemål
- «utforske og beskrive brøk som del av ein heilskap og del av eit tal»
- «samanlikne brøkar og utføre rekning med brøkar»

## Forutsetninger
- Kjenner til deling og multiplikasjon
- Har sett brøkbegrepet visuelt (kakediagram, brøkstaver)

## Seksjon: Oppgaveark — Brøk
Ingen teori (arbeidsark). Gå rett på oppgaver.

## Oppgaver (10 stk)
1–3: Lett — Visuell brøk (skraver deler av figur, fargelegging)
4–5: Lett — Skriv brøk fra bilde
6–7: Middels — Utvid og forkort brøker
8–9: Middels — Addisjon av brøker med lik nevner
10: Vanskelig — Addisjon med ulik nevner (enkel)

## Illustrasjonsbehov
- Oppgave 1-3: TikZ kakediagram/rektangler med skraverte deler (NØDVENDIG)
- Oppgave 4-5: Visuell brøkrepresentasjon (NØDVENDIG)
- INGEN koordinatsystem eller grafer (ikke relevant for dette trinnet)

## Tidsestimat: 30-40 min
""",
    },
    {
        "input": "Klassetrinn: VG1 1T | Tema: Funksjoner | Type: kapittel | 10 oppgaver",
        "output": """\
# Pedagogisk plan: Funksjoner (VG1 1T, kapittel)

## LK20-kompetansemål
- «utforske, analysere og tegne ulike typer funksjoner»
- Kobling mellom tabell, graf og formel

## VIKTIG: Kun funksjoner — IKKE vektorer, trigonometri eller kombinatorikk i dette kapittelet.

## Seksjon 1: Funksjonsbegrepet og representasjoner (15 min)
**Læringsmål:** Forstå funksjon, definisjonsmengde og verdimengde; koble tabell, graf og formel.
**Nøkkelbegreper:** funksjon, definisjonsmengde, verdimengde, koordinatsystem
**Illustrasjon (NØDVENDIG):** Samme lineære funksjon som tabell, graf og formel side om side
**Eksempler:** 2 — les av graf; lag tabell fra f(x)=2x-1
**Utforsk:** Endre stigningstall i GeoGebra — hva skjer med grafen?

## Seksjon 2: Lineære funksjoner (15 min)
**Læringsmål:** Finne stigningstall og konstantledd; tegne graf.
**Eksempler:** 2 — fra to punkter; praktisk modell (mobilabonnement)
**Illustrasjon (NØDVENDIG):** To lineære grafer med ulikt a og b

## Seksjon 3: Andregradsfunksjoner (20 min)
**Læringsmål:** Nullpunkter, toppunkt, symmetri.
**Eksempler:** 2 — faktorisering; abc-formel
**Illustrasjon (NØDVENDIG):** Parabel med toppunkt markert

## Seksjon 4: Polynomfunksjoner (15 min)
**Læringsmål:** Grad, nullpunkter, grov grafisk skisse.
**Eksempler:** 2 — tredjegrads med ett nullpunkt; sammenligne grafer

## Seksjon 5: Rasjonale funksjoner (15 min)
**Læringsmål:** Vertikale og horisontale asymptoter.
**Eksempler:** 2 — tegn graf med hull; finn asymptoter
**Vanlig feil:** Tro at horisontal asymptote aldri kan krysses

## Seksjon 6: Eksponentialfunksjoner og logaritmer (20 min)
**Læringsmål:** Vekst/forfall; logaritmeregler; løse b^x=c.
**Eksempler:** 2 — prosentvekst modell; lg-likning
**Illustrasjon (NØDVENDIG):** Eksponentialkurve

## Oppsummering
Tabell med alle funksjonstyper og metoder.

## Oppgaver (10 stk, stigende vanskelighet, KUN funksjoner)
1–2: Lett — les av lineær graf
3–4: Middels — andregrads nullpunkter
5–6: Middels — asymptoter / eksponentiallikning
7–8: Middels — modellering
9–10: Vanskelig — sammensatte funksjonsproblemer

## Tidsestimat totalt: 90-120 min
""",
    },
]


def build_pedagogue_prompt(
    grade: str,
    topic: str,
    material_type: str,
    num_exercises: int,
    grade_context: str,
    language_instructions: str,
    content_options: dict,
) -> str:
    """Build the user prompt for the pedagogue agent."""
    restrictions = []
    if not content_options.get("include_theory", True):
        restrictions.append("IKKE inkluder teori eller definisjoner")
    if not content_options.get("include_examples", True):
        restrictions.append("IKKE inkluder eksempler")
    if not content_options.get("include_graphs", True):
        restrictions.append("IKKE inkluder figurer eller grafer")

    restrictions_text = ""
    if restrictions:
        restrictions_text = "RESTRIKSJONER:\n" + "\n".join(f"- {r}" for r in restrictions)

    goals = content_options.get("competency_goals", [])
    goals_text = ""
    if goals:
        goals_text = "KOMPETANSEMÅL:\n" + "\n".join(f"- {g}" for g in goals)

    from app.pipeline.material_hints import pedagogue_material_instructions

    material_extra = pedagogue_material_instructions(material_type)

    diff_text = ""
    if material_type == "differensiert" or content_options.get("differentiation_mode"):
        diff_text = "DIFFERENSIERING: Planlegg tre nivåer (Grunnleggende / Standard / Avansert) i samme dokument"

    from app.curriculum.topic_coverage import format_coverage_for_prompt

    coverage_text = format_coverage_for_prompt(
        grade,
        topic,
        material_type=material_type,
        num_exercises=num_exercises,
        competency_goals=goals,
    )

    return f"""\
Lag en pedagogisk plan for:

Klassetrinn: {grade}
Tema: {topic}
Type: {material_type}
Antall oppgaver: {num_exercises}
Vanskelighetsgrad: {content_options.get('difficulty', 'Middels')}

{grade_context}

{restrictions_text}
{goals_text}
{diff_text}
{material_extra}
{coverage_text}
{language_instructions}

Følg formatet fra eksemplene. Alt på norsk (Bokmål).
"""
