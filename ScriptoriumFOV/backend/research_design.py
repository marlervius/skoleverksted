"""Research-based design rules for Norwegian learning sheets.

The rules come from the project's research report on Norwegian as a second
language for learners aged 16–19 (October 2026). Each rule names its source:

- Processability Theory for Scandinavian (Glahn et al., 2001): grammar is
  acquired in a fixed order, so each level trains one stage and never skips.
- Involvement Load Hypothesis (Hulstijn & Laufer, 2001; Yanagisawa & Webb,
  2021): words are kept when the task makes the learner retrieve them and use
  them in new sentences, not when the learner copies them from the text.
- Four Strands (Nation, 2007): about 95–98 % of the running words must be
  known, so new words are few and recycled.
- Teaching and Learning Cycle (Rothery; Gibbons) and the levels of feedback
  (Hattie & Timperley, 2007): model text, supported writing, then independent
  writing, with a self-check and an answer key that explains the rule.

Only Norwegian sheets use these rules. English sheets keep their own prompts.
"""

from __future__ import annotations

import random


def base_level(level: str) -> str:
    """``"A2.1"`` -> ``"A2"``; unknown levels fall back to A2."""
    base = str(level or "").split(".")[0].strip().upper()
    return base if base in LEVEL_DESIGN else "A2"


# ---------------------------------------------------------------------------
# Grammar progression (Processability Theory, stages 1–5)
# ---------------------------------------------------------------------------

_BESTEMT_FORM = {
    "type": "bestemt_form",
    "name": "Ubestemt og bestemt form",
    "instruction": "Skriv ordet i bestemt form: en buss → bussen, et rom → rommet",
    "format": "Substantiv fra teksten i ubestemt form entall, med pil og ___ for bestemt form",
    "example": '"en vakt → ___", "et kontor → ___"',
}
_SUBJEKT = {
    "type": "pronomen_subjekt",
    "name": "Setningen trenger et subjekt",
    "instruction": "Skriv inn hvem som gjør noe: jeg, du, han, hun, vi, de eller det",
    "format": "Setninger fra teksten der subjektet er tatt bort og byttet med ___",
    "example": '"___ begynner klokka fire.", "___ regner i dag."',
}
_NEKTING = {
    "type": "nekting_ikke",
    "name": "Nekting med ikke",
    "instruction": "Skriv setningen med ikke. Ikke står rett etter verbet.",
    "format": "Korte hovedsetninger fra teksten der eleven skal sette inn ikke",
    "example": '"Jeg jobber i dag. → Jeg ___ ___ i dag."',
}
_FLERTALL = {
    "type": "flertall",
    "name": "Flertall av substantiv",
    "instruction": "Skriv flertall: en buss → busser",
    "format": "Substantiv fra teksten i ubestemt form entall (en buss, et rom)",
    "example": '"en buss", "et rom"',
}
_PRESENS = {
    "type": "presens",
    "name": "Verb i presens",
    "instruction": "Skriv verbet i presens (nå): å jobbe → jobber",
    "format": "Setninger fra teksten med verbet i infinitiv i parentes",
    "example": '"Jeg (å jobbe) ___ i butikken."',
}
_ARTIKLER = {
    "type": "artikler",
    "name": "Artikler (en/ei/et)",
    "instruction": "Skriv riktig artikkel: en, ei eller et",
    "format": "Substantiv fra teksten med ___ foran",
    "example": '"___ vakt", "___ kontor"',
}
_TIDSBRUK = {
    "type": "tidsbruk_preteritum_perfektum",
    "name": "Preteritum eller perfektum",
    "instruction": (
        "Velg riktig verbform. Bruk preteritum når det er ferdig (i går, i fjor). "
        "Bruk perfektum når det varer til nå (har bodd, har jobbet)."
    ),
    "format": "Setninger fra teksten med tidsuttrykk og verbet i infinitiv i parentes",
    "example": '"I går (å få) ___ Sara lønnsslippen.", "Sara (å jobbe) ___ der i seks måneder."',
}
_ADJEKTIV_ATTRIBUTIV = {
    "type": "adjektivbøying",
    "name": "Adjektiv foran substantiv",
    "instruction": "Bøy adjektivet: en stor bil – et stort hus – store biler",
    "format": "Først flertall, deretter intetkjønn: adjektivet i parentes foran et substantiv fra teksten",
    "example": '"to (dyr) ___ jakker", "et (stor) ___ rom"',
}
_KAN_VIL = {
    # The type must not contain "verb": the PDF would draw a conjugation table.
    "type": "kan_vil_infinitiv",
    "name": "kan og vil + verb",
    "instruction": "Skriv verbet etter kan eller vil. Verbet har ingen -r: Jeg kan jobbe.",
    "format": "Korte setninger fra teksten med kan eller vil og verbet i parentes",
    "example": '"Jeg kan (jobber) ___ i dag.", "Hun vil (låner) ___ en uniform."',
}
_SKRIFT_BRO = {
    "type": "tegnsetting_stor_bokstav",
    "name": "Stor bokstav, mellomrom og punktum",
    "instruction": "Skriv setningen riktig: stor bokstav først, mellomrom mellom ordene og punktum til slutt.",
    "format": "Korte setninger fra teksten skrevet uten stor bokstav, uten mellomrom og uten punktum",
    "example": '"dubegynnerklokka16.00" → "Du begynner klokka 16.00."',
}
_FEILRETTING_L1 = {
    "type": "feilretting",
    "name": "Feilretting – typiske feil",
    "instruction": "Tre av disse fem setningene har en feil. Finn feilene og skriv setningene riktig.",
    "format": (
        "5 nummererte setninger om tekstens tema. Nøyaktig 3 har én typisk feil hver: manglende subjekt "
        "(«Liker jobben»), verbet ikke på plass 2 («I går Sara fikk lønn»), eller manglende bestemt form "
        "(«Jeg leste kontrakt i går»). 2 er riktige. Marker IKKE hvilke som har feil."
    ),
    "example": '"1. I dag jobber Ali på verkstedet." (riktig), "2. Nå han spiser lunsj." (feil: verbet på plass 2)',
}
_BINDEORD = {
    "type": "konjunksjoner",
    "name": "Bindeord",
    "instruction": "Fyll inn riktig bindeord: og, men, fordi, derfor, etterpå",
    "format": "Setninger fra teksten med ___ der bindeordet mangler",
    "example": '"Sara sjekket lønnsslippen, ___ hun fant en feil."',
}
_LEDDSETNING_IKKE = {
    "type": "kombiner_leddsetning",
    "name": "Leddsetning med ikke",
    "instruction": (
        "Lag én setning med ordet i parentes. I leddsetningen står ikke foran verbet: "
        "…fordi han ikke kommer."
    ),
    "format": "To korte hovedsetninger om tekstens tema og en subjunksjon (fordi, at, hvis, når, selv om) i parentes",
    "example": '"Mange elever rekker ikke leksene. De jobber sent. (fordi)"',
}
_V2_ETTER_LEDDSETNING = {
    "type": "ordstilling_leddsetning_forst",
    "name": "Leddsetning først",
    "instruction": "Begynn med leddsetningen. Husk: verbet i hovedsetningen kommer rett etter kommaet.",
    "format": "Setninger fra teksten som skal skrives om slik at leddsetningen (Når …, Hvis …) står først",
    "example": '"Vi rydder verkstedet når vakta er ferdig." → "Når vakta er ferdig, ___"',
}
_RELATIV = {
    "type": "relativsetninger",
    "name": "Relativsetninger (som)",
    "instruction": "Kombiner setningene ved å bruke som",
    "format": "To setninger som skal kombineres",
    "example": '"Kontrakten er lang. Kontrakten må signeres." → "Kontrakten som må signeres, er lang."',
}
_PASSIV = {
    "type": "passiv",
    "name": "Passiv form",
    "instruction": "Skriv setningene om til passiv form (-s eller bli + perfektum)",
    "format": "Aktive setninger fra teksten som skal omskrives",
    "example": '"Sjefen signerer kontrakten." → "Kontrakten ___."',
}
_SAMMENSATTE = {
    "type": "sammensatte_ord",
    "name": "Sammensatte ord",
    "instruction": "Del opp de sammensatte ordene og forklar betydningen",
    "format": "Sammensatte ord fra teksten",
    "example": '"arbeidsmiljø = arbeid + s + miljø"',
}

LEVEL_DESIGN: dict[str, dict] = {
    "PRE-A1": {
        "stage": "PT-trinn 1 med skriftbro: ord, faste fraser og setninger med subjekt først",
        "grammar_target": (
            "subjekt først i hver setning (Jeg, Du, Det regner), er og har, kan/vil + verb i infinitiv, "
            "og stor bokstav, mellomrom mellom ordene og punktum eller spørsmålstegn"
        ),
        "core_tasks": [_SUBJEKT, _SKRIFT_BRO],
        "pool": [_KAN_VIL, _ARTIKLER, _PRESENS],
        "syntax_task": (
            "Stokkede korte setninger (3-5 ord) i rekkefølgen subjekt–verb–resten. Eleven skriver dem med "
            "stor forbokstav, mellomrom og punktum. Ikke start med tidsuttrykk."
        ),
        "text_length": "40-80 ord",
        "genres": (
            "Bruk en praktisk teksttype med fast oppsett: vaktliste, timeplan, skjema med Navn:/Dag:/Tid:, "
            "SMS eller meldingstråd, prisliste i kantina eller et skilt. Ikke skriv en fortelling"
        ),
        "word_range": "6-8",
        "self_check": [
            "Står personen (Jeg, Du, Han, Hun, Vi) eller det først i hver setning?",
            "Begynner hver setning med stor bokstav og slutter med punktum eller spørsmålstegn?",
            "Har jeg mellomrom mellom alle ordene?",
        ],
        "writing_words": 3,
        "writing_length": "3 setninger eller et utfylt skjema",
        "challenge": "Skriv én setning til med og.",
        "sound_pairs": True,
        "comprehension_questions": 3,
    },
    "A1": {
        "stage": "PT-trinn 1–2: ord og bøying av ord",
        "grammar_target": (
            "subjekt i hver setning (Jeg, Du, Det regner), ubestemt og bestemt form entall "
            "(en buss – bussen), verb i presens og nekting med ikke i hovedsetninger"
        ),
        "core_tasks": [_BESTEMT_FORM, _SUBJEKT],
        "pool": [_NEKTING, _FLERTALL, _PRESENS, _ARTIKLER],
        "syntax_task": (
            "Stokkede setninger i fast rekkefølge subjekt–verb–resten, med stor forbokstav og punktum. "
            "Ikke start med tidsuttrykk."
        ),
        "text_length": "100-160 ord",
        "word_range": "8-10",
        "self_check": [
            "Har alle setningene mine en person eller et det først?",
            "Har jeg skrevet bestemt form når tingen er kjent (bussen, rommet)?",
            "Har hver setning stor forbokstav, mellomrom mellom ordene og punktum?",
        ],
        "writing_words": 3,
        "writing_length": "3–5 setninger",
        "challenge": "Skriv to setninger til med og eller men.",
        "sound_pairs": True,
    },
    "A2": {
        "stage": "PT-trinn 3–4: samsvar i frasen og verbet på plass 2",
        "grammar_target": (
            "verbet på plass 2 etter tidsuttrykk først i setningen (I går fikk Sara lønnsslippen), "
            "preteritum for avsluttet tid og perfektum for det som varer til nå, "
            "og adjektiv foran substantiv (store biler, et stort hus)"
        ),
        "core_tasks": [_TIDSBRUK],
        "pool": [_ADJEKTIV_ATTRIBUTIV, _FEILRETTING_L1, _BINDEORD, _FLERTALL],
        "syntax_task": (
            "Stokkede setninger som begynner med et tidsuttrykk eller stedsuttrykk (I går, Nå, På jobben). "
            "Eleven må sette verbet på plass 2 og subjektet etter verbet."
        ),
        "text_length": "180-280 ord",
        "word_range": "8-10",
        "self_check": [
            "Står verbet på plass 2 når setningen begynner med et tidsuttrykk?",
            "Har jeg brukt preteritum for det som er ferdig og perfektum for det som varer til nå?",
            "Har jeg brukt bindeord som fordi, men og derfor?",
        ],
        "writing_words": 4,
        "writing_length": "80–120 ord",
        "challenge": "Begynn minst tre setninger med et tidsuttrykk, og bruk fordi én gang.",
        "sound_pairs": True,
    },
    "B1": {
        "stage": "PT-trinn 5: leddsetninger og setningsgrenser",
        "grammar_target": (
            "leddsetninger med fordi, at, hvis, når og selv om der ikke står foran verbet "
            "(…fordi han ikke fikk meldingen), og verbet rett etter en leddsetning som står først "
            "(Når vakta er ferdig, rydder vi)"
        ),
        "core_tasks": [_LEDDSETNING_IKKE],
        "pool": [_V2_ETTER_LEDDSETNING, _RELATIV, _PASSIV, _FEILRETTING_L1, _SAMMENSATTE],
        "syntax_task": (
            "Stokkede setninger med en leddsetning (fordi, at, hvis, når) som inneholder ikke. "
            "Eleven må sette ikke foran verbet i leddsetningen."
        ),
        "text_length": "350-450 ord",
        "word_range": "8-10",
        "self_check": [
            "Står ikke foran verbet i leddsetningene mine (…fordi jeg ikke har tid)?",
            "Kommer verbet rett etter kommaet når jeg begynner med en leddsetning?",
            "Har teksten innledning, argumenter og en begrunnet avslutning?",
        ],
        "writing_words": 5,
        "writing_length": "150–250 ord",
        "challenge": "Ta med et motargument og svar på det med selv om.",
        "sound_pairs": False,
    },
    "B2": {
        "stage": "PT-trinn 5 og videre: kompleks syntaks og fagspråk",
        "grammar_target": (
            "leddsetninger med setningsadverbial foran verbet, passiv i sakprosa og indirekte tale"
        ),
        "core_tasks": [_LEDDSETNING_IKKE],
        "pool": [_PASSIV, _RELATIV, _SAMMENSATTE, _V2_ETTER_LEDDSETNING],
        "syntax_task": (
            "Stokkede setninger med foranstilt leddsetning og setningsadverbial (ikke, aldri, ofte)."
        ),
        "text_length": "400-500 ord",
        "word_range": "8-10",
        "self_check": [
            "Står setningsadverbialet (ikke, aldri, ofte) riktig i leddsetningene?",
            "Bruker jeg fagordene presist og forklarer dem der det trengs?",
            "Er argumentene mine bygd opp med tydelige bindeord (derfor, likevel, dessuten)?",
        ],
        "writing_words": 5,
        "writing_length": "250–350 ord",
        "challenge": "Sammenlign to synspunkter og vurder hvilket som er best begrunnet.",
        "sound_pairs": False,
    },
}


def design_for(level: str) -> dict:
    return LEVEL_DESIGN[base_level(level)]


def select_grammar_tasks(level: str, num_tasks: int = 3, rng: random.Random | None = None) -> list[dict]:
    """The level's core stage task(s) first, then varied tasks from the same stage.

    Every task belongs to the level's processability stage, so a sheet never
    trains a structure the learner cannot yet process.
    """
    design = design_for(level)
    chooser = rng or random
    core = list(design["core_tasks"])[:num_tasks]
    remaining = max(0, num_tasks - len(core))
    pool = list(design["pool"])
    extra = chooser.sample(pool, min(remaining, len(pool))) if remaining else []
    return core + extra


# ---------------------------------------------------------------------------
# Prompt blocks
# ---------------------------------------------------------------------------


def text_design_block(level: str) -> str:
    """Rules for the model text: coverage, natural binding and the stage target."""
    design = design_for(level)
    # Pre-A1 and A1 keep to main clauses, so only coordinating words are allowed.
    linking = (
        "og, men, så" if base_level(level) in ("PRE-A1", "A1")
        else "og, men, så, fordi, derfor, etterpå"
    )
    genre_rule = (
        f"            - Teksttype: {design['genres']}.\n" if design.get("genres") else
        "            - Bruk gjerne en tekstsjanger fra virkeligheten: melding, vaktliste, e-post, "
        "oppslag eller kort sakprosa.\n"
    )
    return (
        "\n            FORSKNINGSBASERT TEKSTDESIGN:\n"
        f"            - Grammatisk mål ({design['stage']}): la teksten naturlig inneholde flere eksempler på "
        f"{design['grammar_target']}. Ikke bruk strukturer fra høyere trinn.\n"
        "            - Ordforråd: minst 95 % av ordene skal være kjente på nivået. Nye ord ut over "
        "nøkkelordene skal unngås. Bruk hvert nøkkelord minst to ganger.\n"
        "            - Ikke hakk teksten opp i bare korte setninger uten sammenheng. Vis sammenhengen "
        f"med enkle bindeord ({linking}) der nivået tillater det.\n"
        "            - Velg en situasjon med voksen relevans for ungdom 16–19 år, for eksempel deltidsjobb, "
        "arbeidskontrakt, lønnsslipp, hybel, transport, helse, digital svindel eller praksis i verksted "
        "eller lab.\n"
        f"{genre_rule}"
        "            - Teksten skal være god å lese høyt. Læreren leser den høyt mens elevene følger med.\n"
    )


def worksheet_vocabulary_rules(level: str) -> str:
    # The term stays exactly as it is written in the text: the concept trainer
    # finds its example sentences by matching the term against the text.
    return "\n                - Velg ord eleven trenger for å skrive om temaet selv, ikke sjeldne ord"


def comprehension_section(letter: str, level: str) -> str:
    """Four questions that cannot be answered by copying a line from the text."""
    if design_for(level).get("comprehension_questions") == 3:
        # Pre-A1: the learner finds and combines facts in a form, list or message.
        return f"""{letter}) LESEFORSTÅELSE
                - Lag 3 korte spørsmål. Ingen av dem skal kunne besvares ved å kopiere en linje fra teksten
                - Spørsmål 1 og 2: flervalg med 3 svaralternativer (a, b, c), med andre ord enn teksten
                  (eksempel: teksten sier «Kl. 16.00», alternativet sier «klokka fire»). Marker riktig svar med *
                - Spørsmål 3: eleven må koble to opplysninger, for eksempel regne ut hvor mange timer
                  til sammen eller si hvorfor noen må gjøre noe. Gi en startsetning: «Han jobber ___ timer.»
                  Skriv «Svar med egne ord.» etter spørsmålet"""
    return f"""{letter}) LESEFORSTÅELSE
                - Lag 4 spørsmål. Ingen av dem skal kunne besvares ved å kopiere en setning fra teksten
                - Spørsmålene skal bruke andre ord enn teksten (synonymer eller et annet perspektiv).
                  Ikke gjenta tekstens setning i spørsmålet
                - Spørsmål 1 og 2: flervalg med 3 svaralternativer (a, b, c). Svaralternativene bruker
                  også andre ord enn teksten. Marker riktig svar med *
                - Spørsmål 3: eleven må koble informasjon fra to ulike avsnitt (eller fra tekst og tabell).
                  Skriv «Svar med egne ord.» etter spørsmålet
                - Spørsmål 4: eleven må trekke en slutning eller gi en egen vurdering, og begrunne den.
                  Skriv «Svar med egne ord.» etter spørsmålet"""


def writing_frame_extra(level: str) -> str:
    """Teaching and Learning Cycle: model, supported writing, self-check."""
    design = design_for(level)
    checklist = " / ".join(design["self_check"])
    return (
        "\n                - Bygg rammen som støttet skriving: setningsstartere og bindeord som eleven fyller ut"
        f"\n                - Avslutt med en linje «Sjekk før du leverer:» og disse tre punktene: {checklist}"
    )


def real_case_extra(level: str) -> str:
    """Independent writing in three tracks with an explicit target-word demand."""
    design = design_for(level)
    checklist = " / ".join(design["self_check"])
    return (
        f"\n                - Eleven skal bruke minst {design['writing_words']} av nøkkelordene og øktens "
        f"grammatiske mål: {design['grammar_target']}"
        f"\n                - Lengde: {design['writing_length']}"
        "\n                - Gi tre spor etter oppgaven, hvert på egen linje:"
        "\n                  Basis: [en kortere variant med setningsstartere]"
        "\n                  Standard: [oppgaven slik den står]"
        f"\n                  Utfordring: {design['challenge']}"
        f"\n                - Avslutt med en linje «Sjekk før du leverer:» og disse tre punktene: {checklist}"
    )


def teacher_key_rules(level: str) -> str:
    """Process-level feedback (Hattie & Timperley): explain the rule, not only the answer."""
    return (
        "\nForklar kort på prosessnivå hvorfor svaret er riktig, med regelen eleven skal bruke. "
        "Eksempel: «Her står tidsuttrykket I morgen først. Derfor står verbet starter på plass 2, før jeg.» "
        "For LESEFORSTÅELSE spørsmål 3 og 4: gi et eksempel på et godt svar og hva svaret må inneholde."
    )


def language_task_rules(level: str) -> str:
    """Extra vocabulary tasks with high involvement and the stage-specific syntax task."""
    design = design_for(level)
    rules = f"""
            FORSKNINGSBASERTE ORDOPPGAVER (høy involvering, ikke avskrift):
            - Lag alltid én vocabulary_task med type "setningsbygging": velg 4 nøkkelord fra teksten.
              Hvert item er «ord – ny situasjon», der situasjonen er en annen enn i teksten
              (eksempel: "kontrakt – praksisplass på et verksted"). Instruksjon: "Skriv én setning
              med ordet om situasjonen. Ikke kopier fra teksten."
            - Fyll-inn-oppgaver skal bruke nye setninger med tekstens ord, ikke tekstens egne setninger.
            - syntax_tasks: {design['syntax_task']}"""
    if design["sound_pairs"]:
        rules += """
            - Lag én vocabulary_task med type "lyd_og_skrift": 4-5 ordpar der lang og kort vokal eller
              vokalene y, ø og u skiller ordene (tak – takk, gul – gull, lønn – lån, by – bu). Det ene ordet
              i hvert par skal stå i teksten. Item-format: "tak – takk". Instruksjon: "Les ordparene høyt
              med læreren. Skriv en setning med det ordet som står i teksten." Dette er det eneste unntaket
              fra regelen om at alle ord må komme fra teksten."""
    return rules
