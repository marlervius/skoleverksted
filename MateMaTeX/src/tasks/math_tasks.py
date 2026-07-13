"""
MathTasks - CrewAI tasks for the AI Editorial Team.
Streamlined to 3 tasks: Plan → Write (with illustrations) → Edit & Validate.
Writer produces body content + TikZ inline. Editor validates math and removes preamble.
"""

from crewai import Task, Agent


class MathTasks:
    """
    3-step workflow:
      1. plan_content_task   — Pedagogue plans structure
      2. write_content_task  — Writer produces LaTeX body + TikZ (merged)
      3. edit_and_validate_task — Editor quality-checks, validates answers, strips preamble
    """

    # ------------------------------------------------------------------
    # TASK 1: Plan Content (Pedagogue)
    # ------------------------------------------------------------------
    def plan_content_task(
        self,
        agent: Agent,
        grade: str,
        topic: str,
        content_type: str,
        content_options: dict = None
    ) -> Task:
        """
        Plan the pedagogical structure.
        """
        if content_options is None:
            content_options = {}

        include_theory = content_options.get("include_theory", True)
        include_examples = content_options.get("include_examples", True)
        include_exercises = content_options.get("include_exercises", True)
        include_solutions = content_options.get("include_solutions", True)
        include_graphs = content_options.get("include_graphs", True)
        num_exercises = content_options.get("num_exercises", 10)
        difficulty = content_options.get("difficulty", "Middels")
        competency_goals = content_options.get("competency_goals", [])
        exercise_type_instructions = content_options.get("exercise_type_instructions", [])
        differentiation_mode = content_options.get("differentiation_mode", False)
        language_level = content_options.get("language_level", "standard")

        # Build content restrictions
        content_restrictions = []
        if not include_theory:
            content_restrictions.append("IKKE inkluder teori eller definisjoner")
        if not include_examples:
            content_restrictions.append("IKKE inkluder eksempler")
        if not include_exercises:
            content_restrictions.append("IKKE inkluder oppgaver")
        if not include_graphs:
            content_restrictions.append("IKKE inkluder grafer eller figurer")

        restrictions_text = ""
        if content_restrictions:
            restrictions_text = (
                "\n\n**VIKTIGE RESTRIKSJONER:**\n"
                + "\n".join(f"- {r}" for r in content_restrictions)
            )

        competency_text = ""
        if competency_goals:
            goals_list = "\n".join(f"- {goal}" for goal in competency_goals)
            competency_text = f"\n\n**LK20 KOMPETANSEMÅL:**\n{goals_list}"

        exercise_types_text = ""
        if exercise_type_instructions:
            exercise_types_text = (
                "\n\n**OPPGAVETYPER:**\n"
                + "\n".join(f"- {instr}" for instr in exercise_type_instructions)
            )

        differentiation_text = ""
        if differentiation_mode:
            differentiation_text = """

**DIFFERENSIERING:**
Lag TRE separate nivåer av oppgaver:
1. Nivå 1 (Lett) - Grunnleggende oppgaver for elever som trenger ekstra støtte
2. Nivå 2 (Middels) - Standard oppgaver for de fleste elever
3. Nivå 3 (Vanskelig) - Utfordrende oppgaver for elever som trenger ekstra utfordring
"""

        language_level_text = ""
        if language_level == "b2":
            language_level_text = """

**SPRÅKNIVÅ: B2 (Forenklet norsk)**
- Korte setninger (15-20 ord maks), én idé per setning
- Vanlige, konkrete ord - unngå idiomer
- Forklar fagbegreper første gang de brukes
- Bruk samme ord for samme begrep konsekvent
Matematisk nivå er UENDRET - bare språket er enklere.
"""
        elif language_level == "b1":
            language_level_text = """

**SPRÅKNIVÅ: B1 (Enklere norsk)**
- Veldig korte setninger (10-15 ord maks)
- De 3000 vanligste norske ordene
- Forklar ALLE fagbegreper som om eleven hører det første gang
- Del komplekse oppgaver i steg: "Steg 1:", "Steg 2:"
- Legg til "Tips:" der det hjelper
Matematisk nivå er UENDRET - bare språket er enklere.
"""

        # ---- Exercises-only mode ----
        exercises_only = include_exercises and not include_theory and not include_examples

        if exercises_only:
            return Task(
                description=f"""
**RENT OPPGAVEARK - INGEN TEORI ELLER EKSEMPLER**

**Klassetrinn:** {grade}
**Tema:** {topic}
**Type:** {content_type}
**Antall oppgaver:** {num_exercises}
**Vanskelighetsgrad:** {difficulty}
{competency_text}
{exercise_types_text}
{differentiation_text}
{language_level_text}

Planlegg KUN:
- Tittel
{"- Kompetansemål øverst" if competency_goals else ""}
- {num_exercises} oppgaver{"fordelt på 3 nivåer (lett/middels/vanskelig)" if differentiation_mode else " med stigende vanskelighetsgrad"}
{"- Løsningsforslag" if include_solutions else "- INGEN løsningsforslag"}

IKKE planlegg teori, definisjoner eller eksempler.
Alt på norsk (Bokmål).
""",
                expected_output=f"""
Enkel plan for rent oppgaveark:
- Tittel
{"- LK20 kompetansemål" if competency_goals else ""}
- {num_exercises} oppgaver (kort beskrivelse + vanskelighetsgrad)
{"- Tre nivåer: Lett, Middels, Vanskelig" if differentiation_mode else ""}
{"- Notater om løsningsforslag" if include_solutions else ""}
INGEN teori, definisjoner eller eksempler.
""",
                agent=agent
            )

        # ---- Full content mode ----
        return Task(
            description=f"""
Analyser og lag en detaljert pedagogisk plan:

**Klassetrinn:** {grade}
**Tema:** {topic}
**Type:** {content_type}
**Antall oppgaver:** {num_exercises}
**Vanskelighetsgrad:** {difficulty}
{restrictions_text}
{competency_text}
{exercise_types_text}
{differentiation_text}
{language_level_text}

1. Identifiser relevante kompetansemål fra LK20.
2. Del temaet i logiske delseksjoner (grunnleggende → avansert).
3. For hver delseksjon:
   - Læringsmål
   - Nøkkelbegreper
   {"- Foreslåtte eksempler" if include_examples else "- INGEN eksempler"}
   {"- Oppgaver (totalt " + str(num_exercises) + ")" if include_exercises else "- INGEN oppgaver"}
{"4. Illustrasjoner der det trengs." if include_graphs else "4. INGEN figurer."}
5. Tidsestimat.

Alt på norsk (Bokmål).
""",
            expected_output=f"""
Strukturert plan:
- Tittel
- LK20-kompetansemål
- Seksjon-for-seksjon med:
  * Læringsmål og begreper
  {"* Eksempler" if include_examples else ""}
  {"* Oppgaver (totalt " + str(num_exercises) + ")" if include_exercises else ""}
  {"* Illustrasjonsbehov" if include_graphs else ""}
- Tidsestimat
""",
            agent=agent
        )

    # ------------------------------------------------------------------
    # TASK 2: Write Content + Illustrations (Writer — merged)
    # ------------------------------------------------------------------
    def write_content_task(
        self,
        agent: Agent,
        plan_task: Task,
        content_options: dict = None
    ) -> Task:
        """
        Write LaTeX body content WITH inline TikZ illustrations.
        No more [INSERT FIGURE] placeholders — everything in one pass.

        CRITICAL: Output ONLY body content. NO \\documentclass, NO \\usepackage.
        """
        if content_options is None:
            content_options = {}

        include_theory = content_options.get("include_theory", True)
        include_examples = content_options.get("include_examples", True)
        include_exercises = content_options.get("include_exercises", True)
        include_solutions = content_options.get("include_solutions", True)
        include_graphs = content_options.get("include_graphs", True)
        num_exercises = content_options.get("num_exercises", 10)
        competency_goals = content_options.get("competency_goals", [])
        exercise_type_instructions = content_options.get("exercise_type_instructions", [])
        differentiation_mode = content_options.get("differentiation_mode", False)
        language_level = content_options.get("language_level", "standard")

        # Language instruction (consistent with agents)
        language_instruction = ""
        if language_level == "b2":
            language_instruction = (
                "\n**SPRÅKNIVÅ B2 (Forenklet norsk):**\n"
                "- Korte setninger (15-20 ord maks), én idé per setning\n"
                "- Vanlige, konkrete ord - unngå idiomer\n"
                "- Forklar fagbegreper første gang de brukes\n"
                "- Bruk samme ord for samme begrep konsekvent\n"
                "Matematisk nivå UENDRET.\n"
            )
        elif language_level == "b1":
            language_instruction = (
                "\n**SPRÅKNIVÅ B1 (Enklere norsk):**\n"
                "- Veldig korte setninger (10-15 ord maks)\n"
                "- De 3000 vanligste norske ordene\n"
                "- Forklar ALLE fagbegreper som om eleven hører det første gang\n"
                "- Del komplekse oppgaver i steg: 'Steg 1:', 'Steg 2:'\n"
                "- Legg til 'Tips:' der det hjelper\n"
                "Matematisk nivå UENDRET.\n"
            )

        # Competency goals
        competency_instruction = ""
        if competency_goals:
            goals_list = "\n".join(f"\\item {goal}" for goal in competency_goals)
            competency_instruction = f"""
Start dokumentet med:
\\section*{{Kompetansemål}}
\\begin{{itemize}}
{goals_list}
\\end{{itemize}}
"""

        # Exercise types
        exercise_types_instruction = ""
        if exercise_type_instructions:
            exercise_types_instruction = (
                "\n\nOPPGAVETYPER:\n"
                + "\n".join(f"- {instr}" for instr in exercise_type_instructions)
            )

        # ---- Exercises-only ----
        exercises_only = include_exercises and not include_theory and not include_examples

        if exercises_only:
            diff_instruction = ""
            if differentiation_mode:
                diff_instruction = f"""

DIFFERENSIERING - Organiser i TRE nivåer:
\\section*{{Nivå 1 - Lett}}
{num_exercises // 3} enkle oppgaver

\\section*{{Nivå 2 - Middels}}
{num_exercises // 3} moderate oppgaver

\\section*{{Nivå 3 - Vanskelig}}
{num_exercises - 2*(num_exercises // 3)} utfordrende oppgaver
"""

            solutions_instruction = ""
            if include_solutions:
                solutions_instruction = """
Legg FASIT på slutten:
\\section*{Løsningsforslag}
\\begin{multicols}{2}
\\textbf{Oppgave 1}\\\\
a) Svar ...
\\end{multicols}
"""
            else:
                solutions_instruction = "\nIKKE inkluder løsningsforslag."

            graphs_instruction = ""
            if include_graphs:
                graphs_instruction = (
                    "Der figur er nyttig, skriv FERDIG TikZ-kode direkte "
                    "(\\begin{figure}[H]...\\end{figure}). ALDRI [INSERT FIGURE]."
                )
            else:
                graphs_instruction = "IKKE inkluder figurer eller grafer."

            return Task(
                description=f"""
**RENT OPPGAVEARK - BARE OPPGAVER, INGEN PREAMBLE**

=== KRITISK: INGEN PREAMBLE ===
Du skal ALDRI skrive:
- \\documentclass
- \\usepackage
- \\begin{{document}} / \\end{{document}}
- \\newtcolorbox eller miljødefinisjoner

Start direkte med \\title{{...}} og innhold.
Preamble legges til AUTOMATISK av systemet.
{competency_instruction}
{exercise_types_instruction}
{diff_instruction}
{language_instruction}

SKRIV KUN:
1. \\title{{Tittel}} + \\author{{Generert av MateMaTeX AI}} + \\date{{\\today}} + \\maketitle
2. Gå DIREKTE til oppgavene
3. NØYAKTIG {num_exercises} oppgaver med \\begin{{taskbox}}{{Oppgave N}}...\\end{{taskbox}}
4. {graphs_instruction}
5. {solutions_instruction}

FORMATERING:
- KUN LaTeX-syntaks, ALDRI Markdown
- \\frac{{}}{{}} for brøker, \\cdot for multiplikasjon
- Alt på norsk (Bokmål)
""",
                expected_output=f"""
Rent LaTeX BODY-innhold (INGEN preamble) med:
- \\title, \\author, \\date, \\maketitle
{"- Kompetansemål" if competency_goals else ""}
- {num_exercises} oppgaver i taskbox-format
{"- Tre nivåer" if differentiation_mode else "- Stigende vanskelighetsgrad"}
{"- Løsningsforslag" if include_solutions else ""}
INGEN teori, definisjoner, eksempler.
INGEN \\documentclass eller \\usepackage.
""",
                agent=agent,
                context=[plan_task]
            )

        # ---- Full content mode ----
        task_parts = [
            "Basert på planen, skriv KOMPLETT matematikkinnhold i LaTeX.\n",
            "=== KRITISK: INGEN PREAMBLE ===",
            "ALDRI skriv \\documentclass, \\usepackage, \\begin{document}, \\end{document}.",
            "Start med \\title{...} og innhold. Preamble legges til automatisk.\n",
        ]

        if include_theory:
            task_parts.append("1. Skriv forklaringer med \\begin{definisjon}...\\end{definisjon}.")
        else:
            task_parts.append("1. INGEN teori eller \\begin{definisjon}.")

        if include_examples:
            task_parts.append(
                "2. Inkluder eksempler med \\begin{eksempel}[title=Beskrivende]...\\end{eksempel}."
            )
        else:
            task_parts.append("2. INGEN eksempler eller \\begin{eksempel}.")

        if include_exercises:
            task_parts.append(
                f"3. Lag {num_exercises} oppgaver med "
                "\\begin{taskbox}{Oppgave N}...\\end{taskbox}."
            )
        else:
            task_parts.append("3. INGEN oppgaver.")

        if include_graphs:
            task_parts.append(
                "4. Skriv TikZ/PGFPlots DIREKTE i teksten. "
                "ALDRI [INSERT FIGURE]. Bruk \\begin{figure}[H]...\\end{figure}."
            )
        else:
            task_parts.append("4. INGEN figurer.")

        if include_solutions and include_exercises:
            task_parts.append(
                "5. Legg fasit på SLUTTEN:\n"
                "   \\section*{Løsningsforslag}\n"
                "   \\begin{multicols}{2}\n"
                "   \\textbf{Oppgave 1}\\\\\n"
                "   a) Svar ...\n"
                "   \\end{multicols}"
            )
        else:
            task_parts.append("5. INGEN løsningsforslag.")

        task_parts.append(f"""
FORMATERING:
- KUN LaTeX, ALDRI Markdown
- \\frac{{}}{{}} for brøker, \\cdot for multiplikasjon
- booktabs (\\toprule, \\midrule, \\bottomrule) for tabeller
- Alt på norsk (Bokmål)
{language_instruction}
{exercise_types_instruction}""")

        # Expected output
        output_parts = ["Komplett LaTeX BODY-innhold (INGEN preamble):"]
        output_parts.append("- \\title, \\author, \\date, \\maketitle")
        if include_theory:
            output_parts.append("- Definisjoner i \\begin{definisjon}")
        if include_examples:
            output_parts.append("- Eksempler i \\begin{eksempel}")
        if include_exercises:
            output_parts.append(f"- {num_exercises} oppgaver i \\begin{{taskbox}}")
        if include_graphs:
            output_parts.append("- TikZ-illustrasjoner direkte i teksten")
        if include_solutions and include_exercises:
            output_parts.append("- Løsningsforslag")
        output_parts.append("\nINGEN \\documentclass, \\usepackage, \\begin{document}.")

        return Task(
            description="\n".join(task_parts),
            expected_output="\n".join(output_parts),
            agent=agent,
            context=[plan_task]
        )

    # ------------------------------------------------------------------
    # TASK 3: Edit & Validate (Editor — merged final assembly + QC)
    # ------------------------------------------------------------------
    def edit_and_validate_task(
        self,
        agent: Agent,
        content_task: Task,
        content_options: dict = None
    ) -> Task:
        """
        Quality-check, validate answers, strip any preamble.
        Outputs ONLY clean body content.
        """
        if content_options is None:
            content_options = {}

        include_theory = content_options.get("include_theory", True)
        include_examples = content_options.get("include_examples", True)
        include_exercises = content_options.get("include_exercises", True)
        include_solutions = content_options.get("include_solutions", True)

        exercises_only = include_exercises and not include_theory and not include_examples

        exercises_only_check = ""
        if exercises_only:
            exercises_only_check = """

=== INNHOLDSFILTER (RENT OPPGAVEARK) ===
- FJERN alle \\begin{definisjon}...\\end{definisjon}
- FJERN alle \\begin{eksempel}...\\end{eksempel}
- FJERN all teori og forklarende tekst som ikke er del av en oppgave
- Behold KUN: tittel, oppgaver (taskbox), og eventuelt løsningsforslag
- Fjern all introduksjonstekst og teoribeskrivelser
"""

        return Task(
            description=f"""
Kvalitetssikre og rens innholdet. Output BARE rent body-innhold.

=== KRITISK: FJERN ALL PREAMBLE ===
Hvis innholdet inneholder noe av dette, FJERN det:
- \\documentclass{{...}}
- \\usepackage{{...}}
- \\begin{{document}}
- \\end{{document}}
- \\newtcolorbox, \\definecolor, \\newtheorem definisjoner

Innholdet skal starte DIREKTE med:
\\title{{Tittel}}
\\author{{Generert av MateMaTeX AI}}
\\date{{\\today}}
\\maketitle
...resten av innholdet...

=== KVALITETSKONTROLL ===

a) MILJØER: Ren tekst → riktig LaTeX-miljø:
   - "Definisjon:" → \\begin{{definisjon}}...\\end{{definisjon}}
   - "Eksempel:" → \\begin{{eksempel}}[title=Beskrivende]...\\end{{eksempel}}
   - Oppgaver → \\begin{{taskbox}}{{Oppgave N}}...\\end{{taskbox}}

b) FIGURER: \\begin{{figure}} → \\begin{{figure}}[H] + \\centering + \\caption{{}}

c) MATEMATIKK: Sjekk \\frac{{}}{{}}, \\sqrt{{}}, \\cdot

d) KLAMMER: Alle {{ har matchende }}

e) MILJØ-BALANSE: Alle \\begin{{}} har matchende \\end{{}}

f) FJERN Markdown-rester (**, #, ```)
{exercises_only_check}

=== FASIT-VALIDERING ===
For HVER oppgave med fasit:
1. Les oppgaven nøye
2. Regn ut svaret selv, steg for steg
3. Sammenlign med fasit
4. Hvis feil: KORRIGER fasiten
5. Dobbeltsjekk spesielt: brøker, negative tall, potenser, prosentregning

=== FORBUDT I OUTPUT ===
- \\documentclass
- \\usepackage
- \\begin{{document}} / \\end{{document}}
- \\newtcolorbox / \\definecolor / \\newtheorem
- [INSERT FIGURE: ...] plassholdere
- Markdown-syntaks

OUTPUT: Rent LaTeX body-innhold klart for kompilering.
Alt på norsk (Bokmål).
""",
            expected_output=f"""
Rent, validert LaTeX BODY-innhold:
- \\title, \\author, \\date, \\maketitle
{"- KUN oppgaver og evt. løsningsforslag (INGEN teori/eksempler)" if exercises_only else "- Alt innhold med riktige LaTeX-miljøer"}
- Alle fasitsvar er matematisk verifisert
- Alle miljøer er balansert
- INGEN preamble (\\documentclass, \\usepackage osv.)

Klart for at systemet legger til preamble og kompilerer.
""",
            agent=agent,
            context=[content_task]
        )

    # ------------------------------------------------------------------
    # Backward-compatible aliases
    # ------------------------------------------------------------------
    def generate_graphics_task(
        self, agent: Agent, content_task: Task, content_options: dict = None
    ) -> Task:
        """Backward compat — graphics are now inline in write_content_task."""
        # Return a pass-through task that just cleans up
        return Task(
            description=(
                "Innholdet har allerede illustrasjoner innebygd. "
                "Sjekk at TikZ-koden er korrekt og fjern eventuelle "
                "[INSERT FIGURE: ...] plassholdere. "
                "Output innholdet uendret ellers."
            ),
            expected_output="LaTeX-innholdet med verifisert TikZ-kode.",
            agent=agent,
            context=[content_task]
        )

    def final_assembly_task(
        self, agent: Agent, graphics_task: Task, content_options: dict = None
    ) -> Task:
        """Backward compat — use edit_and_validate_task instead."""
        return self.edit_and_validate_task(agent, graphics_task, content_options)
