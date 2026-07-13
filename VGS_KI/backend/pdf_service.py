import re
import os
import tempfile
import subprocess
import shutil
import requests
from typing import Optional
from contextlib import contextmanager


# Directory with vendored fonts (Source Sans 3) passed to typst --font-path,
# and the Typst template library copied next to every compiled document.
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(_BACKEND_DIR, "fonts")
TEMPLATES_DIR = os.path.join(_BACKEND_DIR, "templates")


def compile_typst(source: str, image_path: Optional[str] = None) -> bytes:
    """
    Compile Typst source to PDF using the CLI.
    
    Uses subprocess to call the system typst executable, which is more
    reliable on Windows than the Python library.
    
    Args:
        source: Typst source code as a string
        image_path: Optional path to an image file to include
        
    Returns:
        PDF bytes
        
    Raises:
        RuntimeError: If compilation fails
    """
    # Find typst executable
    typst_exe = shutil.which("typst")
    if not typst_exe:
        raise RuntimeError("Typst executable not found. Please install Typst: https://typst.app/")
    
    # Create temp directory for source and output
    temp_dir = tempfile.mkdtemp(prefix="fov_typst_")
    source_path = os.path.join(temp_dir, "document.typ")
    output_path = os.path.join(temp_dir, "output.pdf")
    
    try:
        # If there's an image, copy it to the temp directory
        if image_path and os.path.exists(image_path):
            image_filename = os.path.basename(image_path)
            temp_image_path = os.path.join(temp_dir, image_filename)
            shutil.copy2(image_path, temp_image_path)

        # Copy the Typst template library so documents can `#import "laeringsark.typ"`
        if os.path.isdir(TEMPLATES_DIR):
            for fname in os.listdir(TEMPLATES_DIR):
                if fname.endswith(".typ"):
                    shutil.copy2(os.path.join(TEMPLATES_DIR, fname),
                                 os.path.join(temp_dir, fname))

        # Write source file
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(source)

        # Run typst compile (with vendored fonts when available)
        cmd = [typst_exe, "compile"]
        if os.path.isdir(FONTS_DIR):
            cmd += ["--font-path", FONTS_DIR]
        cmd += [source_path, output_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=temp_dir  # Set working directory to temp dir for image access
        )
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise RuntimeError(f"Typst compilation failed: {error_msg}")
        
        # Read the PDF
        if not os.path.exists(output_path):
            raise RuntimeError("Typst did not produce output file")
            
        with open(output_path, "rb") as f:
            pdf_data = f.read()
        
        return pdf_data
        
    finally:
        # Cleanup temp directory
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Ignore cleanup errors


def clean_ai_artifacts(text: str) -> str:
    """
    Remove AI thinking/reasoning artifacts from generated text.
    
    The AI sometimes includes internal reasoning or prompt instructions
    in its output. This function removes those artifacts.
    """
    if not text:
        return ""
    
    # Remove common intro phrases from agents
    text = re.sub(r'^(Her er|Jeg har laget|Her kommer)[^.:\n]*[:\n]', '', text, flags=re.IGNORECASE)
    
    # Remove AI "thinking out loud" patterns
    # Pattern: "Wait, I need to..." or "Let me think..." etc.
    text = re.sub(r'Wait,?\s+I\s+need\s+to[^.]*\.', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Let me\s+(think|check|verify|make sure)[^.]*\.', '', text, flags=re.IGNORECASE)
    text = re.sub(r'I (need|should|must) to[^.]*\.', '', text, flags=re.IGNORECASE)
    
    # Remove raw prompt/tool instructions that leak through.
    # IMPORTANT: «...» is the standard Norwegian quotation mark and is used for
    # legitimate quotes (incl. the primary-source block), so only strip «...»
    # segments that clearly look like leaked tool/prompt instructions — never all.
    text = re.sub(
        r'«[^»]*\b(?:you only have access|action input|tool|final answer|i should use|the following tools)\b[^»]*»',
        '', text, flags=re.IGNORECASE,
    )
    text = re.sub(r'Thought:\s*[^\n]*\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Action:\s*[^\n]*\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Action Input:\s*[^\n]*\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Observation:\s*[^\n]*\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Final Answer:\s*', '', text, flags=re.IGNORECASE)
    
    # Remove "I followed the exact prompt requirements" type sentences
    text = re.sub(r'I\s+followed\s+the\s+exact\s+prompt[^.]*\.', '', text, flags=re.IGNORECASE)
    
    # NOTE: Markdown headings (#, ##, ###) are intentionally NOT stripped here.
    # They are converted to real Typst headings later by
    # convert_markdown_headings_to_typst(), which gives the fagtekst proper
    # subheadings. Stripping them here previously merged headings into paragraphs.
    
    # Remove standalone underscores or dashes on their own lines
    text = re.sub(r'^\s*[_\-]{1,3}\s*$', '', text, flags=re.MULTILINE)
    
    # Remove horizontal rules (---, ___, ***)
    text = re.sub(r'^[\-_\*]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    # Clean up multiple spaces/newlines left behind
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    
    return text.strip()


def clean_section_header(text: str) -> str:
    """
    Remove duplicate/internal headers and Bloom's taxonomy labels from section content.
    """
    if not text:
        return ""
    
    # Split into lines
    lines = text.split('\n')
    cleaned_lines = []
    
    # Headers to remove entirely (Norwegian and English)
    header_keywords = [
        # Norwegian
        'LESEFORSTÅELSE', 'Leseforståelse',
        'VIKTIGE BEGREPER', 'Viktige begreper',
        'DISKUSJON', 'Diskusjon',
        'KULTURBLIKK', 'Kulturblikk',
        'OPPGAVER', 'Oppgaver',
        'BEGREPER', 'Begreper',
        'ORDLISTE', 'Ordliste',
        # English
        'READING COMPREHENSION', 'Reading Comprehension',
        'KEY VOCABULARY', 'Key Vocabulary',
        'DISCUSSION', 'Discussion',
        'CULTURAL PERSPECTIVE', 'Cultural Perspective',
        'ROLE PLAY', 'Role Play',
        'IMAGE DESCRIPTION', 'Image Description',
        'WRITING FRAME', 'Writing Frame',
        'REAL CASE', 'Real Case',
    ]
    
    # Bloom's taxonomy words (English equivalents too)
    bloom_words = [
        'Huske', 'Forstå', 'Anvende', 'Analysere', 'Vurdere', 'Skape',
        'Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create'
    ]
    
    # Instruction fragments (Norwegian and English)
    instruction_fragments = [
        # Norwegian
        'Velg riktig svar',
        'basert på teksten',
        'Snakk sammen med',
        'Svar på spørsmålene',
        'Her er 4 spørsmål',
        'Her er fire spørsmål',
        'tilpasset voksne deltakere',
        # English
        'Choose the correct answer',
        'based on the text',
        'Talk to a partner',
        'Answer the questions',
        'Here are 4 questions',
        'Here are four questions',
        'adapted for adult learners',
    ]
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            cleaned_lines.append('')
            continue
            
        should_remove = False
        
        # Exact match for header keywords
        if line_stripped.upper() in [k.upper() for k in header_keywords]:
            should_remove = True
            
        # Match Bloom's taxonomy in parentheses
        if not should_remove:
            for bloom in bloom_words:
                if re.search(rf'\([^)]*{bloom}[^)]*\)', line_stripped, re.IGNORECASE):
                    should_remove = True
                    break
                    
        # Match header keywords + short line
        if not should_remove:
            for keyword in header_keywords:
                if keyword.upper() in line_stripped.upper() and len(line_stripped) < 100:
                    should_remove = True
                    break
                    
        # Match instruction fragments
        if not should_remove:
            for fragment in instruction_fragments:
                if fragment.lower() in line_stripped.lower() and len(line_stripped) < 150:
                    should_remove = True
                    break
                    
        if not should_remove:
            cleaned_lines.append(line)
            
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def clean_meta_instructions(text: str) -> str:
    """
    Remove meta-instructions that describe the task.
    """
    if not text:
        return ""
    
    # More specific patterns for meta-text
    meta_patterns = [
        r'^Her er \d+ spørsmål[^.:\n]*[:\n]*',
        r'^Her er fire spørsmål[^.:\n]*[:\n]*',
        r'^Disse (?:spørsmålene|oppgavene)[^.:\n]*[:\n]*',
        r'^Følgende oppgaver[^.:\n]*[:\n]*',
        r'^Under finner du[^.:\n]*[:\n]*',
        r'^Nedenfor er[^.:\n]*[:\n]*',
        r'^Dette er oppgaver[^.:\n]*[:\n]*',
        r'^Denne oppgaven[^.:\n]*[:\n]*',
    ]
    
    for pattern in meta_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    return text.strip()


def remove_answer_markers(text: str) -> str:
    """
    Remove trailing asterisks from answers.
    """
    if not text:
        return ""
    
    # Process line by line
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Match asterisk at end of line, or right before/after period
        line = re.sub(r'\s*\*+\s*$', '', line)
        line = re.sub(r'\.\s*\*+\s*$', '.', line)
        line = re.sub(r'\*+\.\s*$', '.', line)
        line = re.sub(r'\s*\(\s*\*+\s*\)\s*$', '', line)
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)


def convert_markdown_lists_to_typst(text: str) -> str:
    """
    Convert * to - for lists.
    """
    if not text:
        return ""
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # If line starts with * (ignoring whitespace), convert to -
        # But not if it's bold like **text**
        if re.match(r'^\s*\*\s+', line) and not line.strip().startswith('**'):
            line = re.sub(r'^\s*\*\s+', '- ', line)
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)


def _escape_typst_brackets(content: str) -> str:
    """Escape square brackets inside generated Typst markup content
    (#strong[...], #emph[...], #heading[...]) so that user/AI text containing
    [ or ] can never break out of the enclosing content block.

    Idempotent: already-escaped brackets are left untouched, so nested
    conversions (e.g. emph inside strong) don't double-escape.
    """
    content = re.sub(r'(?<!\\)\[', r'\\[', content)
    content = re.sub(r'(?<!\\)\]', r'\\]', content)
    return content


def convert_markdown_headings_to_typst(text: str) -> str:
    """
    Convert Markdown headings (###, ##) to Typst headings.
    
    Args:
        text: Text with potential Markdown headings
        
    Returns:
        Text with Typst heading syntax
    """
    if not text:
        return ""
    
    lines = text.split('\n')
    converted_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Match #### (or deeper) heading → level 4
        if re.match(r'#{4,}\s', stripped):
            heading_text = _escape_typst_brackets(stripped.lstrip('#').strip())
            converted_lines.append(f'\n#heading(level: 4)[{heading_text}]')
            continue
        
        # Match ### heading (level 3)
        if stripped.startswith('### '):
            heading_text = _escape_typst_brackets(stripped[4:].strip())
            # Use Typst heading with keep-with-next to prevent orphans
            converted_lines.append(f'\n#heading(level: 3)[{heading_text}]')
            continue
        
        # Match ## heading (level 2)
        if stripped.startswith('## '):
            heading_text = _escape_typst_brackets(stripped[3:].strip())
            converted_lines.append(f'\n#heading(level: 2)[{heading_text}]')
            continue
        
        # Match # heading (level 1) - but not ## or ###
        if stripped.startswith('# ') and not stripped.startswith('## '):
            heading_text = _escape_typst_brackets(stripped[2:].strip())
            converted_lines.append(f'\n#heading(level: 1)[{heading_text}]')
            continue
        
        converted_lines.append(line)
    
    return '\n'.join(converted_lines)


def sanitize_for_typst(text: str, is_section_content: bool = False) -> str:
    """
    Sanitize text for safe inclusion in Typst documents.
    
    Handles:
    - Removing AI reasoning artifacts
    - Escaping special Typst characters (#, $, @, <, >, etc.)
    - Converting Markdown bold/italic to Typst syntax
    - Converting Markdown headings to Typst headings
    - Converting Markdown lists to Typst lists
    - Removing problematic Unicode characters
    - Preserving Norwegian characters (æ, ø, å)
    
    Args:
        text: Raw text that may contain special characters
        is_section_content: If True, also cleans section headers and meta-instructions
        
    Returns:
        Sanitized text safe for Typst compilation
    """
    if not text:
        return ""
    
    # Step 0: Remove AI artifacts first
    text = clean_ai_artifacts(text)
    
    # Step 0.5: If this is section content, clean headers and meta-instructions
    if is_section_content:
        text = clean_section_header(text)
        text = clean_meta_instructions(text)
    
    # Step 0.7: Convert Markdown headings to Typst BEFORE escaping
    text = convert_markdown_headings_to_typst(text)
    
    # Step 1: Convert Markdown lists to Typst format BEFORE other processing
    text = convert_markdown_lists_to_typst(text)
    
    # Step 2: Convert Markdown formatting to Typst before escaping.
    # Brackets inside the content are escaped so quoted text like
    # "*«X [førte til] Y»*" cannot break out of the #emph[...] block.
    def _strong(m: re.Match) -> str:
        return f"#strong[{_escape_typst_brackets(m.group(1))}]"

    def _emph(m: re.Match) -> str:
        return f"#emph[{_escape_typst_brackets(m.group(1))}]"

    # Bold: **text** or __text__ → #strong[text]
    text = re.sub(r'\*\*(.+?)\*\*', _strong, text)
    text = re.sub(r'__(.+?)__', _strong, text)
    
    # Italic: *text* or _text_ → #emph[text]
    # Be careful not to match already converted strong tags or list items
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', _emph, text)
    text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', _emph, text)
    
    # Step 3: Temporarily protect Typst commands we just created.
    # Process inside-out so nested patterns work correctly:
    #   #emph[...] first, then #strong[...] which may wrap emph placeholders.
    # Placeholders contain no ']' so the outer pass sees clean content.
    protected_patterns = []

    def protect_pattern(match):
        idx = len(protected_patterns)
        protected_patterns.append(match.group(0))
        return f"TYPSTPROTECT{idx}ENDPROTECT"

    # Content may contain escaped brackets (\[ and \]), so the patterns accept
    # any backslash escape (\\.) in addition to plain non-bracket characters.
    # Inner patterns first (emph may appear inside strong)
    text = re.sub(r'#emph\[((?:\\.|[^\]\\])*)\]', protect_pattern, text)
    # Outer patterns second (inner emph already replaced → no ']' in content)
    text = re.sub(r'#strong\[((?:\\.|[^\]\\])*)\]', protect_pattern, text)
    # Headings
    text = re.sub(r'#heading\[((?:\\.|[^\]\\])*)\]', protect_pattern, text)
    text = re.sub(r'#heading\(level:\s*\d+\)\[(?:\\.|[^\]\\])*\]', protect_pattern, text)
    
    # Step 4: Escape special Typst characters
    # Order matters: escape backslash first
    escape_chars = [
        ('\\', '\\\\'),
        ('#', '\\#'),
        ('$', '\\$'),
        ('@', '\\@'),
        ('<', '\\<'),
        ('>', '\\>'),
        ('{', '\\{'),
        ('}', '\\}'),
        ('[', '\\['),
        (']', '\\]'),
        ('`', '\\`'),
        ('*', '\\*'),  # Escape asterisks (used by AI to mark correct answers)
        ('_', '\\_'),  # Escape underscores
    ]
    
    for char, escaped in escape_chars:
        text = text.replace(char, escaped)
    
    # Step 5: Restore protected Typst commands — reverse order so that outer
    # patterns (which reference inner placeholders) are expanded first, then
    # the inner placeholder tokens inside them get resolved.
    for idx in range(len(protected_patterns) - 1, -1, -1):
        text = text.replace(f"TYPSTPROTECT{idx}ENDPROTECT", protected_patterns[idx])
    
    # Step 6: Handle special cases
    # Remove zero-width characters that might cause issues
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
    
    # Normalize line breaks
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Convert multiple newlines to paragraph breaks
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text


def sanitize_comprehension_for_typst(text: str) -> str:
    """
    Sanitize comprehension questions, removing answer markers.
    
    This is used specifically for multiple choice questions where
    correct answers are marked with * that should not appear in student PDFs.
    """
    if not text:
        return ""
    
    # First remove answer markers
    text = remove_answer_markers(text)
    
    # Then apply standard sanitization with section cleaning
    return sanitize_for_typst(text, is_section_content=True)


def format_mcq_content(text: str) -> str:
    """
    Format multiple choice question content to ensure proper layout.
    
    Ensures:
    - Questions are numbered
    - Options a), b), c) are properly formatted
    - Each question is separated properly
    """
    if not text:
        return ""
    
    lines = text.split('\n')
    formatted_lines = []
    in_question = False
    question_count = 0
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines but preserve some spacing
        if not stripped:
            if formatted_lines and formatted_lines[-1] != "#v(0.5em)":
                formatted_lines.append("#v(0.5em)")
            continue
        
        # Detect question start (numbered: 1., 2., etc.)
        question_match = re.match(r'^(\d+)[.\)]\s*(.+)$', stripped)
        if question_match:
            question_count += 1
            if question_count > 1:
                formatted_lines.append("#v(0.8em)")  # Space between questions
            formatted_lines.append(f"#strong[{question_match.group(1)}.] {question_match.group(2)}")
            in_question = True
            continue
        
        # Detect option (a), b), c) or a., b., c.)
        option_match = re.match(r'^([a-d])[.\)]\s*(.+)$', stripped, re.IGNORECASE)
        if option_match:
            letter = option_match.group(1).lower()
            option_text = option_match.group(2)
            formatted_lines.append(f"#h(1em) {letter}) {option_text}")
            continue
        
        # Regular content
        formatted_lines.append(stripped)
    
    return '\n'.join(formatted_lines)


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
            headers={"User-Agent": "FOV-Teacher-Assistant/1.0"},
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
    
    Uses Typst box elements to keep sentence parts together and prevent line breaks
    in the middle of fill-in-the-blank sections.
    
    Returns Typst content for cloze exercises.
    """
    if not items:
        return ""
    
    # Define Typst underline element for blanks - inline box that won't break
    BLANK_ELEMENT = "#box(baseline: 0pt)[#box(width: 5em, stroke: (bottom: 1pt + gray))[#h(5em)]]"
    # Use a placeholder that won't be escaped
    PLACEHOLDER = "CLOZEBLANKPLACEHOLDER"
    
    lines = []
    for i, item in enumerate(items, 1):
        text = str(item).strip()
        if not text:
            continue
            
        # First, replace blank markers with placeholder
        # Handle various blank formats: [___], (___), ___, [blank]
        text = re.sub(r'\[___+\]|\[blank\]|\(___+\)|\b___+\b', PLACEHOLDER, text)
        
        # Sanitize the text (this escapes special characters)
        text = sanitize_for_typst(text)
        
        # Now replace placeholder with actual Typst command (after sanitization)
        text = text.replace(PLACEHOLDER, BLANK_ELEMENT)
        
        # Wrap each sentence in a box to keep it together and prevent bad line breaks
        # Use #par to ensure proper paragraph handling
        lines.append(f"#block(breakable: false, width: 100%, inset: (y: 0.3em))[\n  {i}. {text}\n]")
    
    return "\n".join(lines)


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
  inset: 8pt,
  align: horizon,
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
        if not item_str:
            continue
        
        pair = None
        # Try various separators
        for sep in [': ', ' - ', ' = ', ' → ', ' -> ']:
            if sep in item_str:
                parts = item_str.split(sep, 1)
                if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                    pair = (parts[0].strip(), parts[1].strip())
                    break
        
        if pair:
            # Strip leading A., B. or 1., 2. if present
            term = re.sub(r'^[A-Z1-9][.)]\s*', '', pair[0])
            defn = re.sub(r'^[A-Z1-9][.)]\s*', '', pair[1])
            if term and defn:  # Only add if both are non-empty
                terms.append(term)
                definitions.append(defn)
        else:
            # Fallback for single items - only add non-empty
            cleaned = re.sub(r'^[A-Z1-9][.)]\s*', '', item_str)
            if cleaned:
                terms.append(cleaned)
            
    # If we don't have pairs, maybe they are alternating?
    # (Not ideal, but happens)
    if not definitions and len(terms) >= 4:
        mid = len(terms) // 2
        definitions = terms[mid:]
        terms = terms[:mid]
    
    # Ensure we have equal numbers of terms and definitions
    min_len = min(len(terms), len(definitions)) if definitions else 0
    if min_len > 0:
        terms = terms[:min_len]
        definitions = definitions[:min_len]
    
    if terms and definitions and len(terms) == len(definitions):
        import random
        random.seed(42)
        shuffled_defs = definitions.copy()
        random.shuffle(shuffled_defs)
        
        letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        table_rows = []
        
        for i in range(len(terms)):
            letter = letters[i] if i < len(letters) else str(i+1)
            # Sanitize and wrap in block to prevent text overflow
            safe_term = sanitize_for_typst(terms[i])
            safe_def = sanitize_for_typst(shuffled_defs[i])
            t_cell = f'[{letter}. {safe_term}]'
            d_cell = f'[{i+1}. {safe_def}]'
            table_rows.append(f'  {t_cell}, {d_cell},')
        
        # Number of answer slots
        num_items = len(terms)
        answer_slots = " ".join([f"{i+1}\\_" for i in range(min(num_items, 8))])
        
        # Build complete table string with all rows
        rows_content = chr(10).join(table_rows)
            
        # Wrap entire table in a non-breakable block to prevent floating text
        return f'''#block(breakable: false)[
#table(
  columns: (1fr, 2fr),
  inset: 10pt,
  align: (left, left),
  stroke: 0.5pt + line-color,
  fill: (col, row) => if row == 0 {{ box-bg }} else {{ white }},
  [*{term_header}*], [*{def_header}*],
{rows_content}
)

#v(0.5em)
#text(size: 9pt, fill: gray)[{instruction}]
#h(1em) #text(size: 10pt)[{answer_slots}]
]'''

    # Fallback to simple list - also wrapped in block
    lines = [f"{i+1}. {sanitize_for_typst(str(item))}" for i, item in enumerate(items)]
    return "#block(breakable: false)[\n" + "\n\n".join(lines) + "\n]"


def render_preposition_exercise(items: list) -> str:
    """
    Render preposition fill-in exercises.
    
    Returns Typst content with blanks for prepositions.
    """
    if not items:
        return ""
    
    # Define Typst box element for preposition blanks - standard size for prepositions
    PREP_BLANK = "#box(width: 4em, stroke: (bottom: 1pt + gray))[#h(4em)]"
    # Use a placeholder that won't be escaped
    PLACEHOLDER = "PREPPLACEHOLDER"
    
    lines = []
    for i, item in enumerate(items, 1):
        text = str(item)
        # First, replace preposition markers with placeholder
        text = re.sub(r'\[prep\]|\(prep\)|___+', PLACEHOLDER, text)
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
    
    import random
    
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
    
    # Remove duplicates while preserving some randomness
    unique_words = list(set(all_words))
    random.seed(42)  # Consistent shuffle
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
  inset: 8pt,
  align: horizon,
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
  inset: 8pt,
  align: horizon,
  stroke: 0.5pt + line-color,
  fill: (col, row) => if row == 0 {{ box-bg }} else {{ white }},
  {headers}
  {table_content}
)'''


def sort_tasks_numerically(tasks: list) -> list:
    """
    Sort tasks to ensure they appear in numerical order (1, 2, 3...).
    
    Args:
        tasks: List of task dictionaries or strings
        
    Returns:
        Sorted list of tasks
    """
    if not tasks:
        return tasks
    
    # If tasks are dictionaries, try to sort by any 'order' or 'number' field
    # Otherwise, preserve original order (they should already be in order from the agent)
    return tasks


def format_language_exercises(exercises: dict, options: dict = None, is_english: bool = False) -> str:
    """
    Format language exercises dict into Typst content with specialized renderers.
    
    Includes orphan/widow control to keep section headers with their content.
    
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
    
    # Labels based on language - VGS-appropriate terminology
    labels = {
        "grammar": "Subject Knowledge" if is_english else "Fagkunnskap",
        "vocabulary": "Key Concepts" if is_english else "Sentrale begreper",
        "syntax": "Analysis and Reflection" if is_english else "Analyse og refleksjon",
        "task": "Task" if is_english else "Oppgave",
    }
    
    sections = []
    
    # Grammar tasks (verb conjugation, prepositions, word categories)
    grammar_tasks = sort_tasks_numerically(exercises.get("grammar_tasks", []))
    if grammar_tasks and options.get("grammar_tasks", True):
        grammar_content = []
        
        # Start section with header AND first task together (prevents orphan headings)
        grammar_content.append(f"#block(breakable: false)[")
        grammar_content.append(f"#v(0.5em)")
        grammar_content.append(f"#text(size: 14pt, weight: \"bold\", fill: primary-color)[🎓 {labels['grammar']}]")
        grammar_content.append("#v(0.8em)")
        
        for i, task in enumerate(grammar_tasks, 1):
            if isinstance(task, dict):
                instruction = sanitize_for_typst(task.get("instruction", ""))
                items = task.get("items", [])
                task_type = task.get("type", "").lower()
                
                # First task stays with header, subsequent tasks get their own block
                if i > 1:
                    grammar_content.append("]")  # Close previous block
                    grammar_content.append("#block(breakable: false)[")
                
                grammar_content.append(f"#strong[{labels['task']} {i}]")
                if instruction:
                    grammar_content.append(f"\n{instruction}\n")
                grammar_content.append("#v(0.5em)")
                
                # Use specialized renderer based on task type (Norwegian and English variants)
                if "verb" in task_type or "conjugat" in task_type or "bøy" in task_type or "tense" in task_type:
                    grammar_content.append(render_verb_table(items, is_english))
                elif "prep" in task_type:
                    grammar_content.append(render_preposition_exercise(items))
                elif "ordklasse" in task_type or "sorter" in task_type or "kategori" in task_type or "word_sort" in task_type:
                    # Word sorting/categorization task
                    grammar_content.append(render_word_sorting_exercise(items, is_english))
                elif "word_form" in task_type or "sammensatt" in task_type:
                    # Word formation task
                    grammar_content.append(render_word_formation_exercise(items, is_english))
                else:
                    # Default: simple list
                    for j, item in enumerate(items, 1):
                        grammar_content.append(f"{j}. {sanitize_for_typst(str(item))}")
                
                grammar_content.append("#v(1em)")
            elif isinstance(task, str):
                grammar_content.append(f"- {sanitize_for_typst(task)}")
        
        grammar_content.append("]")  # Close final block
        
        if grammar_content:
            sections.append("\n".join(grammar_content))
    
    # Vocabulary tasks (matching, fill-in-blank, spelling, cloze)
    vocab_tasks = sort_tasks_numerically(exercises.get("vocabulary_tasks", []))
    if vocab_tasks and options.get("vocabulary_tasks", True):
        vocab_content = []
        
        # Start section with header AND first task together (prevents orphan headings)
        vocab_content.append(f"#block(breakable: false)[")
        vocab_content.append(f"#v(0.5em)")
        vocab_content.append(f"#text(size: 14pt, weight: \"bold\", fill: primary-color)[🔑 {labels['vocabulary']}]")
        vocab_content.append("#v(0.8em)")
        
        for i, task in enumerate(vocab_tasks, 1):
            if isinstance(task, dict):
                instruction = sanitize_for_typst(task.get("instruction", ""))
                items = task.get("items", [])
                task_type = task.get("type", "").lower()
                
                # First task stays with header, subsequent tasks get their own block
                if i > 1:
                    vocab_content.append("]")  # Close previous block
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
                
                vocab_content.append("#v(1em)")
            elif isinstance(task, str):
                vocab_content.append(f"- {sanitize_for_typst(task)}")
        
        vocab_content.append("]")  # Close final block
        
        if vocab_content:
            sections.append("\n".join(vocab_content))
    
    # Syntax tasks (scrambled sentences, word order)
    # Syntax tasks are usually part of grammar or overall language training
    syntax_tasks = sort_tasks_numerically(exercises.get("syntax_tasks", []))
    if syntax_tasks and options.get("grammar_tasks", True):
        syntax_content = []
        
        # Start section with header AND first task together (prevents orphan headings)
        syntax_content.append(f"#block(breakable: false)[")
        syntax_content.append(f"#v(0.5em)")
        syntax_content.append(f"#text(size: 14pt, weight: \"bold\", fill: primary-color)[🔍 {labels['syntax']}]")
        syntax_content.append("#v(0.8em)")
        
        for i, task in enumerate(syntax_tasks, 1):
            if isinstance(task, dict):
                instruction = sanitize_for_typst(task.get("instruction", ""))
                items = task.get("items", [])
                task_type = task.get("type", "").lower()
                
                # First task stays with header, subsequent tasks get their own block
                if i > 1:
                    syntax_content.append("]")  # Close previous block
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
                
                syntax_content.append("#v(1em)")
            elif isinstance(task, str):
                syntax_content.append(f"- {sanitize_for_typst(task)}")
        
        syntax_content.append("]")  # Close final block
        
        if syntax_content:
            sections.append("\n".join(syntax_content))
    
    return "\n\n".join(sections)


def create_typst_template(
    topic: str,
    level: str,
    subject: str = "Norsk",
    language_level: Optional[str] = None,
    main_text: str = "",
    learning_goals: str = "",
    pre_reading: str = "",
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
    options: dict = None,
    source_name: Optional[str] = None,
) -> str:
    """
    Create a Typst document template for the lesson plan.
    
    Args:
        topic: The lesson topic
        level: VGS level (VG1, VG2, VG3, Yrkesfag)
        language_level: Optional language simplification level (B1, B2) for minority language students
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
        "vgs": "Upper Secondary School" if is_english else "Videregående skole",
        "text": "Text" if is_english else "Tekst",
        "vocabulary": "Subject Terminology" if is_english else "Fagbegreper",
        "language_training": "Subject Exercises" if is_english else "Fagoppgaver",
        "comprehension": "Understanding and Analysis" if is_english else "Forståelse og analyse",
        "discussion": "Discussion and Reflection" if is_english else "Drøfting og refleksjon",
        "cultural": "Global Perspective" if is_english else "Samfunnsperspektiv",
        "role_play": "Case Study" if is_english else "Case / Rollespill",
        "image_desc": "Visual Analysis" if is_english else "Visuell analyse",
        "writing_frame": "Academic Writing Frame" if is_english else "Faglig skriveramme",
        "real_case": "Professional Communication" if is_english else "Yrkesfaglig kommunikasjon",
        "teacher_key": "Answer Key" if is_english else "Lærerens Fasit",
        "write_here": "Write your answers here:" if is_english else "Skriv dine svar her:",
        "reflection": "Reflection:" if is_english else "Refleksjon:",
        "practice_dialogue": "Analyze the case:" if is_english else "Analyser casen:",
        "look_at_image": "Analyze the image and answer the questions:" if is_english else "Analyser bildet og svar på spørsmålene:",
        "your_answers": "Your analysis:" if is_english else "Din analyse:",
        "use_starters": "Use the writing frame to structure your answer:" if is_english else "Bruk skriverammen for å strukturere svaret ditt:",
        "your_text": "Your text:" if is_english else "Din tekst:",
        "write_below": "Write here:" if is_english else "Skriv her:",
        "generated_by": "Generated by VGS Lærerassistent | Adapted to" if is_english else "Generert av VGS Lærerassistent | Tilpasset",
        "level_cefr": "VGS curriculum" if is_english else "VGS-læreplanen",
        "photo": "Photo: Wikimedia Commons" if is_english else "Foto: Wikimedia Commons",
        "deep_dive": "DEEP DIVE" if is_english else "FORDYPNING",
        "simplified_language": "Simplified Language" if is_english else "Tilpasset språk",
        "learning_goals": "Learning Goals" if is_english else "Læringsmål",
        "learning_goals_intro": "After this lesson, you should be able to:" if is_english else "Etter denne leksjonen skal du kunne:",
        "pre_reading": "Before You Read" if is_english else "Før du leser",
        "difficulty_legend": "★ Basic   ·   ★★ Intermediate   ·   ★★★ Advanced" if is_english else "★ Grunnleggende   ·   ★★ Middels   ·   ★★★ Avansert",
        }

    # Process the content using the robust sanitizer
    # Main text and topic don't need section cleaning
    safe_topic = sanitize_for_typst(topic)
    safe_level = sanitize_for_typst(level)
    safe_main_text = sanitize_for_typst(main_text)

    # Muted superscript rendering of [K] citation markers: small grey "K"
    # instead of full-size bracket blocks, so the marks stay checkable without
    # being visual noise. The sanitizer escaped them to \[K\].
    _is_english_subj = subject.lower() == "engelsk"
    _k_super = '#super[#text(size: 7pt, fill: rgb("#7d8a88"), weight: "medium")[K]]'
    _has_citations = "[K]" in (main_text or "")
    if _has_citations:
        safe_main_text = safe_main_text.replace(" \\[K\\]", _k_super)
        safe_main_text = safe_main_text.replace("\\[K\\]", _k_super)

    # Inline-citation legend: only shown when the text actually carries [K]
    # markers (which the writer only adds when source material was available).
    if _has_citations:
        if source_name:
            _safe_source = sanitize_for_typst(source_name)
            _cite_text = (
                f"{_k_super} = this statement is based on the source material ({_safe_source}) and can be checked against it."
                if _is_english_subj
                else f"{_k_super} = påstanden bygger på kildematerialet ({_safe_source}) og kan kontrolleres mot det."
            )
        else:
            _cite_text = (
                f"{_k_super} = this statement is based on the source material the teacher provided and can be checked against it."
                if _is_english_subj
                else f"{_k_super} = påstanden bygger på kildematerialet læreren oppga, og kan kontrolleres mot det."
            )
        citation_legend_section = f'''#block(
  width: 100%,
  inset: (x: 0.9em, y: 0.6em),
  radius: 4pt,
  fill: rgb("#f1f6f6"),
  stroke: (left: 2pt + rgb("#3f7d78")),
)[
  #text(size: 8.5pt, fill: rgb("#274f4d"))[{_cite_text}]
]

#v(1em)'''
    else:
        citation_legend_section = ""

    # Trust badge printed on the document itself (not just shown in the app):
    # the PDF is what circulates in staff rooms, so the grounding claim
    # travels with it.
    trust_badge_section = ""
    if source_name and _has_citations:
        _safe_badge_source = sanitize_for_typst(source_name)
        _badge_label = "Source-grounded" if _is_english_subj else "Kildeforankret"
        trust_badge_section = f'''
#v(0.7em)
#box(
  fill: rgb("#e9f2ec"),
  stroke: 1pt + rgb("#3e7d5e"),
  radius: 99pt,
  inset: (x: 10pt, y: 5pt),
)[
  #text(size: 9pt, fill: rgb("#1f5c3f"), weight: "medium")[✓ {_badge_label}: {_safe_badge_source}]
]
'''
    
    # New pedagogical sections
    safe_learning_goals = sanitize_for_typst(learning_goals, is_section_content=True)
    safe_pre_reading = sanitize_for_typst(pre_reading, is_section_content=True)
    
    # Section content gets extra cleaning (headers, meta-instructions removed)
    safe_vocabulary = sanitize_for_typst(vocabulary, is_section_content=True)
    safe_discussion = sanitize_for_typst(discussion, is_section_content=True)
    safe_cultural = sanitize_for_typst(cultural, is_section_content=True)
    
    # Advanced modules
    safe_role_play = sanitize_for_typst(role_play, is_section_content=True)
    safe_image_description = sanitize_for_typst(image_description, is_section_content=True)
    safe_writing_frame = sanitize_for_typst(writing_frame, is_section_content=True)
    safe_real_case = sanitize_for_typst(real_case, is_section_content=True)
    
    # Comprehension needs answer markers removed for student PDF
    safe_comprehension = sanitize_comprehension_for_typst(comprehension)
    
    # Teacher key doesn't need answer markers removed (it's the answer key!)
    safe_teacher_key = sanitize_for_typst(teacher_key, is_section_content=True)
    
    # Format language exercises if provided and requested
    safe_language_exercises = ""
    if language_exercises and (options.get("grammar_tasks", True) or options.get("vocabulary_tasks", True)):
        safe_language_exercises = format_language_exercises(language_exercises, options, is_english)
    
    # Build image section if image path is provided
    # Keep image and caption together to prevent separation across pages
    image_section = ""
    if image_path:
        image_section = f'''
// Featured image from Wikimedia Commons - kept together with caption
#block(breakable: false)[
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
]

#v(1em)
'''
    
    # Deep dive badge - will be integrated into header
    deep_dive_badge = ""
    if options.get("deep_dive", False):
        deep_dive_badge = f'''#box(fill: accent-color, inset: (x: 8pt, y: 4pt), radius: 3pt)[
      #text(fill: white, size: 9pt, weight: "bold")[{labels["deep_dive"]}]
    ]'''

    # Language level badge - will be integrated into header
    language_level_badge = ""
    if language_level and language_level in ["B1", "B2"]:
        language_level_badge = f'''#box(fill: rgb("#7c3aed"), inset: (x: 8pt, y: 4pt), radius: 3pt)[
      #text(fill: white, size: 9pt, weight: "bold")[{labels["simplified_language"]} ({language_level})]
    ]'''
    
    # Build badges row for header (only if there are badges)
    badges_row = ""
    if deep_dive_badge or language_level_badge:
        badges = []
        if deep_dive_badge:
            badges.append(deep_dive_badge)
        if language_level_badge:
            badges.append(language_level_badge)
        badges_row = f'''
    #v(0.4em)
    {" #h(0.5em) ".join(badges)}'''

    # Build language exercises section if provided (placed after Viktige begreper)
    # Wrap heading with first part of content to prevent orphan headings
    language_exercises_section = ""
    if safe_language_exercises:
        language_exercises_section = f'''
// Language exercises section (sticky numbered heading keeps it with content)
#heading(level: 2)[{labels["language_training"]}]

#block(
  width: 100%,
  inset: 1.2em,
  radius: 6pt,
  fill: rgb("#fdf9ee"),
  stroke: 1pt + rgb("#e3d3a3"),
)[
  {safe_language_exercises}
]

#v(1.5em)
'''
    
    # Learning Goals section - always placed before the main text
    learning_goals_section = ""
    if safe_learning_goals:
        learning_goals_section = f'''
// Learning Goals box - prominent placement
#block(breakable: false)[
#block(
  width: 100%,
  fill: rgb("#f1f6f6"),
  inset: 1.2em,
  radius: 6pt,
  stroke: 1pt + rgb("#8fbab6"),
)[
  #text(fill: rgb("#274f4d"), size: 13pt, weight: "bold")[{labels["learning_goals"]}]
  #v(0.5em)
  {safe_learning_goals}
]
]

#v(1em)
'''

    # Pre-Reading section - placed right before the main text
    pre_reading_section = ""
    if safe_pre_reading:
        pre_reading_section = f'''
// Pre-reading activation box
#block(breakable: false)[
#block(
  width: 100%,
  fill: rgb("#fefce8"),
  inset: 1.2em,
  radius: 6pt,
  stroke: 1pt + rgb("#eab308"),
)[
  #text(fill: rgb("#a16207"), size: 13pt, weight: "bold")[{labels["pre_reading"]}]
  #v(0.5em)
  {safe_pre_reading}
  #v(0.5em)
  #line(length: 100%, stroke: 0.5pt + rgb("#eab308"))
  #v(0.3em)
  #text(size: 9pt, fill: rgb("#a16207"), style: "italic")[
    {"Write your thoughts here before reading the text." if is_english else "Skriv tankene dine her før du leser teksten."}
  ]
  #v(2em)
]
]

#v(1em)
'''

    # Difficulty legend for Bloom's taxonomy stars
    difficulty_legend_section = ""
    if safe_comprehension or safe_discussion:
        difficulty_legend_section = f'''
#block(
  width: 100%,
  inset: (x: 1em, y: 0.5em),
  fill: rgb("#f8fafc"),
  radius: 4pt,
  stroke: 0.5pt + rgb("#e2e8f0"),
)[
  #text(size: 9pt, fill: rgb("#64748b"))[{labels["difficulty_legend"]}]
]

#v(0.5em)
'''

    # Vocabulary section
    vocabulary_section = ""
    if options.get("vocabulary_tasks", True) and safe_vocabulary:
        vocabulary_section = f'''
// Vocabulary box (sticky heading keeps it with the box; the box itself may
// break across pages so long term lists don't leave half-empty pages)
#heading(level: 2)[{labels["vocabulary"]}]

#block(
  width: 100%,
  fill: box-bg,
  inset: 1.2em,
  radius: 6pt,
  stroke: 1pt + line-color,
)[
  {safe_vocabulary}
]

#v(1.5em)
'''

    # Comprehension section - format MCQs properly
    comprehension_section = ""
    if options.get("comprehension_tasks", True) and safe_comprehension:
        # Format the comprehension content to ensure proper MCQ layout
        formatted_comprehension = format_mcq_content(safe_comprehension)
        
        comprehension_section = f'''
// Reading comprehension (sticky heading, breakable content to avoid
// near-empty pages when the section is long)
#heading(level: 2)[{labels["comprehension"]}]

#block(
  width: 100%,
  inset: (x: 1em, y: 0.5em),
)[
  {formatted_comprehension}
]

#v(1.5em)
'''

    # Discussion section
    discussion_section = ""
    if options.get("discussion_tasks", True) and safe_discussion:
        discussion_section = f'''
// Discussion questions with writing lines
#heading(level: 2)[{labels["discussion"]}]

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

#v(1.5em)
'''

    # Cultural section
    cultural_section = ""
    if safe_cultural:
        cultural_section = f'''
// Cultural comparison section
#heading(level: 2)[{labels["cultural"]}]

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
#heading(level: 2)[{labels["role_play"]}]

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
#heading(level: 2)[{labels["image_desc"]}]

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
#heading(level: 2)[{labels["writing_frame"]}]

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
#heading(level: 2)[{labels["real_case"]}]

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
      {safe_topic} | {labels["level"]} {safe_level}
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

    # Header
    header_title = f"{labels['worksheet']}: {safe_topic}"
    header_subtitle = f"{labels['level']} {safe_level} #h(0.5em) | #h(0.5em) {labels['vgs']}"
    
    # Build the Typst document
    typst_doc = f'''// VGS Lærerassistent - Lesson Plan
// UTF-8 encoding for Norwegian characters (æ, ø, å)

// Color definitions (must be before page setup for header/footer use)
// Brand palette: muted petrol/teal, matching the app UI ("accent" in Tailwind).
#let primary-color = rgb("#274f4d")
#let secondary-color = rgb("#3f7d78")
#let accent-color = rgb("#2f6562")
#let box-bg = rgb("#f1f6f6")
#let line-color = rgb("#d6d3d1")

#set document(
  title: "{header_title}",
  author: "VGS Lærerassistent",
)

#set page(
  paper: "a4",
  margin: (x: 2cm, y: 2.5cm),
  header: context {{
    set text(size: 9pt, fill: gray)
    // Truncate long titles to prevent overlap with page numbers
    let max-title-len = 40
    let title-text = "{safe_topic}"
    let display-title = if title-text.len() > max-title-len {{
      title-text.slice(0, max-title-len - 3) + "..."
    }} else {{
      title-text
    }}
    grid(
      columns: (2fr, 1fr),
      align: (left, right),
      [{labels["worksheet"]}: #display-title],
      [{labels["level"]} {safe_level}]
    )
    v(0.5em)
    line(length: 100%, stroke: 0.5pt + line-color)
  }},
  footer: context {{
    set text(size: 9pt, fill: gray)
    line(length: 100%, stroke: 0.5pt + line-color)
    v(0.5em)
    h(1fr)
    counter(page).display("1 / 1", both: true)
    h(1fr)
  }},
)

#set text(
  // Robust font stack: prefers Noto Sans (typically present in prod/Docker),
  // falls back to widely available sans fonts so rendering stays consistent.
  font: ("Noto Sans", "Liberation Sans", "DejaVu Sans", "Arial"),
  size: 11pt,
  lang: "nb",  // Norwegian Bokmål
  hyphenate: true,  // avoids large gaps in justified Norwegian text
)

#set par(
  justify: true,
  leading: 0.78em,
  spacing: 1.25em,  // clearer separation between paragraphs
  first-line-indent: 0pt,
)

#set heading(numbering: none)

// Heading styles with clear visual hierarchy and orphan/widow control.
// Level 2: numbered major sections with a left brand-color stripe
// ("2 · Fagbegreper"). sticky: true keeps the heading with the content
// that follows, so it never strands at the bottom of a page.
#show heading.where(level: 2): it => {{
  counter("vgs-section").step()
  v(1.5em)
  block(breakable: false, sticky: true, below: 0.9em, above: 0.5em)[
    #grid(
      columns: (4pt, 1fr),
      column-gutter: 0.75em,
      align: (left, left + horizon),
      rect(width: 4pt, height: 1.35em, fill: secondary-color, radius: 2pt),
      text(fill: primary-color, size: 15pt, weight: "bold")[
        #context counter("vgs-section").display() · #it.body
      ],
    )
  ]
}}

// Level 3: Subsections (13pt, semibold, secondary color)
#show heading.where(level: 3): it => {{
  v(1em)
  block(breakable: false, sticky: true, below: 0.5em)[
    #text(fill: secondary-color, size: 13pt, weight: "semibold")[#it.body]
  ]
}}

// Level 4: Minor subheadings (11pt, medium weight)
#show heading.where(level: 4): it => {{
  v(0.6em)
  block(breakable: false, sticky: true, below: 0.3em)[
    #text(fill: rgb("#57534e"), size: 11pt, weight: "medium")[#it.body]
  ]
}}

// Header with integrated badges
#align(center)[
  #block(
    width: 100%,
    fill: primary-color,
    inset: 1.2em,
    radius: 4pt,
  )[
    #text(fill: white, size: 18pt, weight: "bold")[
      {header_title}
    ]
    #v(0.3em)
    #text(fill: rgb("#bcd6d3"), size: 12pt)[
      {header_subtitle}
    ]{badges_row}
  ]
]
{trust_badge_section}
#v(1em)

{learning_goals_section}

{pre_reading_section}

{image_section}

// Main educational text (no "Tekst" label - starts directly with content)
#block(
  width: 100%,
  inset: 1em,
  stroke: (left: 3pt + secondary-color),
)[
  {safe_main_text}
]

#v(0.8em)

{citation_legend_section}

#v(0.7em)

{vocabulary_section}

{language_exercises_section}

{difficulty_legend_section}

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
      {labels["generated_by"]} {safe_level} {labels["level_cefr"]}
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
        "learning_goals": "",
        "pre_reading": "",
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

    # Normalize markdown heading markers (### Header, ## Header) to plain headers
    # so the section patterns below (which don't expect '#') still match. The AI
    # frequently emits markdown headings, which previously broke section detection.
    text = re.sub(r'(?m)^\s{0,3}#{1,6}\s*', '', text)

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
        ('learning_goals', [
            # Norwegian
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*LÆRINGSMÅL[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Læringsmål[^\n]*\n',
            r'(?:^|\n)\s*LÆRINGSMÅL[^\n]*\n',
            r'(?:^|\n)\s*Læringsmål[^\n]*\n',
            # English
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*LEARNING\s*GOALS[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Learning\s*[Gg]oals[^\n]*\n',
            r'(?:^|\n)\s*LEARNING\s*GOALS[^\n]*\n',
            r'(?:^|\n)\s*Learning\s*[Gg]oals[^\n]*\n',
        ]),
        ('pre_reading', [
            # Norwegian
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*FØR\s*DU\s*LESER[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Før\s*du\s*leser[^\n]*\n',
            r'(?:^|\n)\s*FØR\s*DU\s*LESER[^\n]*\n',
            r'(?:^|\n)\s*Før\s*du\s*leser[^\n]*\n',
            # English
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*BEFORE\s*YOU\s*READ[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Before\s*[Yy]ou\s*[Rr]ead[^\n]*\n',
            r'(?:^|\n)\s*BEFORE\s*YOU\s*READ[^\n]*\n',
            r'(?:^|\n)\s*Before\s*[Yy]ou\s*[Rr]ead[^\n]*\n',
        ]),
        ('vocabulary', [
            # Norwegian
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*VIKTIGE\s*BEGREPER[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Viktige\s*begreper[^\n]*\n',
            r'(?:^|\n)\s*VIKTIGE\s*BEGREPER[^\n]*\n',
            r'(?:^|\n)\s*Viktige\s*begreper[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*FAGBEGREPER[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Fagbegreper[^\n]*\n',
            r'(?:^|\n)\s*FAGBEGREPER[^\n]*\n',
            r'(?:^|\n)\s*Fagbegreper[^\n]*\n',
            # English
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*KEY\s*VOCABULARY[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Key\s*[Vv]ocabulary[^\n]*\n',
            r'(?:^|\n)\s*KEY\s*VOCABULARY[^\n]*\n',
            r'(?:^|\n)\s*Key\s*[Vv]ocabulary[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*SUBJECT\s*TERMINOLOGY[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Subject\s*[Tt]erminology[^\n]*\n',
            r'(?:^|\n)\s*SUBJECT\s*TERMINOLOGY[^\n]*\n',
            r'(?:^|\n)\s*Subject\s*[Tt]erminology[^\n]*\n',
        ]),
        ('comprehension', [
            # Norwegian
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*FORSTÅELSE\s*OG\s*ANALYSE[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Forståelse\s*og\s*analyse[^\n]*\n',
            r'(?:^|\n)\s*FORSTÅELSE\s*OG\s*ANALYSE[^\n]*\n',
            r'(?:^|\n)\s*Forståelse\s*og\s*analyse[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*LESEFORSTÅELSE[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Leseforståelse[^\n]*\n',
            r'(?:^|\n)\s*LESEFORSTÅELSE[^\n]*\n',
            r'(?:^|\n)\s*Leseforståelse[^\n]*\n',
            # English
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*COMPREHENSION\s*AND\s*ANALYSIS[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Comprehension\s*[Aa]nd\s*[Aa]nalysis[^\n]*\n',
            r'(?:^|\n)\s*COMPREHENSION\s*AND\s*ANALYSIS[^\n]*\n',
            r'(?:^|\n)\s*Comprehension\s*[Aa]nd\s*[Aa]nalysis[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*READING\s*COMPREHENSION[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Reading\s*[Cc]omprehension[^\n]*\n',
            r'(?:^|\n)\s*READING\s*COMPREHENSION[^\n]*\n',
            r'(?:^|\n)\s*Reading\s*[Cc]omprehension[^\n]*\n',
        ]),
        ('discussion', [
            # Norwegian
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*DRØFTING\s*OG\s*REFLEKSJON[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Drøfting\s*og\s*refleksjon[^\n]*\n',
            r'(?:^|\n)\s*DRØFTING\s*OG\s*REFLEKSJON[^\n]*\n',
            r'(?:^|\n)\s*Drøfting\s*og\s*refleksjon[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*DISKUSJON[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Diskusjon[^\n]*\n',
            r'(?:^|\n)\s*DISKUSJON[^\n]*\n',
            r'(?:^|\n)\s*Diskusjon[^\n]*\n',
            # English
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*DISCUSSION\s*AND\s*REFLECTION[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Discussion\s*[Aa]nd\s*[Rr]eflection[^\n]*\n',
            r'(?:^|\n)\s*DISCUSSION\s*AND\s*REFLECTION[^\n]*\n',
            r'(?:^|\n)\s*Discussion\s*[Aa]nd\s*[Rr]eflection[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*DISCUSSION[^\n]*\n',
            r'(?:^|\n)\s*\**[a-z]\)\s*\**\s*Discussion[^\n]*\n',
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
        content = re.sub(r'^[a-z]\)\s*', '', content)
        # Remove bold markers from section headers
        content = re.sub(r'^\*\*\s*', '', content)
        content = re.sub(r'\s*\*\*\s*$', '', content, count=1)
        # Remove both Norwegian and English section headers
        content = re.sub(r'^(?:LÆRINGSMÅL|Læringsmål|LEARNING\s*GOALS|Learning\s*[Gg]oals|FØR\s*DU\s*LESER|Før\s*du\s*leser|BEFORE\s*YOU\s*READ|Before\s*[Yy]ou\s*[Rr]ead|VIKTIGE\s*BEGREPER|Viktige\s*begreper|KEY\s*VOCABULARY|Key\s*[Vv]ocabulary|SUBJECT\s*TERMINOLOGY|Subject\s*[Tt]erminology|FAGBEGREPER|Fagbegreper|LESEFORSTÅELSE|Leseforståelse|READING\s*COMPREHENSION|Reading\s*[Cc]omprehension|FORSTÅELSE\s*OG\s*ANALYSE|Forståelse\s*og\s*analyse|COMPREHENSION\s*AND\s*ANALYSIS|Comprehension\s*[Aa]nd\s*[Aa]nalysis|DISKUSJON|Diskusjon|DISCUSSION|Discussion|DRØFTING\s*OG\s*REFLEKSJON|Drøfting\s*og\s*refleksjon|KULTURBLIKK|Kulturblikk|CULTURAL\s*PERSPECTIVE|Cultural\s*[Pp]erspective|SAMFUNNSPERSPEKTIV|Samfunnsperspektiv|GLOBAL\s*PERSPECTIVE|Global\s*[Pp]erspective)[^\n]*\n*', '', content, flags=re.IGNORECASE)
        
        if content.strip() and not sections[name]:
            sections[name] = content.strip()

    # Fallback: only if NO section headers were detected at all, treat the whole
    # worksheet as vocabulary so nothing is lost. Previously this could clobber a
    # partially-parsed worksheet (e.g. one with only learning goals + discussion).
    if not section_starts and text.strip():
        sections["vocabulary"] = text

    return sections


def render_faktarapport_section(faktarapport_text: str, is_english: bool = False) -> str:
    """
    Render the Faktarapport (teacher fact-check report) as a distinct Typst page.
    This section is clearly marked as teacher-only and NOT for students.
    """
    if not faktarapport_text or not faktarapport_text.strip():
        return ""

    safe_text = sanitize_for_typst(faktarapport_text, is_section_content=True)
    label = "FACT REPORT — For the teacher only" if is_english else "FAKTARAPPORT — Kun for læreren"
    subtitle = "Quality assurance of AI-generated content" if is_english else "Kvalitetssikring av AI-generert innhold"
    not_for_students = "This page is NOT for students." if is_english else "Denne siden er IKKE for elever."
    running_left = "FACT REPORT — TEACHER ONLY" if is_english else "FAKTARAPPORT — KUN FOR LÆREREN"
    running_right = "DO NOT HAND OUT" if is_english else "SKAL IKKE DELES UT"

    # The report gets a tinted page background and its own repeating warning
    # header, so it is visually unmistakable — a teacher printing "all pages"
    # in a hurry will spot it immediately. These #set rules apply from this
    # page to the end of the document; the report is always the last section.
    return f'''
#pagebreak()

// ── Faktarapport-side (tinted, clearly teacher-only) ────────────────────────
#set page(
  fill: rgb("#f4f1ea"),
  header: context {{
    set text(size: 8.5pt, weight: "bold", fill: rgb("#92400e"))
    grid(
      columns: (1fr, auto),
      align: (left, right),
      [{running_left}],
      [{running_right}],
    )
    v(0.4em)
    line(length: 100%, stroke: 1pt + rgb("#ca8a04"))
  }},
)

// Teacher-page headings: unnumbered and amber-toned, visually distinct from
// the numbered student sections.
#show heading.where(level: 2): it => {{
  v(1.2em)
  block(breakable: false, sticky: true, below: 0.7em)[
    #text(fill: rgb("#92400e"), size: 14pt, weight: "bold")[#it.body]
  ]
}}

#block(
  width: 100%,
  inset: (x: 1.2em, y: 0.8em),
  radius: 6pt,
  fill: rgb("#fefce8"),
  stroke: 2pt + rgb("#ca8a04"),
)[
  #grid(
    columns: (auto, 1fr),
    gutter: 0.8em,
    align: (center + horizon, left),
    [#box(fill: rgb("#ca8a04"), radius: 99pt, inset: (x: 11pt, y: 7pt))[#text(fill: white, weight: "bold", size: 14pt)[!]]],
    [
      #text(weight: "bold", size: 12pt, fill: rgb("#92400e"))[{label}]
      #linebreak()
      #text(size: 9pt, fill: rgb("#b45309"))[{subtitle}]
      #linebreak()
      #text(size: 8pt, fill: rgb("#d97706"), style: "italic")[{not_for_students}]
    ]
  )
]

#v(1.2em)

{safe_text}
'''


def create_lesson_pdf(
    content_text: str,
    worksheet_text: str,
    topic: str,
    level: str,
    subject: str = "Norsk",
    language_level: Optional[str] = None,
    image_path: Optional[str] = None,
    language_exercises: Optional[dict] = None,
    options: dict = None,
    faktarapport: Optional[str] = None,
    source_name: Optional[str] = None,
) -> bytes:
    """
    Create a PDF lesson plan from the AI-generated content.

    Args:
        content_text: The main educational text from the Content Creator agent
        worksheet_text: The worksheet content from the Pedagogical Developer agent
        topic: The lesson topic
        level: VGS level (VG1, VG2, VG3, Yrkesfag)
        subject: Subject area (e.g., "Norsk", "Engelsk") - affects output language
        language_level: Optional language simplification level (B1, B2) for minority language students
        image_path: Optional path to a local image file (already processed/optimized)
        language_exercises: Optional dict with grammar, vocabulary, syntax tasks
        options: Dictionary of modular options
        faktarapport: Optional teacher fact-check report text

    Returns:
        Binary PDF data
    """
    # Parse the worksheet into sections
    sections = parse_worksheet_content(worksheet_text)

    is_english = subject.lower() == "engelsk"

    # Determine image root directory and filename for Typst
    image_root = None
    image_filename = None
    if image_path and os.path.exists(image_path):
        image_root = os.path.dirname(image_path)
        image_filename = os.path.basename(image_path)

    # Create the Typst document (with or without image)
    typst_doc = create_typst_template(
        topic=topic,
        level=level,
        subject=subject,
        language_level=language_level,
        main_text=content_text,
        learning_goals=sections["learning_goals"],
        pre_reading=sections["pre_reading"],
        vocabulary=sections["vocabulary"],
        comprehension=sections["comprehension"],
        discussion=sections["discussion"],
        cultural=sections["cultural"],
        role_play=sections["role_play"],
        image_description=sections["image_description"],
        writing_frame=sections["writing_frame"],
        real_case=sections["real_case"],
        teacher_key=sections["teacher_key"],
        image_path=image_filename,  # Just the filename, not full path
        language_exercises=language_exercises,
        options=options,
        source_name=source_name,
    )

    # Append Faktarapport page if present
    if faktarapport and faktarapport.strip():
        typst_doc += render_faktarapport_section(faktarapport, is_english=is_english)

    # Compile to PDF using typst CLI
    full_image_path = None
    if image_filename and image_root:
        full_image_path = os.path.join(image_root, image_filename)

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
#set text(font: ("Noto Sans", "Liberation Sans", "DejaVu Sans", "Arial"), size: 11pt, lang: "nb", hyphenate: true)
#set par(justify: true, leading: 0.8em, spacing: 1.2em)

#let primary = rgb("#1e40af")
#let box-bg = rgb("#f1f5f9")
#let line-color = rgb("#cbd5e1")

#align(center)[
  #block(fill: primary, inset: 1.2em, radius: 4pt, width: 100%)[
    #text(fill: white, size: 18pt, weight: "bold")[Læringsark: {safe_topic}]
    #v(0.3em)
    #text(fill: rgb("#bfdbfe"), size: 12pt)[Nivå {level} | Videregående skole]
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
  #text(size: 9pt, fill: gray)[Generert av VGS Lærerassistent | Nivå {level}]
]
'''
    
    typst_doc = build_doc(img_filename=image_filename)
    
    # Compile to PDF using typst CLI
    full_image_path = None
    if image_filename and image_root:
        full_image_path = os.path.join(image_root, image_filename)
    
    pdf_bytes = compile_typst(typst_doc, image_path=full_image_path)

    return pdf_bytes


# ── Differensiering: kombinert 3-nivå PDF ─────────────────────────────────────

def _diff_section(text: str, level_label: str, level_color: str,
                  badge_emoji: str, badge_bg: str, badge_fg: str,
                  desc: str, topic: str, subject: str, level: str) -> str:
    """Render one differentiation level as a Typst section."""
    safe = sanitize_for_typst(text)
    safe_label = sanitize_for_typst(level_label)
    safe_topic = sanitize_for_typst(topic)
    safe_desc = sanitize_for_typst(desc)
    safe_level = sanitize_for_typst(level)
    return f'''
#pagebreak()

// ── {level_label} ────────────────────────────────────────────────────────────
#block(
  width: 100%,
  inset: (x: 1.2em, y: 0.9em),
  radius: 6pt,
  fill: rgb("{level_color}"),
  stroke: none,
)[
  #grid(
    columns: (auto, 1fr),
    gutter: 0.8em,
    align: (center, left),
    [#box(fill: rgb("{badge_bg}"), inset: (x:8pt,y:4pt), radius:3pt)[
      #text(fill: rgb("{badge_fg}"), size: 11pt, weight: "bold")[{badge_emoji} {safe_label}]
    ]],
    [
      #text(weight: "bold", size: 13pt, fill: white)[{safe_topic}]
      #linebreak()
      #text(size: 9pt, fill: rgb("#e2e8f0"))[{safe_desc} | {safe_level} | {sanitize_for_typst(subject)}]
    ]
  )
]

#v(1.2em)

{safe}
'''


def _diff_worksheet_section(worksheet_text: str, language_exercises: Optional[dict],
                            topic: str, subject: str, level: str,
                            options: Optional[dict], is_english: bool) -> str:
    """Render a shared worksheet/oppgaver page for the differentiated PDF.

    All three levels (støtte/standard/fordypning) share the same tasks, so the
    teacher gets a usable arbeidsark instead of only the three texts.
    """
    has_worksheet = bool(worksheet_text and worksheet_text.strip())
    has_exercises = bool(language_exercises and any(
        language_exercises.get(k) for k in ("grammar_tasks", "vocabulary_tasks", "syntax_tasks")
    ))
    if not has_worksheet and not has_exercises:
        return ""

    section_labels = [
        ("vocabulary", "Fagbegreper" if not is_english else "Key vocabulary"),
        ("comprehension", "Forståelse og analyse" if not is_english else "Comprehension and analysis"),
        ("discussion", "Drøfting og refleksjon" if not is_english else "Discussion and reflection"),
        ("cultural", "Kulturblikk" if not is_english else "Cultural perspective"),
    ]

    body_parts = []
    if has_worksheet:
        sections = parse_worksheet_content(worksheet_text)
        for key, label in section_labels:
            content = sections.get(key, "")
            if content and content.strip():
                body_parts.append(
                    f'#text(weight: "bold", size: 12pt, fill: rgb("#0f766e"))[{sanitize_for_typst(label)}]\n'
                    f'#v(0.4em)\n{sanitize_for_typst(content, is_section_content=True)}\n#v(1em)'
                )

    if has_exercises:
        exercises_typst = format_language_exercises(
            language_exercises,
            options or {"grammar_tasks": True, "vocabulary_tasks": True},
            is_english,
        )
        if exercises_typst.strip():
            body_parts.append(exercises_typst)

    if not body_parts:
        return ""

    title = "Arbeidsark — felles oppgaver" if not is_english else "Worksheet — shared tasks"
    subtitle = ("Samme oppgaver for alle tre nivåer" if not is_english
                else "The same tasks for all three levels")
    body = "\n\n".join(body_parts)
    return f'''
#pagebreak()

// ── Felles arbeidsark ────────────────────────────────────────────────────────
#block(
  width: 100%,
  inset: (x: 1.2em, y: 0.9em),
  radius: 6pt,
  fill: rgb("#0f766e"),
  stroke: none,
)[
  #text(weight: "bold", size: 13pt, fill: white)[{sanitize_for_typst(title)}]
  #linebreak()
  #text(size: 9pt, fill: rgb("#ccfbf1"))[{sanitize_for_typst(subtitle)} | {sanitize_for_typst(topic)}]
]

#v(1.2em)

{body}
'''


def create_differentiated_pdf(
    standard_text: str,
    stoette_text: str,
    fordypning_text: str,
    topic: str,
    level: str,
    subject: str,
    image_path: Optional[str] = None,
    worksheet_text: str = "",
    language_exercises: Optional[dict] = None,
    options: Optional[dict] = None,
) -> bytes:
    """
    Generer en kombinert PDF med alle tre differensieringsnivåer på separate sider.
    Læreren printer riktige sider for hver elevgruppe.
    """
    safe_topic  = sanitize_for_typst(topic)
    safe_level  = sanitize_for_typst(level)
    safe_subject = sanitize_for_typst(subject)

    image_filename = None
    image_root = None
    if image_path and os.path.exists(image_path):
        image_root = os.path.dirname(image_path)
        image_filename = os.path.basename(image_path)

    image_section = ""
    if image_filename:
        image_section = f'''
#align(center)[
  #block(width: 75%, clip: true, radius: 6pt, stroke: 1pt + line-color)[
    #image("{image_filename}", width: 100%)
  ]
  #v(0.3em)
  #text(size: 8pt, fill: gray)[Kilde: Wikimedia Commons]
]
#v(1em)
'''

    is_english = subject.lower() == "engelsk"
    worksheet_section = _diff_worksheet_section(
        worksheet_text, language_exercises, topic, subject, level, options, is_english
    )
    worksheet_note = (
        "\n  - *Siste side*: Felles arbeidsark — oppgaver som passer alle tre nivåer\n  #linebreak()"
        if worksheet_section else ""
    )

    cover = f'''// VGS Lærerassistent — Differensiert undervisningsmateriell
#let primary-color  = rgb("#1e40af")
#let line-color     = rgb("#cbd5e1")
#let box-bg         = rgb("#f1f5f9")

#set document(title: "Differensiert læringsark: {safe_topic}")
#set page(paper: "a4", margin: (x: 2cm, y: 2.5cm),
  footer: context {{
    set text(size: 8pt, fill: gray)
    line(length: 100%, stroke: 0.5pt + line-color)
    v(0.3em)
    h(1fr)
    counter(page).display("1 / 1", both: true)
    h(1fr)
  }}
)
#set text(font: ("Noto Sans", "Liberation Sans", "DejaVu Sans", "Arial"), size: 11pt, lang: "nb", hyphenate: true)
#set par(justify: true, leading: 0.75em, spacing: 1.2em)

// ── Forside ──────────────────────────────────────────────────────────────────
#align(center)[
  #block(fill: primary-color, inset: 1.4em, radius: 8pt, width: 100%)[
    #text(fill: white, size: 20pt, weight: "bold")[Differensiert læringsmateriell]
    #v(0.3em)
    #text(fill: rgb("#bfdbfe"), size: 14pt)[{safe_topic}]
    #v(0.4em)
    #text(fill: rgb("#93c5fd"), size: 10pt)[{safe_subject} | {safe_level} | Videregående skole]
    #v(0.6em)
    #grid(columns: 3, gutter: 1em, align: center,
      box(fill: rgb("#166534"), inset:(x:10pt,y:5pt), radius:4pt)[#text(fill:white, size:9pt, weight:"bold")[📗 STØTTE]],
      box(fill: rgb("#1e40af"), inset:(x:10pt,y:5pt), radius:4pt)[#text(fill:white, size:9pt, weight:"bold")[📘 STANDARD]],
      box(fill: rgb("#7c2d12"), inset:(x:10pt,y:5pt), radius:4pt)[#text(fill:white, size:9pt, weight:"bold")[📕 FORDYPNING]],
    )
  ]
]

#v(1em)

#block(fill: rgb("#fefce8"), inset: 1em, radius: 6pt, stroke: 1pt + rgb("#ca8a04"))[
  #text(weight: "bold", size: 10pt)[📋 Til læreren:]
  #v(0.3em)
  Dette dokumentet inneholder tre nivåtilpassede versjoner av samme fagtekst.
  #linebreak()
  - *Sider 2+*: 📗 Støtte — forenklet tekst for elever som trenger ekstra hjelp
  - *Sider X+*: 📘 Standard — ordinær VGS-tekst for de fleste elever
  - *Sider Y+*: 📕 Fordypning — utvidet tekst for elever som trenger utfordringer
  #linebreak(){worksheet_note}
  Print ut riktige sider for hver elevgruppe.
]

{image_section}
'''

    stoette_section = _diff_section(
        stoette_text, "STØTTE", "#14532d", "📗", "#166534", "#ffffff",
        "Tilpasset for elever som trenger ekstra støtte", topic, subject, level
    )
    standard_section = _diff_section(
        standard_text, "STANDARD", "#1e3a8a", "📘", "#1e40af", "#ffffff",
        "Ordinært VGS-nivå", topic, subject, level
    )
    fordypning_section = _diff_section(
        fordypning_text, "FORDYPNING", "#431407", "📕", "#7c2d12", "#ffffff",
        "Utvidet for elever som trenger utfordringer", topic, subject, level
    )

    typst_doc = cover + stoette_section + standard_section + fordypning_section + worksheet_section

    full_image_path = None
    if image_filename and image_root:
        full_image_path = os.path.join(image_root, image_filename)

    return compile_typst(typst_doc, image_path=full_image_path)


# ── Prøvegenerator PDF ────────────────────────────────────────────────────────

def create_prove_pdf(prove_json: dict, topic: str, level: str, subject: str,
                     include_fasit: bool = False) -> bytes:
    """
    Lag en profesjonell prøve-PDF fra strukturert JSON.

    Args:
        prove_json: Parsed JSON from the prove agent
        topic: Exam topic
        level: VGS level
        subject: Subject
        include_fasit: If True, append teacher answer key

    Returns:
        PDF bytes
    """
    def s(text) -> str:
        return sanitize_for_typst(str(text)) if text else ""

    safe_topic   = s(topic)
    safe_level   = s(level)
    safe_subject = s(subject)

    tittel        = s(prove_json.get("tittel", f"Prøve: {topic}"))
    tid           = s(prove_json.get("tid", "90 minutter"))
    total_poeng   = prove_json.get("total_poeng", "?")
    del_a         = prove_json.get("del_a", {})
    del_b         = prove_json.get("del_b", {})
    del_c         = prove_json.get("del_c", {})

    # ── Del A: Flervalg ──────────────────────────────────────────────────────
    del_a_content = ""
    for sp in del_a.get("sporsmal", []):
        nr   = sp.get("nr", "?")
        tekst = s(sp.get("tekst", ""))
        alts  = sp.get("alternativer", {})
        poeng_label = f"({del_a.get('poeng_per_sporsmal', 2)}p)"
        options_typst = "\n".join(
            f"  #h(1em) {k}) {s(v)}" for k, v in alts.items()
        )
        del_a_content += f"""
#block(inset: (y: 0.4em))[
  *{nr}. {tekst}* {poeng_label}
{options_typst}
]
"""

    # ── Del B: Kortsvarsoppgaver ──────────────────────────────────────────────
    del_b_content = ""
    for sp in del_b.get("sporsmal", []):
        nr    = sp.get("nr", "?")
        tekst = s(sp.get("tekst", ""))
        poeng = sp.get("poeng", "?")
        del_b_content += f"""
#block(inset: (y: 0.4em))[
  *{nr}. {tekst}* ({poeng}p)
]
#v(0.3em)
#for _ in range(4) {{
  line(length: 100%, stroke: 0.4pt + gray)
  v(1.2em)
}}
"""

    # ── Del C: Langsvarsoppgave ───────────────────────────────────────────────
    del_c_content = ""
    for sp in del_c.get("sporsmal", []):
        nr    = sp.get("nr", "?")
        tekst = s(sp.get("tekst", ""))
        poeng = sp.get("poeng", "?")
        kriterier = s(sp.get("vurderingskriterier", ""))
        del_c_content += f"""
#block(inset: (y: 0.4em))[
  *{nr}. {tekst}* ({poeng}p)
  #v(0.3em)
  #text(size: 9pt, fill: gray)[{s(del_c.get("instruksjon", "Skriv et sammenhengende svar."))}]
]
#v(0.3em)
#for _ in range(12) {{
  line(length: 100%, stroke: 0.4pt + gray)
  v(1.4em)
}}
"""
        if kriterier:
            del_c_content += f"""
#block(fill: rgb("#f1f5f9"), inset: 0.8em, radius: 4pt)[
  #text(size: 9pt, style: "italic")[*Vurderingskriterier:* {kriterier}]
]
"""

    # ── Fasit ─────────────────────────────────────────────────────────────────
    fasit_section = ""
    if include_fasit:
        fasit_a = "\n".join(
            f"  {sp.get('nr', '?')}. {s(sp.get('riktig', '?')).upper()}) {s(sp.get('alternativer', {}).get(sp.get('riktig', ''), ''))}"
            for sp in del_a.get("sporsmal", [])
        )
        fasit_b = "\n\n".join(
            f"  *{sp.get('nr', '?')}.* {s(sp.get('fasit', ''))}"
            for sp in del_b.get("sporsmal", [])
        )
        fasit_c = "\n\n".join(
            f"  *{sp.get('nr', '?')}.* {s(sp.get('fasit', ''))}"
            for sp in del_c.get("sporsmal", [])
        )
        fasit_section = f"""
#pagebreak()

#block(fill: rgb("#14532d"), inset: (x:1.2em, y:0.9em), radius:6pt, width:100%)[
  #text(fill: white, size: 16pt, weight: "bold")[✅ FASIT — Kun for læreren]
  #v(0.2em)
  #text(fill: rgb("#bbf7d0"), size: 9pt)[{safe_topic} | {safe_level} | Ikke del med elever]
]
#v(1em)

*Del A – Flervalg:*
{fasit_a}

#v(1em)

*Del B – Kortsvarsoppgaver:*
{fasit_b}

#v(1em)

*Del C – Langsvarsoppgave:*
{fasit_c}
"""

    typst_doc = f"""// VGS Prøvegenerator
#let primary   = rgb("#1e40af")
#let line-color = rgb("#cbd5e1")

#set document(title: "{tittel}")
#set page(paper: "a4", margin: (x: 2cm, y: 2.5cm),
  header: context {{
    set text(size: 8pt, fill: gray)
    grid(columns: (1fr, auto), align: (left, right),
      [{safe_subject} | {safe_level}],
      [Poeng: ___ / {total_poeng}]
    )
    v(0.3em)
    line(length: 100%, stroke: 0.4pt + line-color)
  }},
  footer: context {{
    set text(size: 8pt, fill: gray)
    line(length: 100%, stroke: 0.4pt + line-color)
    v(0.3em)
    h(1fr)
    counter(page).display("1 / 1", both: true)
    h(1fr)
  }}
)
#set text(font: ("Noto Sans", "Liberation Sans", "DejaVu Sans", "Arial"), size: 11pt, lang: "nb", hyphenate: true)
#set par(justify: true, leading: 0.75em, spacing: 1.2em)

// ── Forsideblokk ─────────────────────────────────────────────────────────────
#block(fill: primary, inset: 1.3em, radius: 6pt, width: 100%)[
  #text(fill: white, size: 18pt, weight: "bold")[{tittel}]
  #v(0.4em)
  #grid(columns: (1fr, 1fr, 1fr), align: left,
    [#text(fill: rgb("#bfdbfe"), size: 10pt)[Fag: *{safe_subject}*]],
    [#text(fill: rgb("#bfdbfe"), size: 10pt)[Trinn: *{safe_level}*]],
    [#text(fill: rgb("#bfdbfe"), size: 10pt)[Tid: *{tid}*]],
  )
]

#v(0.6em)

#block(fill: rgb("#f1f5f9"), inset: 0.8em, radius: 4pt)[
  #grid(columns: (1fr, 1fr, 1fr), align: left,
    [Navn: #h(1fr) #box(width: 8em, stroke: (bottom: 1pt + gray))[#h(8em)]],
    [Klasse: #h(1fr) #box(width: 5em, stroke: (bottom: 1pt + gray))[#h(5em)]],
    [Dato: #h(1fr) #box(width: 6em, stroke: (bottom: 1pt + gray))[#h(6em)]],
  )
]

#v(1em)

// ── Del A ─────────────────────────────────────────────────────────────────────
#block(fill: rgb("#dbeafe"), inset: (x:1em, y:0.6em), radius: 4pt)[
  #text(weight: "bold", size: 12pt)[{s(del_a.get("tittel", "Del A – Flervalgsoppgaver"))}]
  #h(1em) #text(size: 9pt, style: "italic")[{s(del_a.get("instruksjon", "Sett ring rundt riktig svar."))}]
]

{del_a_content}

#v(0.8em)

// ── Del B ─────────────────────────────────────────────────────────────────────
#block(fill: rgb("#dcfce7"), inset: (x:1em, y:0.6em), radius: 4pt)[
  #text(weight: "bold", size: 12pt)[{s(del_b.get("tittel", "Del B – Kortsvarsoppgaver"))}]
  #h(1em) #text(size: 9pt, style: "italic")[{s(del_b.get("instruksjon", "Svar med 3–5 setninger."))}]
]

{del_b_content}

#v(0.8em)

// ── Del C ─────────────────────────────────────────────────────────────────────
#block(fill: rgb("#fee2e2"), inset: (x:1em, y:0.6em), radius: 4pt)[
  #text(weight: "bold", size: 12pt)[{s(del_c.get("tittel", "Del C – Langsvarsoppgave"))}]
  #h(1em) #text(size: 9pt, style: "italic")[{s(del_c.get("instruksjon", "Skriv et sammenhengende svar."))}]
]

{del_c_content}

{fasit_section}
"""
    return compile_typst(typst_doc)


def create_sequence_pdf(sequence_json: dict, topic: str, level: str, subject: str) -> bytes:
    """
    Lag en profesjonell sekvensplan-PDF fra strukturert JSON.

    Args:
        sequence_json: Parsed JSON from the sequence agent
        topic:         Topic/theme of the sequence
        level:         School level (VG1, VG2, VG3, Yrkesfag)
        subject:       Subject (Norsk, Historie, etc.)

    Returns:
        PDF bytes
    """
    def s(text) -> str:
        return sanitize_for_typst(str(text)) if text else ""

    safe_topic   = s(topic)
    safe_level   = s(level)
    safe_subject = s(subject)

    tittel        = s(sequence_json.get("tittel", f"Sekvensplan: {topic}"))
    antall_uker   = sequence_json.get("antall_uker", "?")
    kompetansemaal = sequence_json.get("kompetansemaal", [])
    uker          = sequence_json.get("uker", [])
    avsluttende   = s(sequence_json.get("avsluttende_vurdering", ""))
    ressursliste  = sequence_json.get("ressursliste", [])

    # ── Kompetansemål list ───────────────────────────────────────────────────
    km_items = "\n".join(
        f'#list-item[{s(km)}]' for km in kompetansemaal
    ) if kompetansemaal else "#list-item[Se LK20 for gjeldende kompetansemål]"

    # ── Overview table ───────────────────────────────────────────────────────
    # Build a simple overview: Uke | Tema | Antall timer
    overview_rows = ""
    for uke in uker:
        uke_nr   = uke.get("uke_nr", "?")
        uke_tema = s(uke.get("uke_tema", ""))
        n_timer  = len(uke.get("timer", []))
        overview_rows += f"""
  table.cell[*Uke {uke_nr}*],
  table.cell[{uke_tema}],
  table.cell(align: center)[{n_timer}],"""

    overview_table = f"""
#table(
  columns: (auto, 1fr, auto),
  table.header(
    table.cell(fill: rgb("#1e3a8a"))[#text(fill: white, weight: "bold")[Uke]],
    table.cell(fill: rgb("#1e3a8a"))[#text(fill: white, weight: "bold")[Tema]],
    table.cell(fill: rgb("#1e3a8a"), align: center)[#text(fill: white, weight: "bold")[Timer]],
  ),{overview_rows}
)"""

    # ── Lesson cards ─────────────────────────────────────────────────────────
    lesson_cards = ""
    week_colors = ["#eff6ff", "#f0fdf4", "#fefce8", "#fdf4ff", "#fff7ed", "#f0f9ff"]

    for uke in uker:
        uke_nr    = uke.get("uke_nr", "?")
        uke_tema  = s(uke.get("uke_tema", ""))
        ukes_vurd = s(uke.get("ukes_vurdering", ""))
        timer     = uke.get("timer", [])
        bg_color  = week_colors[(int(uke_nr) - 1) % len(week_colors)] if str(uke_nr).isdigit() else week_colors[0]

        lesson_cards += f"""
#pagebreak(weak: true)
#block(fill: rgb("{bg_color}"), inset: 1em, radius: 6pt, width: 100%)[
  #text(size: 14pt, weight: "bold")[Uke {uke_nr}: {uke_tema}]
]
#v(0.6em)
"""
        for t in timer:
            time_nr     = t.get("time_nr", "?")
            tittel_t    = s(t.get("tittel", ""))
            varighet    = s(t.get("varighet", "90 min"))
            bloom       = s(t.get("bloom_niva", ""))
            laeringsmaal = t.get("laeringsmaal", [])
            aktiviteter = t.get("aktiviteter", {})
            vurdering   = s(t.get("vurdering", ""))
            ressurser   = t.get("ressurser", [])
            diff        = s(t.get("differensiering", ""))

            lm_items = "\n".join(f"  #list-item[{s(lm)}]" for lm in laeringsmaal) if laeringsmaal else ""
            res_items = " · ".join(s(r) for r in ressurser) if ressurser else "—"

            intro_txt = s(aktiviteter.get("intro", ""))
            hoved_txt = s(aktiviteter.get("hoved", ""))
            avsl_txt  = s(aktiviteter.get("avslutning", ""))

            bloom_badge = f'#text(size: 8pt, fill: rgb("#6b7280"))[Bloom: {bloom}]' if bloom else ""

            lesson_cards += f"""
#block(stroke: 0.5pt + rgb("#cbd5e1"), inset: (x: 1em, y: 0.8em), radius: 4pt, width: 100%, below: 0.8em)[
  #grid(columns: (1fr, auto), gutter: 0.5em)[
    #text(weight: "bold", size: 11pt)[Time {time_nr}: {tittel_t}]
  ][
    #text(size: 9pt, fill: rgb("#64748b"))[{varighet}]
  ]
  #v(0.2em)
  {bloom_badge}

  #if ({len(laeringsmaal)} > 0) [
    #v(0.4em)
    #text(size: 9pt, weight: "bold")[Læringsmål:]
    {lm_items}
  ]

  #v(0.5em)
  #grid(columns: (1fr, 1fr, 1fr), gutter: 0.6em)[
    #block(fill: rgb("#dbeafe"), inset: 0.6em, radius: 3pt)[
      #text(size: 8pt, weight: "bold")[🔵 Intro]
      #linebreak()
      #text(size: 8pt)[{intro_txt}]
    ]
  ][
    #block(fill: rgb("#dcfce7"), inset: 0.6em, radius: 3pt)[
      #text(size: 8pt, weight: "bold")[🟢 Hoveddel]
      #linebreak()
      #text(size: 8pt)[{hoved_txt}]
    ]
  ][
    #block(fill: rgb("#fef9c3"), inset: 0.6em, radius: 3pt)[
      #text(size: 8pt, weight: "bold")[🟡 Avslutning]
      #linebreak()
      #text(size: 8pt)[{avsl_txt}]
    ]
  ]

  #v(0.4em)
  #grid(columns: (1fr, 1fr), gutter: 0.6em)[
    #block(fill: rgb("#f1f5f9"), inset: 0.5em, radius: 3pt)[
      #text(size: 8pt, weight: "bold")[📊 Vurdering]
      #linebreak()
      #text(size: 8pt)[{vurdering}]
    ]
  ][
    #block(fill: rgb("#f1f5f9"), inset: 0.5em, radius: 3pt)[
      #text(size: 8pt, weight: "bold")[Ressurser]
      #linebreak()
      #text(size: 8pt)[{res_items}]
    ]
  ]

  #if ("{diff}" != "") [
    #v(0.3em)
    #block(fill: rgb("#fdf4ff"), inset: 0.5em, radius: 3pt)[
      #text(size: 8pt, weight: "bold")[Differensiering]
      #linebreak()
      #text(size: 8pt)[{diff}]
    ]
  ]
]
"""

        if ukes_vurd:
            lesson_cards += f"""
#block(fill: rgb("#fef3c7"), stroke: 0.5pt + rgb("#d97706"), inset: 0.7em, radius: 4pt, width: 100%, below: 1em)[
  #text(size: 9pt, weight: "bold")[📋 Ukesvurdering:] #text(size: 9pt)[{ukes_vurd}]
]
"""

    # ── Resources list ───────────────────────────────────────────────────────
    res_list = "\n".join(f"#list-item[{s(r)}]" for r in ressursliste) if ressursliste else "#list-item[Se læreplan og nettressurser]"

    # ── Avsluttende vurdering ────────────────────────────────────────────────
    avsl_section = ""
    if avsluttende:
        avsl_section = f"""
#pagebreak()
#block(fill: rgb("#1e3a8a"), inset: 1.2em, radius: 6pt, width: 100%)[
  #text(fill: white, size: 14pt, weight: "bold")[🎓 Avsluttende vurdering]
]
#v(0.8em)
#block(fill: rgb("#eff6ff"), stroke: 0.5pt + rgb("#93c5fd"), inset: 1em, radius: 4pt)[
  {avsluttende}
]
#v(1.2em)
#text(size: 12pt, weight: "bold")[Ressursliste]
#v(0.4em)
{res_list}
"""

    typst_source = f"""
#set page(
  paper: "a4",
  margin: (top: 2cm, bottom: 2cm, left: 2.2cm, right: 2cm),
  header: [
    #set text(size: 8pt, fill: rgb("#94a3b8"))
    #grid(columns: (1fr, auto))[
      VGS Lærerassistent · Sekvensplan
    ][
      {safe_subject} · {safe_level}
    ]
    #line(length: 100%, stroke: 0.3pt + rgb("#e2e8f0"))
  ],
  footer: [
    #line(length: 100%, stroke: 0.3pt + rgb("#e2e8f0"))
    #set text(size: 8pt, fill: rgb("#94a3b8"))
    #grid(columns: (1fr, auto))[
      {safe_topic}
    ][
      Side #counter(page).display("1 av 1", both: true)
    ]
  ]
)

#set text(font: ("Noto Sans", "Liberation Sans", "DejaVu Sans", "Arial"), size: 10.5pt, lang: "nb", hyphenate: true)
#set par(justify: true, leading: 0.7em, spacing: 1.1em)
#set list(indent: 1em)

// ─── FORSIDEN ──────────────────────────────────────────────────────────────
#block(fill: rgb("#1e3a8a"), inset: (x: 2em, y: 1.5em), radius: 8pt, width: 100%)[
  #text(fill: rgb("#93c5fd"), size: 10pt)[SEKVENSPLAN · {safe_subject} · {safe_level}]
  #v(0.4em)
  #text(fill: white, size: 20pt, weight: "bold")[{tittel}]
  #v(0.6em)
  #grid(columns: (auto, auto, auto), gutter: 1.5em)[
    #text(fill: rgb("#bfdbfe"), size: 10pt)[📅 {antall_uker} uker]
  ][
    #text(fill: rgb("#bfdbfe"), size: 10pt)[🏫 {safe_level}]
  ][
    #text(fill: rgb("#bfdbfe"), size: 10pt)[📘 {safe_subject}]
  ]
]

#v(1em)
// Lærerfelt
#grid(columns: (1fr, 1fr, 1fr), gutter: 0.8em)[
  #block(stroke: 0.5pt + gray, inset: 0.6em, radius: 3pt)[
    #text(size: 8pt, fill: gray)[Lærer]
    #v(1em)
    #line(length: 100%, stroke: 0.3pt + gray)
  ]
][
  #block(stroke: 0.5pt + gray, inset: 0.6em, radius: 3pt)[
    #text(size: 8pt, fill: gray)[Klasse]
    #v(1em)
    #line(length: 100%, stroke: 0.3pt + gray)
  ]
][
  #block(stroke: 0.5pt + gray, inset: 0.6em, radius: 3pt)[
    #text(size: 8pt, fill: gray)[Periode]
    #v(1em)
    #line(length: 100%, stroke: 0.3pt + gray)
  ]
]

#v(1em)
// Kompetansemål
#block(fill: rgb("#f0fdf4"), stroke: 0.5pt + rgb("#86efac"), inset: 1em, radius: 4pt)[
  #text(size: 10pt, weight: "bold")[✅ Kompetansemål (LK20)]
  #v(0.4em)
  {km_items}
]

#v(1em)
// Ukeoversikt
#text(size: 12pt, weight: "bold")[📅 Ukeoversikt]
#v(0.4em)
{overview_table}

// ─── TIMEKORT ──────────────────────────────────────────────────────────────
{lesson_cards}

// ─── AVSLUTTENDE VURDERING ────────────────────────────────────────────────
{avsl_section}
"""
    return compile_typst(typst_source)


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
