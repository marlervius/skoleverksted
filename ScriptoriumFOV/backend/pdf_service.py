import os
import random
import re
import tempfile
from contextlib import contextmanager
from typing import Optional

import requests

if __package__:
    from .text_cleaner import (
        format_mcq_content, format_vocabulary_as_list,
        sanitize_comprehension_for_typst, sanitize_for_typst,
    )
    from .typst_compiler import compile_typst
else:
    from text_cleaner import (
        format_mcq_content, format_vocabulary_as_list,
        sanitize_comprehension_for_typst, sanitize_for_typst,
    )
    from typst_compiler import compile_typst



@contextmanager
def download_image_to_temp(image_url: str):
    """
    Download an image from URL to a temporary file.
    
    Args:
        image_url: URL of the image to download
        
    Yields:
        Path to the temporary file, or None if download failed
        
    Note:
        The temporary file is automatically deleted when the context manager exits.
    """
    temp_path = None
    try:
        # Determine file extension from URL or content type
        response = requests.get(
            image_url,
            headers={"User-Agent": "Scriptorium/1.0"},
            timeout=30,
            stream=True
        )
        response.raise_for_status()
        
        # Get content type to determine extension
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        ext_map = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'image/gif': '.gif',
        }
        ext = ext_map.get(content_type.split(';')[0], '.jpg')
        
        # Create temporary file
        fd, temp_path = tempfile.mkstemp(suffix=ext)
        
        # Write image data to temp file
        with os.fdopen(fd, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        yield temp_path
        
    except Exception as e:
        print(f"Warning: Failed to download image: {e}")
        yield None
        
    finally:
        # Cleanup: delete temporary file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass  # Ignore cleanup errors


def render_cloze_test(items: list) -> str:
    """
    Render cloze test (fill in the blank) exercises.
    Each item should be a sentence with blanks marked as ___ or [blank].
    
    Returns Typst content for cloze exercises.
    """
    if not items:
        return ""
    
    # Define Typst underline element for blanks
    BLANK_ELEMENT = "#box(width: 4em, stroke: (bottom: 1pt + gray))[#h(4em)]"
    # Use a placeholder that won't be escaped
    PLACEHOLDER = "BLANKPLACEHOLDER"
    
    lines = []
    for i, item in enumerate(items, 1):
        text = str(item)
        # First, replace blank markers with placeholder
        text = re.sub(r'\[___+\]|\[blank\]|\(___+\)|\b___+\b', PLACEHOLDER, text)
        # Sanitize the text (this escapes special characters)
        text = sanitize_for_typst(text)
        # Now replace placeholder with actual Typst command (after sanitization)
        text = text.replace(PLACEHOLDER, BLANK_ELEMENT)
        lines.append(f"{i}. {text}")
    
    return "\n\n".join(lines)


def extract_infinitive(verb_text: str) -> str:
    """
    Extract just the infinitive from a verb string.
    Handles cases like:
    - "å bruke" -> "å bruke"
    - "å bruke - bruker - brukte - har brukt" -> "å bruke"
    - "bruke" -> "å bruke"
    """
    text = str(verb_text).strip()
    
    # If it contains " - " (conjugation separator), take only the first part
    if " - " in text:
        text = text.split(" - ")[0].strip()
    
    # If it contains " → " or " -> ", take only the first part
    if " → " in text:
        text = text.split(" → ")[0].strip()
    if " -> " in text:
        text = text.split(" -> ")[0].strip()
    
    # Add "å " prefix if not present (for Norwegian infinitive)
    if not text.startswith("å "):
        text = f"å {text}"
    
    return text


def render_verb_table(items: list, is_english: bool = False) -> str:
    """
    Render verb conjugation table.
    Items should be verbs to conjugate (only infinitive shown, rest empty for students).
    
    Args:
        items: List of verbs to conjugate
        is_english: Whether to use English headers
    
    Returns Typst table for verb conjugation.
    """
    if not items:
        return ""
    
    # Headers based on language
    if is_english:
        headers = "[*Base Form*], [*Present*], [*Past*], [*Perfect*],"
    else:
        headers = "[*Infinitiv*], [*Presens*], [*Preteritum*], [*Perfektum*],"
    
    # Build table rows - first column has infinitive only, rest are empty for students
    rows = []
    seen_verbs = set()  # Avoid duplicates
    
    for item in items:
        # Extract just the infinitive
        infinitive = extract_infinitive(item)
        
        # Skip duplicates
        if infinitive.lower() in seen_verbs:
            continue
        seen_verbs.add(infinitive.lower())
        
        verb = sanitize_for_typst(infinitive)
        # Create row with infinitive in first column, empty cells for student to fill
        rows.append(f'[{verb}], [], [], [],')
    
    if not rows:
        return ""
    
    table_content = "\n    ".join(rows)
    
    return f'''#table(
  columns: (1fr, 1fr, 1fr, 1fr),
  inset: 10pt,
  align: center,
  stroke: 0.5pt + line-color,
  fill: (col, row) => if row == 0 {{ box-bg }} else {{ white }},
  {headers}
  {table_content}
)'''


def render_scrambled_sentences(items: list, is_english: bool = False) -> str:
    """
    Render scrambled sentence exercises.
    
    Args:
        items: List of scrambled sentences
        is_english: Whether to use English labels
    """
    if not items:
        return ""
    
    instruction = "Write the sentence correctly:" if is_english else "Skriv setningen riktig:"
    
    exercises = []
    for i, item in enumerate(items, 1):
        text = str(item).strip()
        
        # Extract words from brackets or split by space
        if '[' in text and ']' in text:
            words = re.findall(r'\[([^\]]+)\]', text)
        else:
            words = [w.strip() for w in re.split(r'[,\s]+', text) if w.strip()]
        
        if words:
            # Create uniform word blocks
            word_boxes = []
            for w in words:
                safe_word = sanitize_for_typst(w)
                # Ensure height and width are somewhat stable for a "button" look
                word_boxes.append(
                    f'#box(stroke: 1pt + line-color, fill: box-bg, inset: (x: 8pt, y: 6pt), radius: 4pt, outset: (y: 2pt))[{safe_word}]'
                )
            
            boxes_str = " #h(0.4em) ".join(word_boxes)
            
            exercises.append(f'''{i}. #block(width: 100%, inset: (y: 0.5em))[
  {boxes_str}
]

#v(0.2em)
#text(size: 9pt, fill: gray)[{instruction}]
#v(0.1em)
#line(length: 100%, stroke: 0.5pt + line-color)
#v(0.8em)''')
    
    return "\n".join(exercises)


def render_matching_exercise(items: list, is_english: bool = False) -> str:
    """
    Render matching/vocabulary exercises as a two-column table.
    Uses a table instead of grid for better page break handling.
    
    Args:
        items: List of term-definition pairs
        is_english: Whether to use English labels
    """
    if not items:
        return ""
    
    # Labels based on language
    term_header = "Term" if is_english else "Begrep"
    def_header = "Definition" if is_english else "Definisjon"
    instruction = "Write the correct letter next to the number (e.g. 1-C):" if is_english else "Skriv riktig bokstav ved siden av tallet (f.eks. 1-C):"
    
    terms = []
    definitions = []
    
    # Improved parsing: some agents return items as "A. Term: Definition"
    # or separate list items. We try to be flexible.
    for item in items:
        item_str = str(item).strip()
        
        pair = None
        # Try various separators
        for sep in [': ', ' - ', ' = ', ' → ', ' -> ']:
            if sep in item_str:
                parts = item_str.split(sep, 1)
                if len(parts) == 2:
                    pair = (parts[0].strip(), parts[1].strip())
                    break
        
        if pair:
            # Strip leading A., B. or 1., 2. if present
            term = re.sub(r'^[A-Z1-9][.)]\s*', '', pair[0])
            defn = re.sub(r'^[A-Z1-9][.)]\s*', '', pair[1])
            terms.append(term)
            definitions.append(defn)
        else:
            # Fallback for single items
            terms.append(re.sub(r'^[A-Z1-9][.)]\s*', '', item_str))
            
    # If we don't have pairs, maybe they are alternating?
    # (Not ideal, but happens)
    if not definitions and len(terms) >= 4:
        mid = len(terms) // 2
        definitions = terms[mid:]
        terms = terms[:mid]
    
    if terms and definitions and len(terms) == len(definitions):
        import random
        random.seed(42)
        shuffled_defs = definitions.copy()
        random.shuffle(shuffled_defs)
        
        letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        table_rows = []
        
        for i in range(len(terms)):
            letter = letters[i] if i < len(letters) else str(i+1)
            t_cell = f'[{letter}. {sanitize_for_typst(terms[i])}]'
            d_cell = f'[{i+1}. {sanitize_for_typst(shuffled_defs[i])}]'
            table_rows.append(f'  {t_cell}, {d_cell},')
        
        # Number of answer slots
        num_items = len(terms)
        answer_slots = " ".join([f"{i+1}\\_" for i in range(min(num_items, 8))])
            
        return f'''#table(
  columns: (1fr, 1fr),
  inset: 8pt,
  align: left,
  stroke: 0.5pt + line-color,
  fill: (col, row) => if row == 0 {{ box-bg }} else {{ white }},
  [*{term_header}*], [*{def_header}*],
{chr(10).join(table_rows)}
)

#v(0.5em)
#text(size: 9pt, fill: gray)[{instruction}]
#h(1em) #text(size: 10pt)[{answer_slots}]'''

    # Fallback to simple list
    lines = [f"{i+1}. {sanitize_for_typst(str(item))}" for i, item in enumerate(items)]
    return "\n\n".join(lines)


def render_preposition_exercise(items: list) -> str:
    """
    Render preposition fill-in exercises.
    
    Returns Typst content with blanks for prepositions.
    """
    if not items:
        return ""
    
    # Define Typst box element for preposition blanks
    PREP_BLANK = "#box(width: 3em, stroke: (bottom: 1pt + gray))[#h(3em)]"
    # Use a placeholder that won't be escaped
    PLACEHOLDER = "PREPPLACEHOLDER"
    
    lines = []
    for i, item in enumerate(items, 1):
        text = str(item)
        # First, replace preposition markers with placeholder
        text = re.sub(r'\[prep\]|\(prep\)|___', PLACEHOLDER, text)
        # Sanitize the text (this escapes special characters)
        text = sanitize_for_typst(text)
        # Now replace placeholder with actual Typst command (after sanitization)
        text = text.replace(PLACEHOLDER, PREP_BLANK)
        lines.append(f"{i}. {text}")
    
    return "\n\n".join(lines)


def render_word_sorting_exercise(items: list, is_english: bool = False) -> str:
    """
    Render word sorting/categorization exercise.
    Shows a mixed list of words and an empty table for students to sort into categories.
    
    The items may contain answers like "Substantiv: x, y, z" which we need to:
    1. Extract all words
    2. Mix them together
    3. Display mixed list + empty table
    
    Args:
        items: List of words or categorized items
        is_english: Whether to use English labels
    """
    if not items:
        return ""
    
    # Default categories based on language
    default_categories = ["Noun", "Verb", "Adjective"] if is_english else ["Substantiv", "Verb", "Adjektiv"]
    instruction = "Write the words in the correct category:" if is_english else "Skriv ordene i riktig kategori:"
    
    # Extract all words from the categorized items
    all_words = []
    categories = []
    
    for item in items:
        item_str = str(item).strip()
        # Check if it's a categorized item like "Substantiv: ord1, ord2, ord3" or "Noun: word1, word2"
        if ':' in item_str:
            parts = item_str.split(':', 1)
            category = parts[0].strip()
            words_part = parts[1].strip()
            
            # Extract words (split by comma or space)
            words = [w.strip().strip('.').strip(',') for w in re.split(r'[,\s]+', words_part) if w.strip()]
            
            if category and category not in categories:
                categories.append(category)
            all_words.extend(words)
        else:
            # Single word
            all_words.append(item_str)
    
    # Remove duplicates and shuffle for each generation
    unique_words = list(set(all_words))
    random.shuffle(unique_words)
    
    if not unique_words:
        return ""
    
    # Create mixed word display
    word_boxes = []
    for w in unique_words[:12]:  # Limit to 12 words
        safe_word = sanitize_for_typst(w)
        word_boxes.append(f'#box(stroke: 1pt + line-color, fill: box-bg, inset: 6pt, radius: 3pt)[{safe_word}]')
    
    words_display = " #h(0.5em) ".join(word_boxes)
    
    # Create empty sorting table based on detected or default categories
    if not categories:
        categories = default_categories
    
    # Limit to 3 categories for layout
    categories = categories[:3]
    
    # Build table with empty cells
    cols = ", ".join(["1fr"] * len(categories))
    headers = ", ".join([f"[*{sanitize_for_typst(cat)}*]" for cat in categories])
    empty_rows = ", ".join(["[]"] * len(categories))
    
    return f'''#block(inset: (y: 0.5em))[
  {words_display}
]

#v(0.8em)
#text(size: 9pt, fill: gray)[{instruction}]
#v(0.3em)

#table(
  columns: ({cols}),
  inset: 10pt,
  align: left,
  stroke: 0.5pt + line-color,
  fill: (col, row) => if row == 0 {{ box-bg }} else {{ white }},
  {headers},
  {empty_rows},
  {empty_rows},
  {empty_rows},
  {empty_rows},
)'''


def render_spelling_exercise(items: list) -> str:
    """
    Render spelling exercises where students fill in missing letters.
    Strips any answers in parentheses like "Kimso_e (Klimasone)".
    """
    if not items:
        return ""
    
    lines = []
    for i, item in enumerate(items, 1):
        text = str(item).strip()
        
        # Remove answer in parentheses: "Kimso_e (Klimasone)" -> "Kimso_e"
        text = re.sub(r'\s*\([^)]+\)\s*$', '', text)
        
        # Also remove answer after colon or dash: "Kimso_e: Klimasone" -> "Kimso_e"
        text = re.sub(r'\s*[:\-–]\s*[A-Za-zÆØÅæøå]+\s*$', '', text)
        
        safe_text = sanitize_for_typst(text.strip())
        lines.append(f"{i}. {safe_text}")
    
    return "\n\n".join(lines)


def render_word_formation_exercise(items: list, is_english: bool = False) -> str:
    """
    Render word formation exercise where students analyze word parts.
    
    Args:
        items: List of compound words or words with prefixes/suffixes
        is_english: Whether to use English labels
    """
    if not items:
        return ""
    
    # Labels based on language
    if is_english:
        headers = "[*Word*], [*Part 1*], [*Part 2*], [*Part 3*],"
        instruction = "Break down each word into its parts:"
    else:
        headers = "[*Ord*], [*Del 1*], [*Del 2*], [*Del 3*],"
        instruction = "Del opp hvert ord i sine deler:"
    
    rows = []
    for item in items:
        word = sanitize_for_typst(str(item).strip())
        # First column has the word, rest are empty for students
        rows.append(f'[{word}], [], [], [],')
    
    if not rows:
        return ""
    
    table_content = "\n    ".join(rows)
    
    return f'''#text(size: 9pt, fill: gray)[{instruction}]
#v(0.3em)

#table(
  columns: (1.5fr, 1fr, 1fr, 1fr),
  inset: 10pt,
  align: center,
  stroke: 0.5pt + line-color,
  fill: (col, row) => if row == 0 {{ box-bg }} else {{ white }},
  {headers}
  {table_content}
)'''


def render_article_exercise(items: list, is_english: bool = False) -> str:
    """
    Render article fill-in exercises (a/an/the for English, en/ei/et for Norwegian).
    
    Args:
        items: List of sentences or phrases with blanks for articles
        is_english: Whether to use English
    """
    if not items:
        return ""
    
    # Define blank element
    ARTICLE_BLANK = "#box(width: 2.5em, stroke: (bottom: 1pt + gray))[#h(2.5em)]"
    PLACEHOLDER = "ARTICLEBLANK"
    
    if is_english:
        instruction = "Fill in the correct article: a, an, or the"
        hint = "#text(size: 9pt, fill: gray)[Tip: Use 'a' before consonant sounds, 'an' before vowel sounds]"
    else:
        instruction = "Fyll inn riktig artikkel: en, ei eller et"
        hint = "#text(size: 9pt, fill: gray)[Husk: Hankjønn = en, Hunkjønn = ei, Intetkjønn = et]"
    
    lines = [f"#text(size: 10pt)[{instruction}]", hint, "#v(0.5em)"]
    
    for i, item in enumerate(items, 1):
        text = str(item)
        # Replace blank markers with placeholder
        text = re.sub(r'___|\[article\]|\[artikkel\]|_+', PLACEHOLDER, text)
        text = sanitize_for_typst(text)
        text = text.replace(PLACEHOLDER, ARTICLE_BLANK)
        lines.append(f"{i}. {text}")
        lines.append("#v(0.3em)")
    
    return "\n".join(lines)


def render_plural_exercise(items: list, is_english: bool = False) -> str:
    """
    Render plural noun exercises with a table format.
    
    Args:
        items: List of singular nouns to pluralize
        is_english: Whether to use English
    """
    if not items:
        return ""
    
    if is_english:
        headers = "[*Singular*], [*Plural*],"
        instruction = "Write the plural form of each noun:"
    else:
        headers = "[*Entall*], [*Flertall*],"
        instruction = "Skriv flertallsformen av hvert substantiv:"
    
    rows = []
    for item in items:
        # Clean the item - remove any existing answers
        text = str(item).strip()
        text = re.sub(r'\s*→.*$', '', text)  # Remove arrow and what follows
        text = re.sub(r'\s*->.*$', '', text)
        text = re.sub(r'\s*\([^)]+\)\s*$', '', text)  # Remove parentheses
        word = sanitize_for_typst(text.strip())
        rows.append(f'[{word}], [],')
    
    if not rows:
        return ""
    
    table_content = "\n    ".join(rows)
    
    return f'''#text(size: 10pt)[{instruction}]
#v(0.5em)

#table(
  columns: (1fr, 1fr),
  inset: 10pt,
  align: left,
  stroke: 0.5pt + line-color,
  fill: (col, row) => if row == 0 {{ box-bg }} else {{ white }},
  {headers}
  {table_content}
)'''


def render_fill_in_generic(items: list, is_english: bool = False) -> str:
    """
    Generic fill-in-the-blank exercise renderer.
    Works for pronouns, possessives, question words, conjunctions, modal verbs, etc.
    
    Args:
        items: List of sentences with blanks (___) or hints in parentheses
        is_english: Whether to use English
    """
    if not items:
        return ""
    
    # Define blank element
    BLANK = "#box(width: 4em, stroke: (bottom: 1pt + gray))[#h(4em)]"
    PLACEHOLDER = "FILLBLANK"
    
    lines = []
    for i, item in enumerate(items, 1):
        text = str(item)
        
        # Check if there's a hint in parentheses at the end
        hint_match = re.search(r'\(([^)]+)\)\s*$', text)
        hint = ""
        if hint_match:
            hint = f" #text(size: 8pt, fill: gray)[({hint_match.group(1)})]"
            text = text[:hint_match.start()].strip()
        
        # Replace blank markers with placeholder
        text = re.sub(r'___+|\[blank\]|\[fill\]', PLACEHOLDER, text)
        text = sanitize_for_typst(text)
        text = text.replace(PLACEHOLDER, BLANK)
        
        lines.append(f"{i}. {text}{hint}")
        lines.append("#v(0.4em)")
    
    return "\n".join(lines)


def render_comparative_exercise(items: list, is_english: bool = False) -> str:
    """
    Render comparative/superlative adjective exercises with a table format.
    
    Args:
        items: List of adjectives to transform
        is_english: Whether to use English
    """
    if not items:
        return ""
    
    if is_english:
        headers = "[*Adjective*], [*Comparative*], [*Superlative*],"
        instruction = "Write the comparative and superlative forms:"
        example = "#text(size: 9pt, fill: gray)[Example: big → bigger → the biggest]"
    else:
        headers = "[*Adjektiv*], [*Komparativ*], [*Superlativ*],"
        instruction = "Skriv komparativ og superlativ:"
        example = "#text(size: 9pt, fill: gray)[Eksempel: stor → større → størst]"
    
    rows = []
    for item in items:
        # Clean the item - keep only the base adjective
        text = str(item).strip()
        text = re.sub(r'\s*→.*$', '', text)
        text = re.sub(r'\s*->.*$', '', text)
        text = re.sub(r'\s*\([^)]+\)\s*$', '', text)
        word = sanitize_for_typst(text.strip())
        rows.append(f'[{word}], [], [],')
    
    if not rows:
        return ""
    
    table_content = "\n    ".join(rows)
    
    return f'''#text(size: 10pt)[{instruction}]
{example}
#v(0.5em)

#table(
  columns: (1fr, 1fr, 1fr),
  inset: 10pt,
  align: left,
  stroke: 0.5pt + line-color,
  fill: (col, row) => if row == 0 {{ box-bg }} else {{ white }},
  {headers}
  {table_content}
)'''


def render_passive_exercise(items: list, is_english: bool = False) -> str:
    """
    Render passive voice transformation exercises.
    
    Args:
        items: List of active sentences to transform to passive
        is_english: Whether to use English
    """
    if not items:
        return ""
    
    if is_english:
        instruction = "Rewrite the sentences in passive voice:"
        example = '#text(size: 9pt, fill: gray)[Example: "The teacher reads the book." → "The book is read by the teacher."]'
    else:
        instruction = "Skriv setningene om til passiv form:"
        example = '#text(size: 9pt, fill: gray)[Eksempel: "Læreren leser boken." → "Boken leses av læreren." / "Boken blir lest av læreren."]'
    
    lines = [f"#text(size: 10pt)[{instruction}]", example, "#v(0.5em)"]
    
    for i, item in enumerate(items, 1):
        text = sanitize_for_typst(str(item).strip())
        lines.append(f"{i}. {text}")
        lines.append("#line(length: 100%, stroke: 0.5pt + line-color)")
        lines.append("#v(0.3em)")
    
    return "\n".join(lines)


def render_sentence_combination_exercise(items: list, is_english: bool = False) -> str:
    """
    Render sentence combination exercises (for relative clauses, conjunctions).
    
    Args:
        items: List of sentence pairs to combine
        is_english: Whether to use English
    """
    if not items:
        return ""
    
    if is_english:
        instruction = "Combine the sentences using the word in parentheses:"
    else:
        instruction = "Kombiner setningene ved å bruke ordet i parentes:"
    
    lines = [f"#text(size: 10pt)[{instruction}]", "#v(0.5em)"]
    
    for i, item in enumerate(items, 1):
        text = sanitize_for_typst(str(item).strip())
        lines.append(f"{i}. {text}")
        lines.append("#line(length: 100%, stroke: 0.5pt + line-color)")
        lines.append("#v(0.5em)")
    
    return "\n".join(lines)


def render_error_correction_exercise(items: list, is_english: bool = False) -> str:
    """
    Render an error-correction exercise (#8).
    Shows 5 numbered sentences; students find and correct 3 that have grammar mistakes.
    """
    if not items:
        return ""
    lines = []
    hint = ("Hint: three sentences contain a grammar mistake." if is_english
            else "Hint: tre av setningene har en grammatikkfeil.")
    lines.append(f"#text(size: 9pt, style: \"italic\", fill: gray)[{hint}]")
    lines.append("#v(0.4em)")
    for i, item in enumerate(items, 1):
        text = sanitize_for_typst(str(item).strip())
        lines.append(f"{i}. {text}")
        lines.append("#v(0.2em)")
        # Two writing lines per sentence (room for correction)
        lines.append("#line(length: 100%, stroke: 0.5pt + line-color)")
        lines.append("#line(length: 100%, stroke: 0.5pt + line-color)")
        lines.append("#v(0.5em)")
    return "\n".join(lines)


def format_language_exercises(exercises: dict, options: dict = None, is_english: bool = False) -> str:
    """
    Format language exercises dict into Typst content with specialized renderers.
    
    Args:
        exercises: Dict with grammar_tasks, vocabulary_tasks, syntax_tasks
        options: Dictionary of modular options
        is_english: Whether to use English labels
        
    Returns:
        Formatted Typst content string
    """
    if not exercises:
        return ""
    
    # Set default options if None
    if options is None:
        options = {"grammar_tasks": True, "vocabulary_tasks": True}
    
    # Labels based on language
    labels = {
        "grammar": "Grammar" if is_english else "Grammatikk",
        "vocabulary": "Vocabulary" if is_english else "Ordforråd",
        "syntax": "Sentence Structure" if is_english else "Setningsstruktur",
        "task": "Task" if is_english else "Oppgave",
    }
    
    sections = []
    
    # Grammar tasks (verb conjugation, prepositions, word categories)
    grammar_tasks = exercises.get("grammar_tasks", [])
    if grammar_tasks and options.get("grammar_tasks", True):
        grammar_content = []
        
        for i, task in enumerate(grammar_tasks, 1):
            if isinstance(task, dict):
                instruction = sanitize_for_typst(task.get("instruction", ""))
                items = task.get("items", [])
                task_type = task.get("type", "").lower()
                
                # Wrap each task in a non-breakable block
                grammar_content.append("#block(breakable: false)[")
                grammar_content.append(f"#strong[{labels['task']} {i}]")
                if instruction:
                    grammar_content.append(f"\n{instruction}\n")
                grammar_content.append("#v(0.5em)")
                
                # Use specialized renderer based on task type (Norwegian and English variants)
                # Adjective inflection tasks (must be checked before verb "bøy" catch-all)
                if "adjektiv" in task_type or "adjective_inflect" in task_type:
                    grammar_content.append(render_fill_in_generic(items, is_english))
                # Verb conjugation tasks
                elif "verb" in task_type or "conjugat" in task_type or "bøy" in task_type or "tense" in task_type or "presens" in task_type:
                    grammar_content.append(render_verb_table(items, is_english))
                # Article tasks (a/an/the, en/ei/et)
                elif "artikl" in task_type or "article" in task_type:
                    grammar_content.append(render_article_exercise(items, is_english))
                # Plural noun tasks
                elif "flertall" in task_type or "plural" in task_type:
                    grammar_content.append(render_plural_exercise(items, is_english))
                # Comparative/superlative tasks
                elif "kompar" in task_type or "superlat" in task_type or "comparat" in task_type:
                    grammar_content.append(render_comparative_exercise(items, is_english))
                # Passive voice tasks
                elif "passiv" in task_type or "passive" in task_type:
                    grammar_content.append(render_passive_exercise(items, is_english))
                # Relative clauses / sentence combination tasks
                elif "relativ" in task_type or "combin" in task_type or "kombiner" in task_type:
                    grammar_content.append(render_sentence_combination_exercise(items, is_english))
                # Preposition tasks
                elif "prep" in task_type:
                    grammar_content.append(render_preposition_exercise(items))
                # Word sorting/categorization tasks
                elif "ordklasse" in task_type or "sorter" in task_type or "kategori" in task_type or "word_sort" in task_type:
                    grammar_content.append(render_word_sorting_exercise(items, is_english))
                # Word formation / compound words tasks
                elif "word_form" in task_type or "sammensatt" in task_type:
                    grammar_content.append(render_word_formation_exercise(items, is_english))
                # Pronoun, possessive, question word, conjunction, modal, conditional tasks
                # These all use a generic fill-in renderer
                elif any(x in task_type for x in ["pronomen", "pronoun", "eiendom", "possessiv", "possess",
                                                   "spørre", "question", "konjunk", "conjunct", "bindeord",
                                                   "modal", "conditional", "betingelse"]):
                    grammar_content.append(render_fill_in_generic(items, is_english))
                # Error correction tasks (#8)
                elif "feilrett" in task_type or "error_correct" in task_type or "error correct" in task_type:
                    grammar_content.append(render_error_correction_exercise(items, is_english))
                else:
                    # Default: generic fill-in (handles most sentence-based exercises)
                    grammar_content.append(render_fill_in_generic(items, is_english))
                
                grammar_content.append("]")  # Close block
                grammar_content.append("#v(1em)")
            elif isinstance(task, str):
                grammar_content.append(f"- {sanitize_for_typst(task)}")
        
        if grammar_content:
            sections.append(f"#strong[{labels['grammar']}]\n#v(0.5em)\n" + "\n".join(grammar_content))
    
    # Vocabulary tasks (matching, fill-in-blank, spelling, cloze)
    vocab_tasks = exercises.get("vocabulary_tasks", [])
    if vocab_tasks and options.get("vocabulary_tasks", True):
        vocab_content = []
        
        for i, task in enumerate(vocab_tasks, 1):
            if isinstance(task, dict):
                instruction = sanitize_for_typst(task.get("instruction", ""))
                items = task.get("items", [])
                task_type = task.get("type", "").lower()
                
                # Wrap each task in a non-breakable block
                vocab_content.append("#block(breakable: false)[")
                vocab_content.append(f"#strong[{labels['task']} {i}]")
                if instruction:
                    vocab_content.append(f"\n{instruction}\n")
                vocab_content.append("#v(0.5em)")
                
                # Use specialized renderer based on task type (Norwegian and English variants)
                if "fill" in task_type or "blank" in task_type or "cloze" in task_type or "fyll" in task_type:
                    vocab_content.append(render_cloze_test(items))
                elif "match" in task_type or "koble" in task_type:
                    vocab_content.append(render_matching_exercise(items, is_english))
                elif "stav" in task_type or "spell" in task_type:
                    # Spelling exercise - strip answers in parentheses
                    vocab_content.append(render_spelling_exercise(items))
                else:
                    # Default: simple list (but also check for hidden answers)
                    for j, item in enumerate(items, 1):
                        item_text = str(item)
                        # Strip answers in parentheses for any task type
                        item_text = re.sub(r'\s*\([^)]+\)\s*$', '', item_text)
                        vocab_content.append(f"{j}. {sanitize_for_typst(item_text)}")
                
                vocab_content.append("]")  # Close block
                vocab_content.append("#v(1em)")
            elif isinstance(task, str):
                vocab_content.append(f"- {sanitize_for_typst(task)}")
        
        if vocab_content:
            sections.append(f"#strong[{labels['vocabulary']}]\n#v(0.5em)\n" + "\n".join(vocab_content))
    
    # Syntax tasks (scrambled sentences, word order)
    # Syntax tasks are usually part of grammar or overall language training
    syntax_tasks = exercises.get("syntax_tasks", [])
    if syntax_tasks and options.get("grammar_tasks", True):
        syntax_content = []
        
        for i, task in enumerate(syntax_tasks, 1):
            if isinstance(task, dict):
                instruction = sanitize_for_typst(task.get("instruction", ""))
                items = task.get("items", [])
                task_type = task.get("type", "").lower()
                
                # Wrap each task in a non-breakable block
                syntax_content.append("#block(breakable: false)[")
                syntax_content.append(f"#strong[{labels['task']} {i}]")
                if instruction:
                    syntax_content.append(f"\n{instruction}\n")
                syntax_content.append("#v(0.5em)")
                
                # Scrambled sentences get special treatment (Norwegian and English variants)
                if "scrambl" in task_type or "order" in task_type or "stokk" in task_type or "rekkefølge" in task_type:
                    syntax_content.append(render_scrambled_sentences(items, is_english))
                else:
                    # Default: simple list with writing lines
                    for j, item in enumerate(items, 1):
                        syntax_content.append(f"{j}. {sanitize_for_typst(str(item))}")
                        syntax_content.append("#line(length: 100%, stroke: 0.5pt + line-color)")
                        syntax_content.append("#v(0.5em)")
                
                syntax_content.append("]")  # Close block
                syntax_content.append("#v(1em)")
            elif isinstance(task, str):
                syntax_content.append(f"- {sanitize_for_typst(task)}")
        
        if syntax_content:
            sections.append(f"#strong[{labels['syntax']}]\n#v(0.5em)\n" + "\n".join(syntax_content))
    
    return "\n\n".join(sections)


def create_typst_template(
    topic: str,
    level: str,
    subject: str = "Norsk",
    main_text: str = "",
    vocabulary: str = "",
    comprehension: str = "",
    discussion: str = "",
    cultural: str = "",
    role_play: str = "",
    image_description: str = "",
    writing_frame: str = "",
    real_case: str = "",
    image_path: Optional[str] = None,
    language_exercises: Optional[dict] = None,
    teacher_key: str = "",
    teacher_key_content: str = "",
    series_header: str = "",
    accessibility: Optional[dict] = None,
    options: dict = None
) -> str:
    """
    Create a Typst document template for the lesson plan.
    
    Args:
        topic: The lesson topic
        level: CEFR level (A1, A2, B1, B2)
        main_text: The educational text content
        vocabulary: Key terms and definitions
        comprehension: Multiple choice questions
        discussion: Open-ended discussion questions
        image_path: Optional path to a local image file
        language_exercises: Optional dict with grammar, vocabulary, syntax tasks
        teacher_key: Optional answer key content
        options: Dictionary of modular options
    
    Returns:
        Complete Typst document as a string
    """
    # Set default options if None
    if options is None:
        options = {
            "deep_dive": False, 
            "grammar_tasks": True, 
            "vocabulary_tasks": True,
            "comprehension_tasks": True,
            "discussion_tasks": True,
            "teacher_key": False
        }
    
    # Determine if output should be in English
    is_english = subject.lower() == "engelsk"
    
    # Labels based on language
    labels = {
        "worksheet": "Worksheet" if is_english else "Læringsark",
        "level": "Level" if is_english else "Nivå",
        "adult_education": "Adult Education" if is_english else "Voksenopplæring",
        "text": "Text" if is_english else "Tekst",
        "vocabulary": "Key Vocabulary" if is_english else "Viktige begreper",
        "language_training": "Language Training" if is_english else "Språktrening",
        "comprehension": "Reading Comprehension" if is_english else "Leseforståelse",
        "discussion": "Discussion" if is_english else "Diskusjon",
        "cultural": "Cultural Perspective" if is_english else "Kulturblikk",
        "role_play": "Role Play" if is_english else "Rollespill",
        "image_desc": "Image Description" if is_english else "Bildebeskrivelse",
        "writing_frame": "Writing Frame" if is_english else "Skriveramme",
        "real_case": "Real Case" if is_english else "Virkelig Case",
        "teacher_key": "Answer Key" if is_english else "Lærerens Fasit",
        "write_here": "Write your answers here:" if is_english else "Skriv dine svar her:",
        "reflection": "Reflection:" if is_english else "Refleksjon:",
        "practice_dialogue": "Practice the dialogue with a partner:" if is_english else "Øv dialogen med en partner:",
        "look_at_image": "Look at the image at the top and answer the questions:" if is_english else "Se på bildet øverst på arket og svar på spørsmålene:",
        "your_answers": "Write your answers:" if is_english else "Skriv dine svar:",
        "use_starters": "Use the sentence starters below to write a short text:" if is_english else "Bruk setningsstartene under for å skrive en kort tekst:",
        "your_text": "Your text:" if is_english else "Din tekst:",
        "write_below": "Write here:" if is_english else "Skriv her:",
        "generated_by": "Generated by Scriptorium | Adapted to" if is_english else "Generert av Scriptorium | Tilpasset",
        "level_cefr": "level (CEFR)" if is_english else "-nivå (CEFR)",
        "photo": "Photo: Wikimedia Commons" if is_english else "Foto: Wikimedia Commons",
        "deep_dive": "DEEP DIVE" if is_english else "FORDYPNING",
        }

    # Process the content using the robust sanitizer
    # Main text and topic don't need section cleaning
    safe_topic = sanitize_for_typst(topic)
    safe_main_text = sanitize_for_typst(main_text)
    
    # Section content gets extra cleaning (headers, meta-instructions removed)
    safe_vocabulary = format_vocabulary_as_list(sanitize_for_typst(vocabulary, is_section_content=True))
    safe_discussion = sanitize_for_typst(discussion, is_section_content=True)
    safe_cultural = sanitize_for_typst(cultural, is_section_content=True)
    
    # Advanced modules
    safe_role_play = sanitize_for_typst(role_play, is_section_content=True)
    safe_image_description = sanitize_for_typst(image_description, is_section_content=True)
    safe_writing_frame = sanitize_for_typst(writing_frame, is_section_content=True)
    safe_real_case = sanitize_for_typst(real_case, is_section_content=True)
    
    # Comprehension needs answer markers removed for student PDF
    safe_comprehension = sanitize_comprehension_for_typst(comprehension)
    
    # Teacher key: prefer explicit teacher_key_content from agents (#4), fall back to parsed section
    raw_teacher_key = teacher_key_content if teacher_key_content else teacher_key
    safe_teacher_key = sanitize_for_typst(raw_teacher_key, is_section_content=True)

    # Accessibility settings (#12)
    acc = accessibility or {}
    pdf_font = "OpenDyslexic" if acc.get("dyslexia_font") else "Noto Sans"
    pdf_font_size = "13pt" if acc.get("large_print") else "11pt"
    if acc.get("high_contrast"):
        color_primary   = 'rgb("#000000")'
        color_secondary = 'rgb("#000000")'
        color_accent    = 'rgb("#000000")'
        color_box_bg    = 'rgb("#ffffff")'
        color_line      = 'rgb("#000000")'
        page_fill_line  = '#set page(fill: white)'
    else:
        color_primary   = 'rgb("#1e40af")'
        color_secondary = 'rgb("#3b82f6")'
        color_accent    = 'rgb("#0ea5e9")'
        color_box_bg    = 'rgb("#f1f5f9")'
        color_line      = 'rgb("#cbd5e1")'
        page_fill_line  = ''

    # Series header badge (#11)
    series_badge = ""
    if series_header:
        safe_series = sanitize_for_typst(series_header)
        series_badge = f'''
#align(center)[
  #box(fill: rgb("#7c3aed"), inset: (x: 10pt, y: 5pt), radius: 3pt)[
    #text(fill: white, size: 9pt, weight: "bold")[📚 {safe_series}]
  ]
]
#v(0.5em)
'''
    
    # Format language exercises if provided and requested
    safe_language_exercises = ""
    if language_exercises and (options.get("grammar_tasks", True) or options.get("vocabulary_tasks", True)):
        safe_language_exercises = format_language_exercises(language_exercises, options, is_english)
    
    # Build image section if image path is provided
    image_section = ""
    if image_path:
        image_section = f'''
// Featured image from Wikimedia Commons
#align(center)[
  #block(
    width: 90%,
    clip: true,
    radius: 6pt,
    stroke: 1pt + line-color,
  )[
    #image("{image_path}", width: 100%)
  ]
  #v(0.3em)
  #text(size: 9pt, fill: gray, style: "italic")[
    {labels["photo"]}
  ]
]

#v(1em)
'''
    
    # Deep dive badge/header
    deep_dive_badge = ""
    if options.get("deep_dive", False):
        deep_dive_badge = f'''
#align(right)[
  #box(fill: accent-color, inset: 6pt, radius: 3pt)[
    #text(fill: white, size: 9pt, weight: "bold")[🚀 {labels["deep_dive"]}]
  ]
]
#v(-1em)
'''

    # Build language exercises section if provided (placed after Viktige begreper)
    language_exercises_section = ""
    if safe_language_exercises:
        language_exercises_section = f'''
// Language exercises (CLIL)
#heading(level: 2)[
  #text(fill: primary-color)[🔡 {labels["language_training"]}]
]

#block(
  width: 100%,
  inset: 1.2em,
  radius: 6pt,
  fill: rgb("#fef3c7"),
  stroke: 1pt + rgb("#f59e0b"),
)[
  {safe_language_exercises}
]

#v(1.5em)
'''
    
    # Vocabulary section
    vocabulary_section = ""
    if options.get("vocabulary_tasks", True) and safe_vocabulary:
        vocabulary_section = f'''
// Vocabulary box - kept together
#block(breakable: false)[
#heading(level: 2)[
  #text(fill: primary-color)[📚 {labels["vocabulary"]}]
]

#block(
  width: 100%,
  fill: box-bg,
  inset: 1.2em,
  radius: 6pt,
  stroke: 1pt + line-color,
)[
  {safe_vocabulary}
]
]

#v(1.5em)
'''

    # Comprehension section - format MCQs properly
    comprehension_section = ""
    if options.get("comprehension_tasks", True) and safe_comprehension:
        # Format the comprehension content to ensure proper MCQ layout
        formatted_comprehension = format_mcq_content(safe_comprehension)
        
        comprehension_section = f'''
// Reading comprehension - kept together with breakable: false
#block(breakable: false)[
#heading(level: 2)[
  #text(fill: primary-color)[✏️ {labels["comprehension"]}]
]

#block(
  width: 100%,
  inset: (x: 1em, y: 0.5em),
)[
  {formatted_comprehension}
]
]

#v(1.5em)
'''

    # Discussion section
    discussion_section = ""
    if options.get("discussion_tasks", True) and safe_discussion:
        discussion_section = f'''
// Discussion questions with writing lines
#block(breakable: false)[
#heading(level: 2)[
  #text(fill: primary-color)[💬 {labels["discussion"]}]
]

// Helper function for writing lines
#let writing-lines(count) = {{
  for i in range(count) {{
    v(0.8em)
    line(length: 100%, stroke: 0.5pt + line-color)
  }}
}}

#block(
  width: 100%,
  inset: (x: 1em, y: 0.5em),
)[
  {safe_discussion}
  
  #v(0.5em)
  #text(size: 10pt, fill: gray)[{labels["write_here"]}]
  #writing-lines(4)
]
]

#v(1.5em)
'''

    # Cultural section
    cultural_section = ""
    if safe_cultural:
        cultural_section = f'''
// Cultural comparison section
#heading(level: 2)[
  #text(fill: primary-color)[🌍 {labels["cultural"]}]
]

#block(
  width: 100%,
  inset: (x: 1em, y: 0.5em),
)[
  {safe_cultural}
  
  #v(0.5em)
  #text(size: 10pt, fill: gray)[{labels["reflection"]}]
  #for i in range(3) {{
    v(0.8em)
    line(length: 100%, stroke: 0.5pt + line-color)
  }}
]

#v(1.5em)
'''

    # Role Play section
    role_play_section = ""
    if safe_role_play:
        role_play_section = f'''
// Role play section
#heading(level: 2)[
  #text(fill: primary-color)[🎭 {labels["role_play"]}]
]

#block(
  width: 100%,
  fill: rgb("#fef3c7"),
  inset: 1.2em,
  radius: 6pt,
  stroke: 1pt + rgb("#f59e0b"),
)[
  {safe_role_play}
]

#v(0.5em)
#text(size: 10pt, fill: gray)[{labels["practice_dialogue"]}]
#for i in range(4) {{
  v(0.8em)
  line(length: 100%, stroke: 0.5pt + line-color)
}}

#v(1.5em)
'''

    # Image Description section
    image_description_section = ""
    if safe_image_description:
        image_description_section = f'''
// Image description section
#heading(level: 2)[
  #text(fill: primary-color)[🖼️ {labels["image_desc"]}]
]

#block(
  width: 100%,
  fill: rgb("#e0f2fe"),
  inset: 1.2em,
  radius: 6pt,
  stroke: 1pt + rgb("#0284c7"),
)[
  #text(size: 10pt, fill: rgb("#0369a1"))[{labels["look_at_image"]}]
  
  #v(0.5em)
  {safe_image_description}
]

#v(0.5em)
#text(size: 10pt, fill: gray)[{labels["your_answers"]}]
#for i in range(5) {{
  v(0.8em)
  line(length: 100%, stroke: 0.5pt + line-color)
}}

#v(1.5em)
'''

    # Writing Frame section
    writing_frame_section = ""
    if safe_writing_frame:
        writing_frame_section = f'''
// Writing frame section
#heading(level: 2)[
  #text(fill: primary-color)[✍️ {labels["writing_frame"]}]
]

#block(
  width: 100%,
  fill: rgb("#f0fdf4"),
  inset: 1.2em,
  radius: 6pt,
  stroke: 1pt + rgb("#22c55e"),
)[
  #text(size: 10pt, fill: rgb("#166534"))[{labels["use_starters"]}]
  
  #v(0.5em)
  {safe_writing_frame}
]

#v(0.5em)
#text(size: 10pt, fill: gray)[{labels["your_text"]}]
#for i in range(8) {{
  v(0.8em)
  line(length: 100%, stroke: 0.5pt + line-color)
}}

#v(1.5em)
'''

    # Real Case section (email, SMS, official letter)
    real_case_section = ""
    if safe_real_case:
        real_case_section = f'''
// Real case section (practical writing)
#heading(level: 2)[
  #text(fill: primary-color)[📧 {labels["real_case"]}]
]

#block(
  width: 100%,
  fill: rgb("#fdf4ff"),
  inset: 1.2em,
  radius: 6pt,
  stroke: 1pt + rgb("#a855f7"),
)[
  {safe_real_case}
]

#v(0.5em)
#text(size: 10pt, fill: gray)[{labels["write_below"]}]
#block(
  width: 100%,
  stroke: 1pt + line-color,
  inset: 1em,
  radius: 4pt,
)[
  #for i in range(10) {{
    v(0.8em)
    line(length: 100%, stroke: 0.3pt + rgb("#e5e7eb"))
  }}
]

#v(1.5em)
'''

    # Teacher Key Section (Fasit)
    teacher_key_section = ""
    if options.get("teacher_key", False) and safe_teacher_key:
        teacher_key_section = f'''
#pagebreak()

#align(center)[
  #block(
    width: 100%,
    fill: rgb("#059669"), // Green for teacher key
    inset: 1em,
    radius: 4pt,
  )[
    #text(fill: white, size: 16pt, weight: "bold")[
      {labels["teacher_key"]}
    ]
    #v(0.2em)
    #text(fill: rgb("#ecfdf5"), size: 10pt)[
      {safe_topic} | {labels["level"]} {level}
    ]
  ]
]

#v(1em)

#block(
  width: 100%,
  inset: 1.5em,
  radius: 6pt,
  fill: rgb("#f0fdf4"),
  stroke: 1pt + rgb("#10b981"),
)[
  {safe_teacher_key}
]
'''

    # Build the Typst document
    typst_doc = f'''// Scriptorium - Lesson Plan
// UTF-8 encoding for Norwegian characters (æ, ø, å)

#set document(
  title: "Læringsark: {safe_topic}",
  author: "Scriptorium",
)

#set page(
  paper: "a4",
  margin: (x: 2cm, y: 2.5cm),
  header: context {{
    if counter(page).get().first() > 1 [
      #set text(size: 9pt, fill: gray)
      {labels["worksheet"]}: {safe_topic} #h(1fr) {labels["level"]} {level}
    ]
  }},
  footer: context {{
    set text(size: 9pt, fill: gray)
    h(1fr)
    counter(page).display("1 / 1", both: true)
    h(1fr)
  }},
)

{page_fill_line}
#set text(
  font: "{pdf_font}",
  size: {pdf_font_size},
  lang: "nb",  // Norwegian Bokmål
)

#set par(
  justify: true,
  leading: 0.8em,
)

#set heading(numbering: none)

// Color definitions
#let primary-color = {color_primary}
#let secondary-color = {color_secondary}
#let accent-color = {color_accent}
#let box-bg = {color_box_bg}
#let line-color = {color_line}

// Header
#align(center)[
  #block(
    width: 100%,
    fill: primary-color,
    inset: 1.2em,
    radius: 4pt,
  )[
    #text(fill: white, size: 18pt, weight: "bold")[
      {labels["worksheet"]}: {safe_topic}
    ]
    #v(0.3em)
    #text(fill: rgb("#bfdbfe"), size: 12pt)[
      {labels["level"]} {level} #h(0.5em) | #h(0.5em) {labels["adult_education"]}
    ]
  ]
]

#v(1em)

{series_badge}

{deep_dive_badge}

{image_section}

// Main educational text
#heading(level: 2)[
  #text(fill: primary-color)[📖 {labels["text"]}]
]

#block(
  width: 100%,
  inset: 1em,
  stroke: (left: 3pt + secondary-color),
)[
  {safe_main_text}
]

#v(1.5em)

{vocabulary_section}

{language_exercises_section}

{comprehension_section}

{discussion_section}

{cultural_section}

{role_play_section}

{image_description_section}

{writing_frame_section}

{real_case_section}

// Footer note
#align(center)[
  #block(
    width: 80%,
    inset: 0.8em,
  )[
    #text(size: 9pt, fill: gray)[
      {labels["generated_by"]} {level} {labels["level_cefr"]}
    ]
  ]
]

{teacher_key_section}
'''
    
    return typst_doc


def parse_worksheet_content(worksheet: str) -> dict:
    """
    Parse the worksheet content from the AI agent into structured sections.
    More robust parsing to avoid section content bleeding into each other.
    """
    sections = {
        "vocabulary": "",
        "comprehension": "",
        "discussion": "",
        "cultural": "",
        "role_play": "",
        "image_description": "",
        "writing_frame": "",
        "real_case": "",
        "teacher_key": ""
    }
    
    text = worksheet.strip()
    
    # Extract Fasit first (it's usually at the very end)
    fasit_patterns = [
        r'(?:\n\s*)?(?:FASIT|Fasit|ANSWER KEY|Answer Key|Lærerens fasit)[:\s]*\n(.*)$',
        r'(?:\n\s*)?(?:={3,}|_{3,}|-{3,})\s*(?:FASIT|Fasit)[:\s]*\n(.*)$'
    ]
    for pattern in fasit_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            sections["teacher_key"] = match.group(1).strip()
            text = text[:match.start()].strip()
            break

    # Define section patterns with clearer boundaries
    # Using flexible letter matching since sections can have different letters based on which options are enabled
    # Includes both Norwegian and English patterns
    section_patterns = [
        ('vocabulary', [
            # Norwegian
            r'(?:^|\n)\s*[a-z]\)\s*VIKTIGE\s*BEGREPER[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Viktige\s*begreper[^\n]*\n',
            r'(?:^|\n)\s*VIKTIGE\s*BEGREPER[^\n]*\n',
            r'(?:^|\n)\s*Viktige\s*begreper[^\n]*\n',
            # English
            r'(?:^|\n)\s*[a-z]\)\s*KEY\s*VOCABULARY[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Key\s*[Vv]ocabulary[^\n]*\n',
            r'(?:^|\n)\s*KEY\s*VOCABULARY[^\n]*\n',
            r'(?:^|\n)\s*Key\s*[Vv]ocabulary[^\n]*\n',
        ]),
        ('comprehension', [
            # Norwegian
            r'(?:^|\n)\s*[a-z]\)\s*LESEFORSTÅELSE[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Leseforståelse[^\n]*\n',
            r'(?:^|\n)\s*LESEFORSTÅELSE[^\n]*\n',
            r'(?:^|\n)\s*Leseforståelse[^\n]*\n',
            # English
            r'(?:^|\n)\s*[a-z]\)\s*READING\s*COMPREHENSION[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Reading\s*[Cc]omprehension[^\n]*\n',
            r'(?:^|\n)\s*READING\s*COMPREHENSION[^\n]*\n',
            r'(?:^|\n)\s*Reading\s*[Cc]omprehension[^\n]*\n',
        ]),
        ('discussion', [
            # Norwegian
            r'(?:^|\n)\s*[a-z]\)\s*DISKUSJON[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Diskusjon[^\n]*\n',
            r'(?:^|\n)\s*DISKUSJON[^\n]*\n',
            r'(?:^|\n)\s*Diskusjon[^\n]*\n',
            # English
            r'(?:^|\n)\s*[a-z]\)\s*DISCUSSION[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Discussion[^\n]*\n',
            r'(?:^|\n)\s*DISCUSSION[^\n]*\n',
            r'(?:^|\n)\s*Discussion[^\n]*\n',
        ]),
        ('cultural', [
            # Norwegian
            r'(?:^|\n)\s*[a-z]\)\s*KULTURBLIKK[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Kulturblikk[^\n]*\n',
            r'(?:^|\n)\s*KULTURBLIKK[^\n]*\n',
            r'(?:^|\n)\s*Kulturblikk[^\n]*\n',
            r'(?:^|\n)\s*KULTURSAMMENLIGNING[^\n]*\n',
            # English
            r'(?:^|\n)\s*[a-z]\)\s*CULTURAL\s*PERSPECTIVE[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Cultural\s*[Pp]erspective[^\n]*\n',
            r'(?:^|\n)\s*CULTURAL\s*PERSPECTIVE[^\n]*\n',
            r'(?:^|\n)\s*Cultural\s*[Pp]erspective[^\n]*\n',
        ]),
        # Advanced modules
        ('role_play', [
            # Norwegian
            r'(?:^|\n)\s*[a-z]\)\s*ROLLESPILL[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Rollespill[^\n]*\n',
            r'(?:^|\n)\s*ROLLESPILL[^\n]*\n',
            r'(?:^|\n)\s*Rollespill[^\n]*\n',
            # English
            r'(?:^|\n)\s*[a-z]\)\s*ROLE\s*PLAY[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Role\s*[Pp]lay[^\n]*\n',
            r'(?:^|\n)\s*ROLE\s*PLAY[^\n]*\n',
            r'(?:^|\n)\s*Role\s*[Pp]lay[^\n]*\n',
        ]),
        ('image_description', [
            # Norwegian
            r'(?:^|\n)\s*[a-z]\)\s*BILDEBESKRIVELSE[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Bildebeskrivelse[^\n]*\n',
            r'(?:^|\n)\s*BILDEBESKRIVELSE[^\n]*\n',
            r'(?:^|\n)\s*Bildebeskrivelse[^\n]*\n',
            # English
            r'(?:^|\n)\s*[a-z]\)\s*IMAGE\s*DESCRIPTION[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Image\s*[Dd]escription[^\n]*\n',
            r'(?:^|\n)\s*IMAGE\s*DESCRIPTION[^\n]*\n',
            r'(?:^|\n)\s*Image\s*[Dd]escription[^\n]*\n',
        ]),
        ('writing_frame', [
            # Norwegian
            r'(?:^|\n)\s*[a-z]\)\s*SKRIVERAMME[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Skriveramme[^\n]*\n',
            r'(?:^|\n)\s*SKRIVERAMME[^\n]*\n',
            r'(?:^|\n)\s*Skriveramme[^\n]*\n',
            # English
            r'(?:^|\n)\s*[a-z]\)\s*WRITING\s*FRAME[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Writing\s*[Ff]rame[^\n]*\n',
            r'(?:^|\n)\s*WRITING\s*FRAME[^\n]*\n',
            r'(?:^|\n)\s*Writing\s*[Ff]rame[^\n]*\n',
        ]),
        ('real_case', [
            # Norwegian
            r'(?:^|\n)\s*[a-z]\)\s*VIRKELIG\s*CASE[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Virkelig\s*case[^\n]*\n',
            r'(?:^|\n)\s*VIRKELIG\s*CASE[^\n]*\n',
            r'(?:^|\n)\s*Virkelig\s*case[^\n]*\n',
            # English
            r'(?:^|\n)\s*[a-z]\)\s*REAL\s*CASE[^\n]*\n',
            r'(?:^|\n)\s*[a-z]\)\s*Real\s*[Cc]ase[^\n]*\n',
            r'(?:^|\n)\s*REAL\s*CASE[^\n]*\n',
            r'(?:^|\n)\s*Real\s*[Cc]ase[^\n]*\n',
        ]),
    ]
    
    # Find all section start positions
    section_starts = []
    for name, patterns in section_patterns:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                section_starts.append((name, match.start(), match.end()))
                break  # Found this section, move to next
    
    # Sort by position
    section_starts.sort(key=lambda x: x[1])
    
    # Extract content between section markers
    for i, (name, start_pos, header_end) in enumerate(section_starts):
        # Content starts after the header
        content_start = header_end
        
        # Content ends at the next section or end of text
        if i + 1 < len(section_starts):
            content_end = section_starts[i + 1][1]
        else:
            content_end = len(text)
        
        content = text[content_start:content_end].strip()
        
        # Additional cleanup: remove any remaining section headers at the start
        content = re.sub(r'^[a-d]\)\s*', '', content)
        # Remove both Norwegian and English section headers
        content = re.sub(r'^(?:VIKTIGE\s*BEGREPER|Viktige\s*begreper|KEY\s*VOCABULARY|Key\s*[Vv]ocabulary|LESEFORSTÅELSE|Leseforståelse|READING\s*COMPREHENSION|Reading\s*[Cc]omprehension|DISKUSJON|Diskusjon|DISCUSSION|Discussion|KULTURBLIKK|Kulturblikk|CULTURAL\s*PERSPECTIVE|Cultural\s*[Pp]erspective)[^\n]*\n*', '', content, flags=re.IGNORECASE)
        
        if content.strip() and not sections[name]:
            sections[name] = content.strip()
            
    # Fallback: if no sections found, treat everything as vocabulary
    if not any([sections["vocabulary"], sections["comprehension"], sections["discussion"]]):
        sections["vocabulary"] = text
    
    return sections


def create_lesson_pdf(
    content_text: str,
    worksheet_text: str,
    topic: str,
    level: str,
    subject: str = "Norsk",
    image_path: Optional[str] = None,
    language_exercises: Optional[dict] = None,
    options: dict = None,
    teacher_key_content: str = "",
    series_header: str = "",
    accessibility: Optional[dict] = None,
) -> bytes:
    """
    Create a PDF lesson plan from the AI-generated content.
    
    Args:
        content_text: The main educational text from the Content Creator agent
        worksheet_text: The worksheet content from the Pedagogical Developer agent
        topic: The lesson topic
        level: CEFR level (A1, A2, B1, B2)
        subject: Subject area (e.g., "Norsk", "Engelsk") - affects output language
        image_path: Optional path to a local image file (already processed/optimized)
        language_exercises: Optional dict with grammar, vocabulary, syntax tasks
        options: Dictionary of modular options
    
    Returns:
        Binary PDF data
    """
    # Parse the worksheet into sections
    sections = parse_worksheet_content(worksheet_text)
    
    # Determine image root directory and filename for Typst
    image_root = None
    image_filename = None
    full_image_path = None
    if image_path and os.path.exists(image_path):
        # Validate the image file is readable and not empty
        try:
            file_size = os.path.getsize(image_path)
            if file_size > 0:
                image_root = os.path.dirname(image_path)
                # Sanitize filename - only allow safe characters
                raw_filename = os.path.basename(image_path)
                image_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', raw_filename)
                full_image_path = image_path
            else:
                print(f"WARNING: Image file is empty: {image_path}")
        except OSError as e:
            print(f"WARNING: Could not read image file: {e}")
    
    # Create the Typst document (with or without image)
    typst_doc = create_typst_template(
        topic=topic,
        level=level,
        subject=subject,
        main_text=content_text,
        vocabulary=sections["vocabulary"],
        comprehension=sections["comprehension"],
        discussion=sections["discussion"],
        cultural=sections["cultural"],
        role_play=sections["role_play"],
        image_description=sections["image_description"],
        writing_frame=sections["writing_frame"],
        real_case=sections["real_case"],
        teacher_key=sections["teacher_key"],
        teacher_key_content=teacher_key_content,
        series_header=series_header,
        accessibility=accessibility,
        image_path=image_filename,  # Just the filename, not full path
        language_exercises=language_exercises,
        options=options
    )
    
    # Compile to PDF using typst CLI
    pdf_bytes = compile_typst(typst_doc, image_path=full_image_path)
    
    return pdf_bytes


def create_lesson_pdf_simple(
    full_content: str,
    topic: str,
    level: str,
    image_path: Optional[str] = None
) -> bytes:
    """
    Simplified version that takes the full AI output as a single text block.
    
    Args:
        full_content: Complete lesson content (text + worksheet combined)
        topic: The lesson topic
        level: CEFR level
        image_path: Optional path to a local image file
    
    Returns:
        Binary PDF data
    """
    # Use the robust sanitizer for content
    safe_topic = sanitize_for_typst(topic)
    safe_content = sanitize_for_typst(full_content)
    
    # Determine image root directory and filename for Typst
    image_root = None
    image_filename = None
    if image_path and os.path.exists(image_path):
        image_root = os.path.dirname(image_path)
        image_filename = os.path.basename(image_path)
    
    def build_doc(img_filename: Optional[str] = None) -> str:
        # Build image section if provided
        if img_filename:
            image_section = f'''
#align(center)[
  #image("{img_filename}", width: 80%)
  #v(0.3em)
  #text(size: 9pt, fill: gray)[Foto: Wikimedia Commons]
]
#v(1em)
'''
        else:
            image_section = ""
        
        return f'''#set document(title: "Læringsark: {safe_topic}")
#set page(paper: "a4", margin: 2cm)
#set text(font: "Noto Sans", size: 11pt, lang: "nb")
#set par(justify: true, leading: 0.8em)

#let primary = rgb("#1e40af")
#let box-bg = rgb("#f1f5f9")
#let line-color = rgb("#cbd5e1")

#align(center)[
  #block(fill: primary, inset: 1.2em, radius: 4pt, width: 100%)[
    #text(fill: white, size: 18pt, weight: "bold")[Læringsark: {safe_topic}]
    #v(0.3em)
    #text(fill: rgb("#bfdbfe"), size: 12pt)[Nivå {level}]
  ]
]

#v(1em)

{image_section}

{safe_content}

#v(2em)

#text(size: 10pt, fill: gray)[Skriv dine svar her:]

#for i in range(8) {{
  v(0.8em)
  line(length: 100%, stroke: 0.5pt + line-color)
}}

#v(2em)
#align(center)[
  #text(size: 9pt, fill: gray)[Generert av Scriptorium | Nivå {level}]
]
'''
    
    typst_doc = build_doc(img_filename=image_filename)
    
    # Compile to PDF using typst CLI
    full_image_path = None
    if image_filename and image_root:
        full_image_path = os.path.join(image_root, image_filename)
    
    pdf_bytes = compile_typst(typst_doc, image_path=full_image_path)
    
    return pdf_bytes


# For testing purposes
if __name__ == "__main__":
    # Sample content for testing
    sample_text = """Norge er et land i Nord-Europa. Det er et langt land med mange fjorder og fjell. 
    Cirka 5,5 millioner mennesker bor i Norge. Oslo er hovedstaden.
    
    Nordmenn er ofte glad i naturen. Mange liker å gå på tur i skogen eller i fjellet.
    Om vinteren kan man gå på ski. Om sommeren kan man bade i sjøen."""
    
    sample_worksheet = """a) VIKTIGE BEGREPER
    
    Fjord: En lang, smal havbukt mellom høye fjell.
    Hovedstad: Den viktigste byen i et land, der regjeringen er.
    Natur: Alt som ikke er laget av mennesker, som trær, fjell og dyr.
    
    b) LESEFORSTÅELSE
    
    1. Hvor mange mennesker bor i Norge?
    a) 3,5 millioner
    b) 5,5 millioner *
    c) 7,5 millioner
    
    2. Hva er hovedstaden i Norge?
    a) Bergen
    b) Trondheim
    c) Oslo *
    
    3. Hva liker mange nordmenn å gjøre?
    a) Gå på tur i naturen *
    b) Se på TV hele dagen
    c) Bo i store byer
    
    c) DISKUSJON
    
    1. Hva liker du å gjøre i naturen? Fortell om en tur du har vært på.
    
    2. Hvordan er naturen i ditt hjemland? Er den lik eller ulik naturen i Norge?"""
    
    # Test with a sample image URL
    sample_image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Norway_-_National_Day.jpg/800px-Norway_-_National_Day.jpg"
    
    # Generate test PDF without image
    print("Testing PDF generation without image...")
    pdf_data = create_lesson_pdf(
        content_text=sample_text,
        worksheet_text=sample_worksheet,
        topic="Norge - landet vårt",
        level="A2",
        image_path=None
    )
    
    with open("test_lesson_no_image.pdf", "wb") as f:
        f.write(pdf_data)
    print(f"✓ PDF without image created ({len(pdf_data)} bytes)")
    
    # Generate test PDF with image using ImageProcessor
    print("\nTesting PDF generation with image...")
    from media_manager import image_processor
    
    processed_image_path = image_processor.process_image(sample_image_url)
    
    if processed_image_path:
        print(f"  Image processed: {processed_image_path}")
        pdf_data_with_image = create_lesson_pdf(
            content_text=sample_text,
            worksheet_text=sample_worksheet,
            topic="Norge - landet vårt",
            level="A2",
            image_path=processed_image_path
        )
        
        with open("test_lesson_with_image.pdf", "wb") as f:
            f.write(pdf_data_with_image)
        print(f"✓ PDF with image created ({len(pdf_data_with_image)} bytes)")
        
        # Cleanup the processed image
        image_processor.cleanup_image(processed_image_path)
        print("  Temporary image cleaned up")
    else:
        print("✗ Image processing failed, skipping image test")
    
    print("\nTest files saved:")
    print("  - test_lesson_no_image.pdf")
    print("  - test_lesson_with_image.pdf (if image processing succeeded)")
