"""
MathBookAgents - CrewAI agents for the AI Editorial Team.
Streamlined to 3 agents: Pedagogue, Writer (math+illustrations), Editor.
Temperature lowered to 0.3 for mathematical accuracy.
"""

import os
from crewai import Agent, LLM
from src.curriculum import format_boundaries_for_prompt, get_grade_boundaries


# Language level configurations for simplified Norwegian
LANGUAGE_LEVELS = {
    "standard": {
        "name": "Standard norsk",
        "code": "C1-C2",
        "description": "Vanlig akademisk norsk",
        "instructions": "",
    },
    "b2": {
        "name": "Forenklet norsk (B2)",
        "code": "B2",
        "description": "For elever med norsk som andrespråk - øvre mellomnivå",
        "instructions": """
=== SPRÅKNIVÅ: B2 (Øvre mellomnivå) ===
Skriv for elever som lærer norsk:
- Korte setninger (15-20 ord maks), én idé per setning
- Vanlige, konkrete ord - unngå idiomer
- Forklar fagbegreper første gang de brukes
- Bruk samme ord for samme begrep konsekvent
- Enkle oppgavetekster med klar struktur
VIKTIG: Matematisk nivå er UENDRET - bare språket er enklere.
""",
    },
    "b1": {
        "name": "Enklere norsk (B1)",
        "code": "B1",
        "description": "For elever med norsk som andrespråk - nedre mellomnivå",
        "instructions": """
=== SPRÅKNIVÅ: B1 (Mellomnivå) ===
Skriv for elever som lærer norsk:
- Veldig korte setninger (10-15 ord maks)
- De 3000 vanligste norske ordene
- Forklar ALLE fagbegreper som om eleven hører det første gang
- Bruk konkrete eksempler med tall
- Del ALLTID komplekse oppgaver i steg: "Steg 1:", "Steg 2:"
- Legg til "Tips:" der det hjelper
VIKTIG: Matematisk nivå er UENDRET - bare språket er enklere.
""",
    },
}


def get_language_level_instructions(language_level: str) -> str:
    """Get language simplification instructions for the given level."""
    return LANGUAGE_LEVELS.get(language_level, {}).get("instructions", "")


class MathBookAgents:
    """
    3 specialized agents: Pedagogue, Writer, Editor.
    - Pedagogue: Plans content structure
    - Writer: Writes math + TikZ illustrations in one pass
    - Editor: Quality-checks and outputs clean body content (NO preamble)
    """

    def __init__(self, language_level: str = "standard"):
        model = os.getenv("PRIMARY_MODEL", "gemini-2.0-flash")
        api_key = os.getenv("GOOGLE_API_KEY")

        # Temperature 0.3 for mathematical accuracy (was 0.7)
        self.llm = LLM(
            model=f"gemini/{model}",
            api_key=api_key,
            temperature=0.3
        )

        self.language_level = language_level
        self.language_instructions = get_language_level_instructions(language_level)

    # ------------------------------------------------------------------
    # AGENT 1: Pedagogue
    # ------------------------------------------------------------------
    def pedagogue(self, grade: str = None) -> Agent:
        """Curriculum expert - plans content aligned with LK20."""
        grade_context = format_boundaries_for_prompt(grade) if grade else ""
        lang_block = self.language_instructions or ""

        backstory = (
            "Du er en ekspert på matematikkdidaktikk med dyp kunnskap om "
            "det norske læreplanverket LK20.\n\n"

            "=== NIVÅTILPASNING ===\n"
            "- ALDRI inkluder konsepter elevene ikke har lært ennå\n"
            "- ALDRI lag oppgaver som er for enkle (under nivå)\n"
            "- ALLTID sjekk at matematikken matcher trinnet\n\n"

            f"{grade_context}\n"
            f"{lang_block}\n"

            "VIKTIG: Alt innhold skal være på norsk (Bokmål)."
        )

        return Agent(
            role="Didaktikk- og læreplanspesialist (LK20)",
            goal=(
                f"Lag en strukturert pedagogisk plan for {grade or 'det valgte klassetrinnet'}. "
                "Sørg for at ALT er NØYAKTIG tilpasset dette trinnet."
            ),
            backstory=backstory,
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

    # ------------------------------------------------------------------
    # AGENT 2: Writer (merged mathematician + illustrator)
    # ------------------------------------------------------------------
    def writer(self, grade: str = None) -> Agent:
        """
        Combined mathematician and illustrator.
        Writes math content AND TikZ illustrations in one pass.
        No more [INSERT FIGURE] placeholders.
        """
        grade_context = ""
        difficulty_context = ""

        if grade:
            boundaries = get_grade_boundaries(grade)
            if boundaries:
                examples = boundaries.get("example_exercises", [])
                too_hard = boundaries.get("too_hard_examples", [])
                difficulty_defs = boundaries.get("difficulty_definitions", {})

                grade_context = f"\n=== SPESIFIKT FOR {grade.upper()} ===\n"
                grade_context += "PASSENDE OPPGAVETYPER:\n"
                for ex in examples[:5]:
                    grade_context += f"  ✓ {ex}\n"
                if too_hard:
                    grade_context += "FOR VANSKELIG - BRUK IKKE:\n"
                    for ex in too_hard[:4]:
                        grade_context += f"  ✗ {ex}\n"
                if difficulty_defs:
                    difficulty_context = f"\nVANSKELIGHETSGRADERING:\n"
                    for level, desc in difficulty_defs.items():
                        difficulty_context += f"  {level.capitalize()}: {desc}\n"

        lang_block = self.language_instructions or ""
        age_instructions = self._get_age_illustration_instructions(grade)

        return Agent(
            role="Matematiker, lærebokforfatter og illustratør",
            goal=(
                f"Skriv komplett LaTeX-innhold for {grade or 'det valgte klassetrinnet'} "
                "med matematikk, oppgaver OG TikZ-illustrasjoner direkte i teksten. "
                "IKKE bruk [INSERT FIGURE]-plassholdere - skriv ferdig TikZ-kode med en gang."
            ),
            backstory=(
                "Du er en profesjonell matematiker og lærebokforfatter som også er ekspert "
                "på TikZ og PGFPlots. Du skriver KOMPLETT innhold i én omgang: tekst, "
                "matematikk OG illustrasjoner.\n\n"

                "=== NIVÅTILPASNING ===\n"
                f"{grade_context}"
                f"{difficulty_context}\n"
                f"{lang_block}\n"

                "=== OBLIGATORISKE LaTeX-MILJØER ===\n\n"

                "DEFINISJONER (blå boks):\n"
                "\\begin{definisjon}\n"
                "En \\textbf{lineær funksjon} er ...\n"
                "\\end{definisjon}\n\n"

                "EKSEMPLER (grønn boks med EKTE tittel):\n"
                "\\begin{eksempel}[title=Finne stigningstall]\n"
                "...\n"
                "\\end{eksempel}\n"
                "FORBUDT: [title=title], [title=Eksempel]\n\n"

                "OPPGAVER (lilla boks):\n"
                "\\begin{taskbox}{Oppgave 1}\n"
                "...\n"
                "\\end{taskbox}\n\n"

                "TIPS (oransje boks): \\begin{merk}...\\end{merk}\n"
                "LØSNING (teal boks): \\begin{losning}...\\end{losning}\n\n"

                "Deloppgaver:\n"
                "\\begin{enumerate}[label=\\alph*)]\n"
                "\\item ...\n"
                "\\end{enumerate}\n\n"

                "=== TikZ OG GRAFER ===\n\n"

                "Skriv TikZ-kode DIREKTE - aldri [INSERT FIGURE].\n"
                f"{age_instructions}\n\n"

                "TILGJENGELIGE TikZ-BIBLIOTEKER (allerede lastet i preamble):\n"
                "arrows.meta, calc, patterns, positioning, shapes.geometric,\n"
                "decorations.pathreplacing\n"
                "IKKE bruk andre biblioteker - de er IKKE tilgjengelige.\n\n"

                "TILGJENGELIGE PAKKER: tikz, pgfplots (compat=1.18), "
                "float, booktabs, enumitem, multicol, tcolorbox, siunitx, mathtools, bm\n\n"

                "Tilgjengelige farger i preamble:\n"
                "mainBlue, lightBlue, mainGreen, lightGreen, mainOrange, lightOrange,\n"
                "mainPurple, lightPurple, mainTeal, lightTeal, mainGray, lightGray\n\n"

                "FIGUR-FORMAT (alltid):\n"
                "\\begin{figure}[H]\n"
                "\\centering\n"
                "\\begin{tikzpicture}\n"
                "...\n"
                "\\end{tikzpicture}\n"
                "\\caption{Norsk beskrivelse.}\n"
                "\\end{figure}\n\n"

                "FUNKSJONSGRAF:\n"
                "\\begin{figure}[H]\n"
                "\\centering\n"
                "\\begin{tikzpicture}\n"
                "\\begin{axis}[width=0.7\\textwidth, height=0.5\\textwidth,\n"
                "  xlabel={$x$}, ylabel={$y$}, grid=major, axis lines=middle]\n"
                "\\addplot[mainBlue, thick, domain=-4:4] {2*x+1};\n"
                "\\end{axis}\n"
                "\\end{tikzpicture}\n"
                "\\caption{Grafen til $f(x)=2x+1$.}\n"
                "\\end{figure}\n\n"

                "=== MATEMATIKK-FORMATERING ===\n"
                "- \\frac{}{} for brøker, ALDRI a/b i display math\n"
                "- \\cdot for multiplikasjon, ALDRI *\n"
                "- \\sqrt{} for kvadratrot\n"
                "- Tabeller: booktabs (\\toprule, \\midrule, \\bottomrule), INGEN |\n\n"

                "=== LØSNINGSFORSLAG ===\n"
                "Plasser på SLUTTEN:\n"
                "\\section*{Løsningsforslag}\n"
                "\\begin{multicols}{2}\n"
                "\\textbf{Oppgave 1}\\\\\n"
                "a) $x = 3$ ...\n"
                "\\end{multicols}\n\n"

                "FORBUDT:\n"
                "- Ren tekst 'Definisjon:', 'Eksempel:' uten boks\n"
                "- Markdown-syntaks\n"
                "- [INSERT FIGURE: ...] plassholdere\n"
                "- Vertikale linjer i tabeller\n\n"

                "VIKTIG: Alt innhold på norsk (Bokmål)."
            ),
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

    # ------------------------------------------------------------------
    # AGENT 3: Editor
    # ------------------------------------------------------------------
    def chief_editor(self) -> Agent:
        """
        Quality controller. Outputs ONLY body content - NO preamble.
        The preamble is added automatically by pdf_generator.
        """
        language_check = ""
        if self.language_level != "standard":
            level_name = LANGUAGE_LEVELS.get(self.language_level, {}).get("name", "Forenklet")
            language_check = f"""
   h) SPRÅKKONSISTENS ({level_name}):
      - Sjekk at språket er enkelt og klart gjennom hele dokumentet
      - Korte setninger, vanlige ord
      - Fagbegreper skal være forklart
"""

        return Agent(
            role="Ansvarlig redaktør og kvalitetskontrollør",
            goal=(
                "Kvalitetssikre og sett sammen innholdet til et rent LaTeX-dokument. "
                "OUTPUT BARE BODY-INNHOLD - INGEN \\documentclass eller preamble. "
                "Preamble legges til automatisk av systemet."
            ),
            backstory=(
                "Du er en redaktør med ekspertise på LaTeX. Din jobb er å levere "
                "rent, feilfritt body-innhold.\n\n"

                "=== KRITISK: INGEN PREAMBLE ===\n"
                "Du skal ALDRI inkludere:\n"
                "- \\documentclass\n"
                "- \\usepackage\n"
                "- \\begin{document} / \\end{document}\n"
                "- \\newtcolorbox eller andre miljødefinisjoner\n\n"
                "Disse legges til AUTOMATISK av systemet. Hvis du inkluderer dem,\n"
                "vil dokumentet FEILE.\n\n"

                "Start innholdet direkte med:\n"
                "\\title{Tittel}\n"
                "\\author{Generert av MateMaTeX AI}\n"
                "\\date{\\today}\n"
                "\\maketitle\n"
                "...resten av innholdet...\n\n"

                "=== KVALITETSKONTROLL ===\n\n"

                "a) DEFINISJONER: Ren tekst 'Definisjon:' → \\begin{definisjon}...\\end{definisjon}\n"
                "b) EKSEMPLER: Ren tekst 'Eksempel:' → \\begin{eksempel}[title=Beskrivende]...\\end{eksempel}\n"
                "c) FIGURER: \\begin{figure} → \\begin{figure}[H] + \\centering + \\caption{}\n"
                "d) OPPGAVER: Ren tekst oppgaver → \\begin{taskbox}{Oppgave N}...\\end{taskbox}\n"
                "e) MATEMATIKK: Sjekk \\frac{}{}, \\sqrt{}, \\cdot\n"
                "f) KLAMMER: Tell at alle { har matchende }\n"
                "g) MILJØER: Alle \\begin{} har matchende \\end{}\n"
                f"{language_check}\n"

                "=== FASIT-VALIDERING ===\n\n"
                "For HVER oppgave med fasit:\n"
                "1. Les oppgaven nøye\n"
                "2. Regn ut svaret selv steg for steg\n"
                "3. Sammenlign med fasit-svaret\n"
                "4. Hvis de ikke stemmer, KORRIGER fasiten\n"
                "5. Dobbeltsjekk spesielt: brøker, negative tall, potenser\n\n"

                "Fjern alle [INSERT FIGURE: ...] plassholdere som ikke ble erstattet.\n\n"

                "OUTPUT: Rent LaTeX body-innhold klart for kompilering.\n"
                "VIKTIG: Alt innhold på norsk (Bokmål)."
            ),
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )

    # ------------------------------------------------------------------
    # Backward-compatible aliases
    # ------------------------------------------------------------------
    def mathematician(self, grade: str = None) -> Agent:
        """Alias for writer() - backward compatibility."""
        return self.writer(grade=grade)

    def illustrator(self, grade: str = None) -> Agent:
        """Alias for writer() - backward compatibility."""
        return self.writer(grade=grade)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_age_illustration_instructions(self, grade: str) -> str:
        """Get age-appropriate illustration guidance."""
        if not grade:
            return ""

        g = grade.lower()

        if any(x in g for x in ["1.", "2.", "3.", "4.", "1-4"]):
            return (
                "ILLUSTRASJONER FOR 1.-4. TRINN:\n"
                "- Tellebrikker, tierrammer, kakediagram for brøker\n"
                "- Store, fargerike figurer. Ingen koordinatsystem med negative tall."
            )
        elif any(x in g for x in ["5.", "6.", "7.", "5-7"]):
            return (
                "ILLUSTRASJONER FOR 5.-7. TRINN:\n"
                "- Tallinje, enkelt koordinatsystem, geometriske figurer med mål\n"
                "- Søylediagram, sektordiagram."
            )
        elif any(x in g for x in ["8.", "9.", "10."]):
            return (
                "ILLUSTRASJONER FOR 8.-10. TRINN:\n"
                "- Koordinatsystem med 4 kvadranter, funksjonsgrafer\n"
                "- Pytagoras-figurer, boksplott, statistikk."
            )
        elif "vg" in g:
            return (
                "ILLUSTRASJONER FOR VG1-VG3:\n"
                "- Polynomgrafer, eksponential-/logaritmefunksjoner\n"
                "- Tangentlinjer, skraverte arealer, vektorer."
            )
        return ""
