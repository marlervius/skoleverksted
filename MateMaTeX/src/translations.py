"""
Internationalization (i18n) for MateMaTeX.
Supports Norwegian (Bokmål) and English.
"""

from typing import Dict, Any

# Language codes
NORWEGIAN = "no"
ENGLISH = "en"

# Available languages
LANGUAGES = {
    NORWEGIAN: "Norsk (Bokmål)",
    ENGLISH: "English",
}

# Translation dictionaries
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # ========================================
    # UI Labels
    # ========================================
    "app_title": {
        "no": "MateMaTeX",
        "en": "MateMaTeX",
    },
    "app_subtitle": {
        "no": "Generer profesjonelle matematikkoppgaver, arbeidsark og kapitler tilpasset norsk læreplan (LK20)",
        "en": "Generate professional math exercises, worksheets, and chapters aligned with curriculum standards",
    },
    "powered_by": {
        "no": "Drevet av Gemini AI",
        "en": "Powered by Gemini AI",
    },
    
    # Sidebar
    "sidebar_title": {
        "no": "MateMaTeX",
        "en": "MateMaTeX",
    },
    "sidebar_subtitle": {
        "no": "AI-drevet oppgavegenerator",
        "en": "AI-powered exercise generator",
    },
    "connected": {
        "no": "Tilkoblet",
        "en": "Connected",
    },
    "not_configured": {
        "no": "Ikke konfigurert",
        "en": "Not configured",
    },
    "add_api_key": {
        "no": "Legg til GOOGLE_API_KEY i .env",
        "en": "Add GOOGLE_API_KEY to .env",
    },
    "history": {
        "no": "Historikk",
        "en": "History",
    },
    "no_history": {
        "no": "Ingen genererte dokumenter ennå",
        "en": "No generated documents yet",
    },
    "links": {
        "no": "Lenker",
        "en": "Links",
    },
    "curriculum_link": {
        "no": "LK20 Læreplan",
        "en": "Curriculum Guide",
    },
    "settings": {
        "no": "Innstillinger",
        "en": "Settings",
    },
    "language": {
        "no": "Språk",
        "en": "Language",
    },
    
    # Templates
    "quick_start": {
        "no": "Hurtigstart med mal",
        "en": "Quick start with template",
    },
    "template_worksheet": {
        "no": "Oppgaveark",
        "en": "Worksheet",
    },
    "template_worksheet_desc": {
        "no": "Kun oppgaver, ingen teori",
        "en": "Exercises only, no theory",
    },
    "template_chapter": {
        "no": "Fullt kapittel",
        "en": "Full chapter",
    },
    "template_chapter_desc": {
        "no": "Teori, eksempler og oppgaver",
        "en": "Theory, examples, and exercises",
    },
    "template_exam": {
        "no": "Eksamenstrening",
        "en": "Exam practice",
    },
    "template_exam_desc": {
        "no": "Varierte eksamensoppgaver",
        "en": "Varied exam exercises",
    },
    "template_theory": {
        "no": "Teorihefte",
        "en": "Theory booklet",
    },
    "template_theory_desc": {
        "no": "Kun teori og eksempler",
        "en": "Theory and examples only",
    },
    "template_homework": {
        "no": "Lekseark",
        "en": "Homework sheet",
    },
    "template_homework_desc": {
        "no": "Enkle repetisjonsoppgaver",
        "en": "Simple review exercises",
    },
    "template_differentiated": {
        "no": "Differensiert",
        "en": "Differentiated",
    },
    "template_differentiated_desc": {
        "no": "3 nivåer: lett/middels/vanskelig",
        "en": "3 levels: easy/medium/hard",
    },
    
    # Configuration
    "select_grade_topic": {
        "no": "Velg klassetrinn og tema",
        "en": "Select grade and topic",
    },
    "based_on_curriculum": {
        "no": "Basert på LK20 læreplan",
        "en": "Based on curriculum standards",
    },
    "grade": {
        "no": "Klassetrinn",
        "en": "Grade level",
    },
    "topic": {
        "no": "Tema",
        "en": "Topic",
    },
    "select_topic": {
        "no": "Velg tema",
        "en": "Select topic",
    },
    "custom_topic": {
        "no": "Skriv eget tema...",
        "en": "Write custom topic...",
    },
    "custom_topic_placeholder": {
        "no": "f.eks. Lineære funksjoner, Pytagoras, Brøk...",
        "en": "e.g. Linear functions, Pythagorean theorem, Fractions...",
    },
    "material_type": {
        "no": "Materialtype",
        "en": "Material type",
    },
    "what_to_generate": {
        "no": "Hva skal genereres?",
        "en": "What to generate?",
    },
    "chapter": {
        "no": "Kapittel / Lærestoff",
        "en": "Chapter / Study material",
    },
    "worksheet": {
        "no": "Arbeidsark",
        "en": "Worksheet",
    },
    "exam": {
        "no": "Prøve / Eksamen",
        "en": "Test / Exam",
    },
    "homework": {
        "no": "Lekseark",
        "en": "Homework sheet",
    },
    
    # Content options
    "content": {
        "no": "Innhold",
        "en": "Content",
    },
    "customize_content": {
        "no": "Tilpass hva som inkluderes",
        "en": "Customize what is included",
    },
    "include_theory": {
        "no": "Teori og definisjoner",
        "en": "Theory and definitions",
    },
    "include_examples": {
        "no": "Eksempler",
        "en": "Examples",
    },
    "include_exercises": {
        "no": "Oppgaver",
        "en": "Exercises",
    },
    "include_solutions": {
        "no": "Fasit",
        "en": "Answer key",
    },
    "include_graphs": {
        "no": "Grafer/Figurer",
        "en": "Graphs/Figures",
    },
    "include_tips": {
        "no": "Tips og hint",
        "en": "Tips and hints",
    },
    
    # Exercise settings
    "exercise_settings": {
        "no": "Oppgaveinnstillinger",
        "en": "Exercise settings",
    },
    "num_exercises": {
        "no": "Antall oppgaver",
        "en": "Number of exercises",
    },
    "difficulty": {
        "no": "Vanskelighetsgrad",
        "en": "Difficulty level",
    },
    "easy": {
        "no": "Lett",
        "en": "Easy",
    },
    "medium": {
        "no": "Middels",
        "en": "Medium",
    },
    "hard": {
        "no": "Vanskelig",
        "en": "Hard",
    },
    "differentiation": {
        "no": "Differensiering",
        "en": "Differentiation",
    },
    "generate_3_levels": {
        "no": "Generer 3 nivåer (differensiering)",
        "en": "Generate 3 levels (differentiation)",
    },
    
    # Competency goals
    "competency_goals": {
        "no": "Kompetansemål (LK20)",
        "en": "Competency Goals",
    },
    "select_competency_goals": {
        "no": "Velg hvilke kompetansemål materialet skal dekke.",
        "en": "Select which competency goals the material should cover.",
    },
    
    # Exercise types
    "exercise_types": {
        "no": "Oppgavetyper",
        "en": "Exercise types",
    },
    
    # Generation
    "estimated_time": {
        "no": "Estimert tid",
        "en": "Estimated time",
    },
    "minutes": {
        "no": "minutter",
        "en": "minutes",
    },
    "generate": {
        "no": "Generer materiale",
        "en": "Generate material",
    },
    "generating": {
        "no": "AI-teamet arbeider...",
        "en": "AI team is working...",
    },
    "select_topic_warning": {
        "no": "Velg eller skriv inn et tema for å generere materiale",
        "en": "Select or enter a topic to generate material",
    },
    
    # Progress steps
    "step_pedagogue": {
        "no": "Pedagogen planlegger",
        "en": "Pedagogue is planning",
    },
    "step_pedagogue_desc": {
        "no": "Analyserer læreplan og strukturerer innhold",
        "en": "Analyzing curriculum and structuring content",
    },
    "step_mathematician": {
        "no": "Matematikeren skriver",
        "en": "Mathematician is writing",
    },
    "step_mathematician_desc": {
        "no": "Genererer oppgaver og forklaringer",
        "en": "Generating exercises and explanations",
    },
    "step_illustrator": {
        "no": "Illustratøren tegner",
        "en": "Illustrator is drawing",
    },
    "step_illustrator_desc": {
        "no": "Lager figurer og grafer",
        "en": "Creating figures and graphs",
    },
    "step_editor": {
        "no": "Redaktøren ferdigstiller",
        "en": "Editor is finalizing",
    },
    "step_editor_desc": {
        "no": "Setter sammen og kvalitetssikrer",
        "en": "Assembling and quality checking",
    },
    
    # Results
    "material_generated": {
        "no": "Materiale generert!",
        "en": "Material generated!",
    },
    "download_files": {
        "no": "Last ned filene nedenfor",
        "en": "Download the files below",
    },
    "download_latex": {
        "no": "Last ned LaTeX (.tex)",
        "en": "Download LaTeX (.tex)",
    },
    "download_pdf": {
        "no": "Last ned PDF",
        "en": "Download PDF",
    },
    "download_word": {
        "no": "Last ned Word (.docx)",
        "en": "Download Word (.docx)",
    },
    "copy_latex": {
        "no": "Kopier LaTeX",
        "en": "Copy LaTeX",
    },
    "copied": {
        "no": "LaTeX-kode kopiert til utklippstavlen!",
        "en": "LaTeX code copied to clipboard!",
    },
    "pdf_requires_pdflatex": {
        "no": "PDF krever pdflatex",
        "en": "PDF requires pdflatex",
    },
    "word_requires_docx": {
        "no": "Word krever python-docx",
        "en": "Word requires python-docx",
    },
    "preview": {
        "no": "Forhåndsvisning",
        "en": "Preview",
    },
    "view_latex": {
        "no": "Se LaTeX-kode",
        "en": "View LaTeX code",
    },
    "edit_latex": {
        "no": "Rediger LaTeX-kode",
        "en": "Edit LaTeX code",
    },
    "save_changes": {
        "no": "Lagre endringer",
        "en": "Save changes",
    },
    "recompile_pdf": {
        "no": "Kompiler PDF på nytt",
        "en": "Recompile PDF",
    },
    "lines": {
        "no": "linjer",
        "en": "lines",
    },
    "characters": {
        "no": "tegn",
        "en": "characters",
    },
    "exercises": {
        "no": "oppgaver",
        "en": "exercises",
    },
    
    # Footer
    "built_with": {
        "no": "Bygget med",
        "en": "Built with",
    },
    
    # Errors
    "error_generating": {
        "no": "Feil under generering",
        "en": "Error during generation",
    },
    "saving_files": {
        "no": "Lagrer filer...",
        "en": "Saving files...",
    },
    
    # Sidebar sections
    "my_templates": {
        "no": "Mine maler",
        "en": "My templates",
    },
    "favorites": {
        "no": "Favoritter",
        "en": "Favorites",
    },
    "no_favorites": {
        "no": "Ingen favoritter ennå",
        "en": "No favorites yet",
    },
    "folders_and_tags": {
        "no": "Mapper og tags",
        "en": "Folders and tags",
    },
    "folders": {
        "no": "Mapper",
        "en": "Folders",
    },
    "tags": {
        "no": "Tags",
        "en": "Tags",
    },
    "new_folder": {
        "no": "Ny mappe",
        "en": "New folder",
    },
    "create_folder": {
        "no": "Lag mappe",
        "en": "Create folder",
    },
    "new_tag": {
        "no": "Ny tag",
        "en": "New tag",
    },
    "create_tag": {
        "no": "Lag tag",
        "en": "Create tag",
    },
    "exercise_bank": {
        "no": "Oppgavebank",
        "en": "Exercise bank",
    },
    "exercises_saved": {
        "no": "oppgaver lagret",
        "en": "exercises saved",
    },
    "no_exercises_saved": {
        "no": "Ingen oppgaver lagret ennå",
        "en": "No exercises saved yet",
    },
    "usage_dashboard": {
        "no": "Bruksdashboard",
        "en": "Usage dashboard",
    },
    "watermark_logo": {
        "no": "Vannmerke / Logo",
        "en": "Watermark / Logo",
    },
    "school_name": {
        "no": "Skolenavn",
        "en": "School name",
    },
    "delete": {
        "no": "Slett",
        "en": "Delete",
    },
    "save": {
        "no": "Lagre",
        "en": "Save",
    },
    "load": {
        "no": "Last inn",
        "en": "Load",
    },
    "loaded": {
        "no": "Lastet",
        "en": "Loaded",
    },
    "deleted": {
        "no": "Slettet",
        "en": "Deleted",
    },
    "saved": {
        "no": "Lagret",
        "en": "Saved",
    },
    "search": {
        "no": "Søk",
        "en": "Search",
    },
    "search_all_content": {
        "no": "Søk i alt innhold...",
        "en": "Search all content...",
    },
    "found_results": {
        "no": "Fant {count} resultater",
        "en": "Found {count} results",
    },
    "no_results": {
        "no": "Ingen resultater funnet",
        "en": "No results found",
    },
    "filter_folder": {
        "no": "Filtrer etter mappe",
        "en": "Filter by folder",
    },
    "all_folders": {
        "no": "Alle mapper",
        "en": "All folders",
    },
    "filter_tags": {
        "no": "Filtrer etter tags",
        "en": "Filter by tags",
    },
    
    # Results section
    "pdf_preview": {
        "no": "PDF Forhåndsvisning",
        "en": "PDF Preview",
    },
    "show_preview": {
        "no": "Vis forhåndsvisning",
        "en": "Show preview",
    },
    "print_friendly": {
        "no": "Utskriftsvennlig versjon",
        "en": "Print-friendly version",
    },
    "create_print_version": {
        "no": "Lag utskriftsversjon",
        "en": "Create print version",
    },
    "create_answer_sheet": {
        "no": "Lag kun fasit-ark",
        "en": "Create answer sheet only",
    },
    "regenerate_section": {
        "no": "Regenerer seksjon",
        "en": "Regenerate section",
    },
    "difficulty_analysis": {
        "no": "Vanskelighetsanalyse",
        "en": "Difficulty analysis",
    },
    "qr_code_answers": {
        "no": "QR-kode til fasit",
        "en": "QR code for answers",
    },
    "geogebra_graphs": {
        "no": "GeoGebra Grafer",
        "en": "GeoGebra Graphs",
    },
    "assessment_rubrics": {
        "no": "Vurderingsrubrikker",
        "en": "Assessment rubrics",
    },
    "lk20_coverage": {
        "no": "LK20 Dekningsrapport",
        "en": "Curriculum coverage report",
    },
    "differentiation_assistant": {
        "no": "Differensiering",
        "en": "Differentiation",
    },
    "save_as_favorite": {
        "no": "Lagre som favoritt",
        "en": "Save as favorite",
    },
    "give_name": {
        "no": "Gi favoritten et navn...",
        "en": "Give the favorite a name...",
    },
    "save_to_bank": {
        "no": "Lagre til oppgavebank",
        "en": "Save to exercise bank",
    },
    "find_exercises": {
        "no": "Finn oppgaver",
        "en": "Find exercises",
    },
    "save_all": {
        "no": "Lagre alle",
        "en": "Save all",
    },
    "found_exercises": {
        "no": "Funne oppgaver:",
        "en": "Found exercises:",
    },
    
    # Topic suggestions
    "suggested_topics": {
        "no": "Foreslåtte emner:",
        "en": "Suggested topics:",
    },
    
    # Formula library
    "formula_library": {
        "no": "Formelbibliotek",
        "en": "Formula library",
    },
    "click_to_copy": {
        "no": "Klikk for å kopiere formler til bruk i oppgaver.",
        "en": "Click to copy formulas for use in exercises.",
    },
    "category": {
        "no": "Kategori",
        "en": "Category",
    },
    "copy_latex": {
        "no": "Kopier LaTeX",
        "en": "Copy LaTeX",
    },
    
    # Language level settings
    "language_level": {
        "no": "Språknivå",
        "en": "Language level",
    },
    "language_level_desc": {
        "no": "For elever med norsk som andrespråk",
        "en": "For students with Norwegian as second language",
    },
    "select_language_level": {
        "no": "Velg språknivå",
        "en": "Select language level",
    },
    "language_standard": {
        "no": "Standard norsk",
        "en": "Standard Norwegian",
    },
    "language_b2": {
        "no": "Forenklet norsk (B2)",
        "en": "Simplified Norwegian (B2)",
    },
    "language_b1": {
        "no": "Enklere norsk (B1)",
        "en": "Simpler Norwegian (B1)",
    },
    "language_level_help": {
        "no": "Velg enklere språk for elever som lærer norsk. Matematikknivået forblir det samme.",
        "en": "Choose simpler language for students learning Norwegian. Math level stays the same.",
    },
    "language_level_note": {
        "no": "Det matematiske innholdet er det samme - bare språket er tilpasset.",
        "en": "The mathematical content is the same - only the language is adapted.",
    },
}


class Translator:
    """Translation helper class."""
    
    def __init__(self, language: str = NORWEGIAN):
        """
        Initialize translator.
        
        Args:
            language: Language code ('no' or 'en').
        """
        self.language = language if language in LANGUAGES else NORWEGIAN
    
    def get(self, key: str, **kwargs) -> str:
        """
        Get translated string.
        
        Args:
            key: Translation key.
            **kwargs: Format arguments.
        
        Returns:
            Translated string, or key if not found.
        """
        if key not in TRANSLATIONS:
            return key
        
        text = TRANSLATIONS[key].get(self.language, TRANSLATIONS[key].get(NORWEGIAN, key))
        
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        
        return text
    
    def __call__(self, key: str, **kwargs) -> str:
        """Shorthand for get()."""
        return self.get(key, **kwargs)
    
    def set_language(self, language: str):
        """
        Set the current language.
        
        Args:
            language: Language code.
        """
        if language in LANGUAGES:
            self.language = language


# Default translator instance
t = Translator()


def get_translator(language: str = NORWEGIAN) -> Translator:
    """
    Get a translator for the specified language.
    
    Args:
        language: Language code.
    
    Returns:
        Translator instance.
    """
    return Translator(language)
