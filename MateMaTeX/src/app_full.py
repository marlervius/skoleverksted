"""
MateMaTeX - Matematikkverkstedet AI
Streamlined UI - Clean, focused, user-friendly.
"""

import os
import base64
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="MateMaTeX",
    page_icon="◇",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Inject styles
from src.ui import inject_styles
inject_styles()


# ============================================================================
# TEMPLATES
# ============================================================================
TEMPLATES = {
    "worksheet_basic": {
        "name": "Oppgaveark",
        "emoji": "📝",
        "description": "Kun oppgaver",
        "config": {
            "material_type": "arbeidsark",
            "include_theory": False, "include_examples": False,
            "include_exercises": True, "include_solutions": True,
            "include_graphs": True, "include_tips": False,
            "num_exercises": 10,
        }
    },
    "chapter_full": {
        "name": "Fullt kapittel",
        "emoji": "📖",
        "description": "Teori + oppgaver",
        "config": {
            "material_type": "kapittel",
            "include_theory": True, "include_examples": True,
            "include_exercises": True, "include_solutions": True,
            "include_graphs": True, "include_tips": True,
            "num_exercises": 8,
        }
    },
    "exam_prep": {
        "name": "Eksamen",
        "emoji": "📋",
        "description": "Eksamensoppgaver",
        "config": {
            "material_type": "prøve",
            "include_theory": False, "include_examples": False,
            "include_exercises": True, "include_solutions": True,
            "include_graphs": True, "include_tips": False,
            "num_exercises": 15,
        }
    },
    "differentiated": {
        "name": "Differensiert",
        "emoji": "📊",
        "description": "3 nivåer",
        "config": {
            "material_type": "arbeidsark",
            "include_theory": False, "include_examples": False,
            "include_exercises": True, "include_solutions": True,
            "include_graphs": True, "include_tips": False,
            "num_exercises": 12, "differentiation_mode": True,
        }
    },
}

# Difficulty mapping — robust, no string splitting
DIFFICULTY_OPTIONS = {
    "🟢 Lett": "Lett",
    "🟡 Middels": "Middels",
    "🔴 Vanskelig": "Vanskelig",
}
DIFFICULTY_REVERSE = {v: k for k, v in DIFFICULTY_OPTIONS.items()}


# ============================================================================
# SESSION STATE
# ============================================================================
def initialize_session_state():
    """Initialize session state with sensible defaults."""
    defaults = {
        "latex_result": None,
        "pdf_path": None,
        "pdf_bytes": None,
        "generation_complete": False,
        "generation_cancelled": False,
        "include_theory": True,
        "include_examples": True,
        "include_exercises": True,
        "include_solutions": True,
        "include_graphs": True,
        "include_tips": False,
        "difficulty_level": "Middels",
        "selected_exercise_types": ["standard"],
        "differentiation_mode": False,
        "num_exercises": 10,
        "selected_competency_goals": [],
        "selected_template": None,
        "language_level": "standard",
        "_generating": False,
        "_last_filename": "",
        "word_bytes": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_template(template_key: str):
    """Apply a template configuration."""
    if template_key in TEMPLATES:
        config = TEMPLATES[template_key]["config"]
        for key, value in config.items():
            st.session_state[key] = value
        st.session_state.selected_template = template_key


# ============================================================================
# CORE FUNCTIONS
# ============================================================================
def run_crew(grade: str, topic: str, material_type: str, instructions: str, content_options: dict) -> str:
    """
    Run the CrewAI editorial team to generate content.
    3 agents: Pedagogue → Writer → Editor (streamlined from 4).
    """
    from crewai import Crew, Process
    from src.agents import MathBookAgents
    from src.tasks import MathTasks

    language_level = content_options.get("language_level", "standard")
    agents = MathBookAgents(language_level=language_level)
    tasks = MathTasks()

    # 3 agents (writer handles both math content + illustrations)
    pedagogue = agents.pedagogue(grade=grade)
    writer = agents.writer(grade=grade)
    editor = agents.chief_editor()

    full_topic = f"{topic}\n\nTilleggsinstruksjoner: {instructions}" if instructions else topic

    # 3 tasks (no separate graphics task — writer produces TikZ inline)
    task1 = tasks.plan_content_task(pedagogue, grade, full_topic, material_type, content_options)
    task2 = tasks.write_content_task(writer, task1, content_options)
    task3 = tasks.edit_and_validate_task(editor, task2, content_options)

    crew = Crew(
        agents=[pedagogue, writer, editor],
        tasks=[task1, task2, task3],
        process=Process.sequential,
        verbose=True
    )

    result = crew.kickoff()
    return result.raw if hasattr(result, 'raw') else str(result)


def generate_pdf(latex_content: str, filename: str) -> str | None:
    """Generate PDF from LaTeX content."""
    from src.tools import compile_latex_to_pdf
    try:
        return compile_latex_to_pdf(latex_content, filename)
    except (FileNotFoundError, RuntimeError) as e:
        st.error(f"PDF-kompilering feilet: {e}")
        return None


def save_tex_file(latex_content: str, filename: str) -> str:
    """Save LaTeX content to .tex file.
    
    Ensures the saved file is a complete, self-contained LaTeX document
    that compiles in Overleaf/pdflatex by validating it has a preamble.
    """
    from src.tools import ensure_preamble
    from src.tools.pdf_generator import clean_ai_output
    
    # Ensure the .tex file is always complete and self-contained
    if r'\documentclass' not in latex_content:
        latex_content = ensure_preamble(clean_ai_output(latex_content))
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    tex_path = output_dir / f"{filename}.tex"
    tex_path.write_text(latex_content, encoding="utf-8")
    return str(tex_path)


def make_safe_filename(topic: str, grade: str) -> str:
    """Create a safe filename from topic and grade. Never returns empty."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')[:30]
    safe_grade = grade.replace(' ', '_').replace('.', '')
    if not safe_topic:
        safe_topic = "matematikk"
    return f"{safe_topic}_{safe_grade}_{timestamp}"


# ============================================================================
# MAIN APPLICATION
# ============================================================================
def main():
    """Main application - clean, linear flow."""
    initialize_session_state()

    api_configured = bool(os.getenv("GOOGLE_API_KEY"))
    model_name = os.getenv("PRIMARY_MODEL", "gemini-2.0-flash")

    # ------------------------------------------------------------------
    # HEADER
    # ------------------------------------------------------------------
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0 1rem 0;">
        <h1 style="
            font-size: 2.5rem; font-weight: 800; margin: 0;
            background: linear-gradient(135deg, #f8fafc 0%, #f59e0b 80%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            letter-spacing: -1px;
        ">◇ MateMaTeX</h1>
        <p style="color: #94a3b8; font-size: 0.95rem; margin-top: 0.5rem;">
            Generer matematikkoppgaver tilpasset norsk læreplan
        </p>
    </div>
    """, unsafe_allow_html=True)

    # API status - minimal
    if api_configured:
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 1.5rem;">
            <span style="
                background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.25);
                padding: 0.3rem 0.8rem; border-radius: 20px;
                color: #10b981; font-size: 0.75rem;
            ">● {model_name}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error("API-nøkkel mangler. Legg til GOOGLE_API_KEY i miljøvariablene.")
        return

    # ------------------------------------------------------------------
    # STEP 1: Quick-start templates
    # ------------------------------------------------------------------
    st.markdown("##### Hurtigstart")
    cols = st.columns(4)
    for i, (key, tmpl) in enumerate(TEMPLATES.items()):
        with cols[i]:
            is_selected = st.session_state.selected_template == key
            if st.button(
                f"{tmpl['emoji']} {tmpl['name']}",
                key=f"tmpl_{key}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                apply_template(key)
                st.rerun()

    st.markdown("---")

    # ------------------------------------------------------------------
    # STEP 2: Grade + Topic (the two most important choices)
    # ------------------------------------------------------------------
    from src.cache import get_curriculum_topics

    grade_options = {
        "1.-4. trinn": "1-4. trinn",
        "5.-7. trinn": "5-7. trinn",
        "8. trinn": "8. trinn",
        "9. trinn": "9. trinn",
        "10. trinn": "10. trinn",
        "VG1 1T": "VG1 1T",
        "VG1 1P": "VG1 1P",
        "VG2 2P": "VG2 2P",
        "VG2 R1": "VG2 R1",
        "VG3 R2": "VG3 R2",
    }

    col_grade, col_topic = st.columns([1, 2])

    with col_grade:
        st.markdown("##### Klassetrinn")
        selected_grade = st.selectbox(
            "Klassetrinn",
            options=list(grade_options.keys()),
            index=4,
            label_visibility="collapsed"
        )

    with col_topic:
        st.markdown("##### Tema")
        topics_by_category = get_curriculum_topics(selected_grade)
        topic_choices = ["✍️ Skriv eget tema..."]
        for _cat, topics_list in topics_by_category.items():
            topic_choices.extend(topics_list)

        selected_topic_choice = st.selectbox(
            "Velg tema",
            options=topic_choices,
            label_visibility="collapsed"
        )

    topic = ""
    if selected_topic_choice == "✍️ Skriv eget tema...":
        topic = st.text_input(
            "Skriv tema",
            placeholder="f.eks. Lineære funksjoner, Pytagoras, Brøk...",
            label_visibility="collapsed"
        )
        # C9: Show topic suggestions from curriculum
        try:
            from src.tools import get_topic_suggestions
            suggestions = get_topic_suggestions(grade=selected_grade, current_topic=topic, num_suggestions=4)
            if suggestions:
                st.caption("Forslag:")
                suggestion_cols = st.columns(len(suggestions))
                for i, sug in enumerate(suggestions):
                    with suggestion_cols[i]:
                        if st.button(sug.get("topic", ""), key=f"sug_{i}", use_container_width=True):
                            st.session_state._suggestion_topic = sug.get("topic", "")
                            st.rerun()
                # Apply suggestion if one was clicked
                if st.session_state.get("_suggestion_topic"):
                    topic = st.session_state._suggestion_topic
                    st.session_state._suggestion_topic = None
        except Exception:
            pass  # Topic suggestions are non-critical
    else:
        topic = selected_topic_choice

    # Store for exercise bank
    st.session_state._last_topic = topic
    st.session_state._last_grade = selected_grade

    # ------------------------------------------------------------------
    # STEP 3: Content toggles - simple row
    # ------------------------------------------------------------------
    st.markdown("---")
    st.markdown("##### Innhold")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.session_state.include_theory = st.checkbox("📘 Teori", value=st.session_state.include_theory)
    with c2:
        st.session_state.include_examples = st.checkbox("💡 Eksempler", value=st.session_state.include_examples)
    with c3:
        st.session_state.include_exercises = st.checkbox("✍️ Oppgaver", value=st.session_state.include_exercises)
    with c4:
        st.session_state.include_solutions = st.checkbox("🔑 Fasit", value=st.session_state.include_solutions)
    with c5:
        st.session_state.include_graphs = st.checkbox("📊 Grafer", value=st.session_state.include_graphs)
    with c6:
        st.session_state.include_tips = st.checkbox("💬 Tips", value=st.session_state.include_tips)

    # Exercise count + difficulty (only if exercises enabled)
    if st.session_state.include_exercises:
        col_count, col_diff = st.columns(2)
        with col_count:
            st.session_state.num_exercises = st.slider(
                "Antall oppgaver", min_value=3, max_value=25,
                value=st.session_state.num_exercises, step=1
            )
        with col_diff:
            difficulty_labels = list(DIFFICULTY_OPTIONS.keys())
            current_label = DIFFICULTY_REVERSE.get(st.session_state.difficulty_level, "🟡 Middels")
            diff_idx = difficulty_labels.index(current_label) if current_label in difficulty_labels else 1
            selected_difficulty = st.radio(
                "Vanskelighetsgrad",
                options=difficulty_labels,
                index=diff_idx,
                horizontal=True
            )
            st.session_state.difficulty_level = DIFFICULTY_OPTIONS[selected_difficulty]

    # ------------------------------------------------------------------
    # STEP 4: Advanced options (collapsed by default)
    # ------------------------------------------------------------------
    with st.expander("⚙️ Flere innstillinger", expanded=False):
        adv_col1, adv_col2 = st.columns(2)

        with adv_col1:
            # Differentiation
            st.session_state.differentiation_mode = st.checkbox(
                "📊 Generer 3 nivåer (differensiering)",
                value=st.session_state.differentiation_mode
            )

            # Language level
            lang_options = {"Standard norsk": "standard", "Forenklet (B2)": "b2", "Enklere (B1)": "b1"}
            current_lang = st.session_state.get("language_level", "standard")
            lang_idx = list(lang_options.values()).index(current_lang) if current_lang in lang_options.values() else 0
            selected_lang = st.selectbox(
                "Språknivå",
                options=list(lang_options.keys()),
                index=lang_idx,
                help="For elever med norsk som andrespråk"
            )
            st.session_state.language_level = lang_options[selected_lang]

        with adv_col2:
            # Exercise types
            if st.session_state.include_exercises:
                from src.cache import get_all_exercise_types
                exercise_types = get_all_exercise_types()
                selected_types = []
                for type_key, type_info in exercise_types.items():
                    if st.checkbox(
                        type_info["name"],
                        value=type_key in st.session_state.selected_exercise_types,
                        key=f"extype_{type_key}"
                    ):
                        selected_types.append(type_key)
                st.session_state.selected_exercise_types = selected_types if selected_types else ["standard"]

        # Competency goals
        from src.cache import get_curriculum_goals
        competency_goals = get_curriculum_goals(selected_grade)
        if competency_goals:
            st.markdown("**🎯 Kompetansemål (LK20)**")
            selected_goals = []
            for i, goal in enumerate(competency_goals):
                display = goal[:80] + "..." if len(goal) > 80 else goal
                if st.checkbox(display, key=f"goal_{i}", help=goal):
                    selected_goals.append(goal)
            st.session_state.selected_competency_goals = selected_goals

    # ------------------------------------------------------------------
    # GENERATE BUTTON
    # ------------------------------------------------------------------
    st.markdown("---")

    can_generate = api_configured and bool(topic)

    if not topic:
        st.info("Velg eller skriv inn et tema for å starte.")

    # C1: Show time estimate before generation
    if can_generate:
        from src.curriculum import estimate_generation_time
        _est_material = "arbeidsark"
        if st.session_state.selected_template and st.session_state.selected_template in TEMPLATES:
            _est_material = TEMPLATES[st.session_state.selected_template]["config"].get("material_type", "arbeidsark")
        est_min, est_max = estimate_generation_time(
            material_type=_est_material,
            num_exercises=st.session_state.num_exercises,
            include_theory=st.session_state.include_theory,
            include_examples=st.session_state.include_examples,
            include_graphs=st.session_state.include_graphs,
        )
        st.caption(f"Estimert tid: {est_min}–{est_max} min")

    # B3: Removed non-functional cancel button (run_crew is blocking)
    generate_clicked = st.button(
        "◇ Generer materiale",
        disabled=not can_generate,
        use_container_width=True,
        type="primary"
    )

    # ------------------------------------------------------------------
    # GENERATION LOGIC
    # ------------------------------------------------------------------
    if generate_clicked:
        st.session_state.latex_result = None
        st.session_state.pdf_path = None
        st.session_state.pdf_bytes = None
        st.session_state.generation_complete = False
        st.session_state.generation_cancelled = False
        st.session_state._generating = True
        st.session_state.word_bytes = None  # C3: Reset Word cache on new generation

        filename = make_safe_filename(topic, selected_grade)
        st.session_state._last_filename = filename  # C4: Store for download buttons

        # Build content options
        from src.cache import get_all_exercise_types
        exercise_types = get_all_exercise_types()
        exercise_type_instructions = [
            exercise_types[et]["instruction"]
            for et in st.session_state.selected_exercise_types
            if et in exercise_types
        ]

        # Get material type from selected template (fix: no unnecessary loop)
        if st.session_state.selected_template and st.session_state.selected_template in TEMPLATES:
            selected_material = TEMPLATES[st.session_state.selected_template]["config"].get("material_type", "arbeidsark")
        else:
            selected_material = "arbeidsark"

        content_options = {
            "include_theory": st.session_state.include_theory,
            "include_examples": st.session_state.include_examples,
            "include_exercises": st.session_state.include_exercises,
            "include_solutions": st.session_state.include_solutions,
            "include_graphs": st.session_state.include_graphs,
            "include_tips": st.session_state.include_tips,
            "num_exercises": st.session_state.num_exercises,
            "difficulty": st.session_state.difficulty_level,
            "material_type": selected_material,
            "competency_goals": st.session_state.selected_competency_goals,
            "exercise_types": st.session_state.selected_exercise_types,
            "exercise_type_instructions": exercise_type_instructions,
            "differentiation_mode": st.session_state.differentiation_mode,
            "language_level": st.session_state.language_level,
        }

        # Build instructions
        content_instructions = []
        if not st.session_state.include_theory:
            content_instructions.append("IKKE inkluder teori eller definisjoner")
        if not st.session_state.include_examples:
            content_instructions.append("IKKE inkluder eksempler")
        if st.session_state.include_exercises:
            content_instructions.append(f"Lag {st.session_state.num_exercises} oppgaver")
        if st.session_state.differentiation_mode:
            content_instructions.append("Lag tre nivåer: lett, middels, vanskelig")
        instructions = ". ".join(content_instructions)

        # C2: Better progress with status message
        progress_bar = st.progress(0, text="Starter generering...")
        status_msg = st.empty()

        try:
            progress_bar.progress(10, text="🎓 AI-teamet jobber...")
            status_msg.info("⏳ Pedagogen planlegger, matematikeren skriver, og redaktøren kvalitetssikrer. Dette tar vanligvis 1–3 minutter.")

            raw_result = run_crew(
                grade=grade_options[selected_grade],
                topic=topic,
                material_type=selected_material,
                instructions=instructions,
                content_options=content_options
            )

            status_msg.empty()
            progress_bar.progress(70, text="🔧 Bygger komplett LaTeX-dokument...")

            # Always produce a complete, self-contained .tex file
            # by cleaning AI output and wrapping with standard preamble.
            # This ensures the .tex file compiles in Overleaf/pdflatex.
            from src.tools import ensure_preamble
            from src.tools.pdf_generator import clean_ai_output
            latex_result = ensure_preamble(clean_ai_output(raw_result))
            st.session_state.latex_result = latex_result

            progress_bar.progress(80, text="📄 Lagrer filer...")

            tex_path = save_tex_file(latex_result, filename)
            # Pass already-processed content to PDF generator
            pdf_path = generate_pdf(latex_result, filename)
            if pdf_path:
                st.session_state.pdf_path = pdf_path
                with open(pdf_path, "rb") as f:
                    st.session_state.pdf_bytes = f.read()

            progress_bar.progress(100, text="✅ Ferdig!")

            # Record history and invalidate cache so it shows immediately
            try:
                from src.storage import add_to_history as save_to_storage
                from src.cache import invalidate_history_cache
                save_to_storage(
                    topic=topic, grade=selected_grade,
                    material_type=selected_material,
                    tex_content=latex_result, pdf_path=pdf_path
                )
                invalidate_history_cache()
            except Exception as e:
                logger.warning(f"Kunne ikke lagre til historikk: {e}")

            # Record usage
            try:
                from src.tools import record_generation
                record_generation(
                    topic=topic, grade=selected_grade,
                    material_type=selected_material,
                    num_exercises=st.session_state.num_exercises
                )
            except Exception as e:
                logger.warning(f"Kunne ikke registrere bruk: {e}")

            st.session_state.generation_complete = True
            st.session_state._generating = False
            st.rerun()

        except Exception as e:
            st.session_state._generating = False
            progress_bar.empty()
            status_msg.empty()
            logger.error(f"Generering feilet: {e}", exc_info=True)

            # C6: User-friendly error messages
            err_str = str(e).lower()
            if "api_key" in err_str or "authentication" in err_str or "401" in err_str:
                st.error("API-nøkkel mangler eller er ugyldig. Sjekk GOOGLE_API_KEY i .env-filen.")
            elif "quota" in err_str or "429" in err_str or "rate" in err_str:
                st.error("API-grensen er nådd. Vent litt og prøv igjen.")
            elif "pdflatex" in err_str or "tex" in err_str:
                st.error("LaTeX-kompilering feilet. Prøv å forenkle innholdet eller sjekk at pdflatex er installert.")
            elif "timeout" in err_str:
                st.error("Genereringen tok for lang tid. Prøv med færre oppgaver eller enklere innhold.")
            else:
                st.error(f"Noe gikk galt under generering. Prøv igjen.")
            with st.expander("Tekniske detaljer"):
                st.code(str(e))

    # ------------------------------------------------------------------
    # RESULTS
    # ------------------------------------------------------------------
    if st.session_state.generation_complete and st.session_state.latex_result:
        st.markdown("---")
        st.success("Materiale generert!")

        # C4: Use descriptive filenames
        dl_basename = st.session_state.get("_last_filename", f"matematikk_{datetime.now().strftime('%Y%m%d')}")

        # Download row
        dl_col1, dl_col2, dl_col3 = st.columns(3)

        with dl_col1:
            st.download_button(
                "📄 Last ned LaTeX",
                data=st.session_state.latex_result,
                file_name=f"{dl_basename}.tex",
                mime="text/plain",
                use_container_width=True
            )

        with dl_col2:
            if st.session_state.pdf_bytes:
                st.download_button(
                    "📕 Last ned PDF",
                    data=st.session_state.pdf_bytes,
                    file_name=f"{dl_basename}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.button("📕 PDF", disabled=True, use_container_width=True, help="Krever pdflatex")

        with dl_col3:
            # C3: Persist Word export in session state
            if st.session_state.get("word_bytes"):
                st.download_button(
                    "📘 Last ned Word",
                    data=st.session_state.word_bytes,
                    file_name=f"{dl_basename}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
            else:
                try:
                    from src.tools import is_word_export_available, latex_to_word
                    if is_word_export_available():
                        if st.button("📘 Word (.docx)", use_container_width=True):
                            with st.spinner("Konverterer til Word..."):
                                output_path = Path("output") / f"{dl_basename}.docx"
                                output_path.parent.mkdir(exist_ok=True)
                                word_path = latex_to_word(st.session_state.latex_result, str(output_path))
                                if word_path and Path(word_path).exists():
                                    with open(word_path, "rb") as f:
                                        st.session_state.word_bytes = f.read()
                                    st.rerun()
                                else:
                                    st.warning("Word-konvertering feilet.")
                    else:
                        st.button("📘 Word", disabled=True, use_container_width=True)
                except ImportError:
                    st.button("📘 Word", disabled=True, use_container_width=True)

        # C5: Better PDF preview with controls and fallback
        if st.session_state.pdf_bytes:
            pdf_b64 = base64.b64encode(st.session_state.pdf_bytes).decode('utf-8')
            st.markdown(f'''
            <div style="position: relative; margin-top: 1rem;">
                <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-bottom: 0.5rem;">
                    <a href="data:application/pdf;base64,{pdf_b64}" target="_blank"
                       style="color: #94a3b8; font-size: 0.8rem; text-decoration: none;">
                       Åpne i ny fane ↗
                    </a>
                </div>
                <iframe
                    src="data:application/pdf;base64,{pdf_b64}#toolbar=1&navpanes=0"
                    width="100%" height="700"
                    style="border: 1px solid #334155; border-radius: 12px;"
                ></iframe>
                <noscript>
                    <p style="color: #94a3b8; text-align: center; padding: 2rem;">
                        PDF-forhåndsvisning krever JavaScript. Last ned filen i stedet.
                    </p>
                </noscript>
            </div>
            ''', unsafe_allow_html=True)

        # LaTeX code viewer
        with st.expander("👁️ Se LaTeX-kode"):
            st.code(st.session_state.latex_result, language="latex")

        # Re-compile after edit
        with st.expander("✏️ Rediger og kompiler på nytt"):
            edited = st.text_area(
                "LaTeX", value=st.session_state.latex_result,
                height=300, label_visibility="collapsed"
            )
            if st.button("🔄 Kompiler på nytt", use_container_width=True):
                st.session_state.latex_result = edited
                with st.spinner("Kompilerer..."):
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    pdf_path = generate_pdf(edited, f"redigert_{ts}")
                    if pdf_path:
                        st.session_state.pdf_path = pdf_path
                        with open(pdf_path, "rb") as f:
                            st.session_state.pdf_bytes = f.read()
                        st.rerun()

        # ==============================================================
        # C9: Surface useful tools that were built but not in the UI
        # ==============================================================

        # --- Difficulty analysis ---
        with st.expander("📊 Vanskelighetsanalyse"):
            try:
                from src.tools import analyze_content
                analysis = analyze_content(st.session_state.latex_result)
                if analysis.total_exercises > 0:
                    ac1, ac2, ac3, ac4 = st.columns(4)
                    ac1.metric("🟢 Lett", analysis.easy_count)
                    ac2.metric("🟡 Middels", analysis.medium_count)
                    ac3.metric("🔴 Vanskelig", analysis.hard_count)
                    ac4.metric("⏱️ Est. tid", f"{analysis.estimated_time_minutes} min")
                    if analysis.recommendations:
                        for rec in analysis.recommendations:
                            st.caption(f"💡 {rec}")
                else:
                    st.caption("Ingen oppgaver funnet å analysere.")
            except Exception:
                st.caption("Analyse ikke tilgjengelig.")

        # --- Print-friendly version ---
        with st.expander("🖨️ Utskriftsvennlig versjon"):
            st.caption("Genererer en versjon med gråtoner, optimalisert for utskrift.")
            if st.button("Lag utskriftsversjon", use_container_width=True, key="btn_print"):
                try:
                    from src.tools import create_print_version
                    with st.spinner("Lager utskriftsversjon..."):
                        print_latex = create_print_version(st.session_state.latex_result)
                        print_pdf = generate_pdf(print_latex, f"print_{datetime.now().strftime('%H%M%S')}")
                        if print_pdf and Path(print_pdf).exists():
                            with open(print_pdf, "rb") as f:
                                st.download_button(
                                    "⬇️ Last ned utskriftsversjon",
                                    data=f.read(),
                                    file_name=f"{dl_basename}_utskrift.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                )
                        else:
                            st.warning("Kunne ikke generere utskriftsversjon.")
                except Exception as e:
                    st.warning(f"Feil: {e}")

        # --- Exercise bank ---
        with st.expander("🏦 Lagre til oppgavebank"):
            st.caption("Ekstraher enkeltoppgaver og lagre dem for gjenbruk.")
            if st.button("🔍 Finn og lagre oppgaver", use_container_width=True, key="btn_exbank"):
                try:
                    from src.tools import extract_exercises_from_latex, add_exercise
                    extracted = extract_exercises_from_latex(st.session_state.latex_result)
                    if extracted:
                        count = 0
                        for ex in extracted:
                            try:
                                add_exercise(
                                    title=ex.get("title", "Oppgave"),
                                    topic=st.session_state.get("_last_topic", "Matematikk") or "Matematikk",
                                    grade_level=st.session_state.get("_last_grade", "8. trinn") or "8. trinn",
                                    latex_content=ex.get("full_latex", ex.get("content", "")),
                                    difficulty=ex.get("difficulty", "middels"),
                                    solution=ex.get("solution"),
                                    source="generated",
                                )
                                count += 1
                            except Exception:
                                pass
                        from src.cache import invalidate_exercises_cache
                        invalidate_exercises_cache()
                        st.success(f"Lagret {count} oppgaver til oppgavebanken!")
                    else:
                        st.info("Fant ingen oppgaver å ekstrahere.")
                except Exception as e:
                    st.warning(f"Feil: {e}")

        # --- Rubric generator ---
        with st.expander("📋 Vurderingsrubrikk"):
            st.caption("Generer en vurderingsmatrise basert på innholdet.")
            if st.button("Lag rubrikk", use_container_width=True, key="btn_rubric"):
                try:
                    from src.tools import generate_rubric, rubric_to_markdown
                    rubric_topic = st.session_state.get("_last_topic", "Matematikk") or "Matematikk"
                    rubric_grade = st.session_state.get("_last_grade", "10. trinn") or "10. trinn"
                    rubric = generate_rubric(
                        topic=rubric_topic,
                        grade_level=rubric_grade,
                        num_exercises=st.session_state.num_exercises,
                    )
                    st.markdown(rubric_to_markdown(rubric))
                except Exception as e:
                    st.warning(f"Feil: {e}")

        # --- LK20 coverage ---
        with st.expander("🎯 LK20-dekning"):
            st.caption("Sjekk hvilke kompetansemål innholdet dekker.")
            try:
                from src.tools import analyze_coverage, format_coverage_report
                coverage_grade = st.session_state.get("_last_grade", "10. trinn") or "10. trinn"
                coverage = analyze_coverage(st.session_state.latex_result, coverage_grade)
                report = format_coverage_report(coverage)
                st.markdown(report)
            except Exception as e:
                st.caption("LK20-analyse ikke tilgjengelig.")

    # ------------------------------------------------------------------
    # HISTORY (show recent generations)
    # ------------------------------------------------------------------
    try:
        from src.cache import get_history
        history = get_history()
        if history:
            with st.expander(f"📚 Tidligere genereringer ({len(history)})", expanded=False):
                for entry in history[:10]:
                    entry_topic = entry.get("topic", "Ukjent")
                    entry_grade = entry.get("grade", "")
                    entry_type = entry.get("material_type", "")
                    entry_date = entry.get("created_at", entry.get("timestamp", ""))
                    if isinstance(entry_date, str) and len(entry_date) > 10:
                        entry_date = entry_date[:10]

                    col_info, col_action = st.columns([3, 1])
                    with col_info:
                        st.markdown(
                            f"**{entry_topic}** — {entry_grade} · {entry_type}  \n"
                            f"<small style='color:#64748b'>{entry_date}</small>",
                            unsafe_allow_html=True
                        )
                    with col_action:
                        entry_id = entry.get("id", "")
                        if entry_id:
                            from src.storage import get_tex_content
                            tex_content = get_tex_content(entry_id)
                            if tex_content:
                                # Ensure historical .tex files also have preamble
                                if r'\documentclass' not in tex_content:
                                    from src.tools import ensure_preamble
                                    from src.tools.pdf_generator import clean_ai_output
                                    tex_content = ensure_preamble(clean_ai_output(tex_content))
                                st.download_button(
                                    "⬇️ .tex",
                                    data=tex_content,
                                    file_name=f"{entry_topic[:20]}.tex",
                                    mime="text/plain",
                                    key=f"hist_{entry_id}",
                                    use_container_width=True,
                                )
                    st.markdown("<hr style='margin:0.3rem 0;border-color:#1e293b'>", unsafe_allow_html=True)
    except Exception:
        pass  # History display is non-critical

    # ------------------------------------------------------------------
    # FOOTER
    # ------------------------------------------------------------------
    st.markdown("""
    <div style="text-align: center; color: #64748b; font-size: 0.75rem; margin-top: 3rem; padding: 1rem 0;">
        MateMaTeX &copy; 2026 &bull; <a href="https://www.crewai.com/" target="_blank" style="color: #f59e0b; text-decoration: none;">CrewAI</a>
        + <a href="https://streamlit.io/" target="_blank" style="color: #f59e0b; text-decoration: none;">Streamlit</a>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
