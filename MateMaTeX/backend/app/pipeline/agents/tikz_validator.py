"""
TikZ Figure Validator — rule-based post-processing of LaTeX body.

No LLM calls. Runs after Editor, before LaTeX Validator.
Catches the most common AI figure mistakes and either fixes them
automatically or replaces the broken figure with a safe fallback.

Rules applied (in order):
1. Strip any remaining \\includegraphics
2. Fix double-caption / orphaned-caption bug (Figur N: ... after \\end{figure})
3. Move figures out of taskbox environments
4. Ensure every \\begin{figure} has [H] placement
5. Add \\centering where missing
6. Wrap bare \\begin{tikzpicture} in figure environment
7. Wrap bare \\begin{axis} (pgfplots) in figure+tikzpicture
8. Replace known bad Pytagoras patterns with \\MMArettvinklet macro
9. Log a summary of all changes made
"""

from __future__ import annotations

import re
from datetime import datetime

import structlog

from app.models.state import AgentRole, AgentStep, PipelineState

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Individual fix functions
# ---------------------------------------------------------------------------

def _strip_includegraphics(body: str) -> tuple[str, int]:
    """Remove all \\includegraphics commands."""
    pattern = re.compile(
        r'\\includegraphics\s*(?:\[.*?\])?\s*\{[^}]*\}',
        re.DOTALL,
    )
    new_body, count = pattern.subn('', body)
    return new_body, count


_TITLED_BOX_ENVS = (
    r'(?:eksempel|examplebox|definisjon|definitionbox|regel|setning|merk|'
    r'tipbox|losning|vurdering|husk|vanligfeil|utforsk|laeringsmaal|oppsummering)'
)


def _brace_box_titles(body: str) -> tuple[str, int]:
    r"""
    Wrap unbraced title values in braces.

    \begin{eksempel}[title=Løse $\frac{dy}{dx} = 2xy$] breaks pgfkeys: the `=`
    inside the value splits the key/value pair and compilation fails. With
    braces — [title={...}] — any content is safe.
    """
    count = 0
    pattern = re.compile(
        r'(\\begin\{' + _TITLED_BOX_ENVS + r'\}\[title=)([^{\]][^\]]*)(\])'
    )

    def repl(m: re.Match) -> str:
        nonlocal count
        value = m.group(2)
        # Plain titles without special characters parse fine — leave them.
        if not re.search(r'[=$\\,]', value):
            return m.group(0)
        # Value contains an unmatched [ — the real title extends past our
        # match (e.g. "Intervallet [2, 5]"); too risky to rewrite.
        if value.count('[') != value.count(']'):
            return m.group(0)
        count += 1
        return f'{m.group(1)}{{{value}}}{m.group(3)}'

    return pattern.sub(repl, body), count


def _wrap_bare_tikzpicture(body: str) -> tuple[str, int]:
    """
    Wrap any \\begin{tikzpicture}...\\end{tikzpicture} that is NOT already
    inside a figure environment.
    """
    count = 0

    # Find all tikzpicture spans and check if they are inside figure
    result = []
    pos = 0
    tikz_start_re = re.compile(r'\\begin\{tikzpicture\}')
    tikz_end_re = re.compile(r'\\end\{tikzpicture\}')

    i = 0
    text = body
    output_parts = []

    while True:
        m_start = tikz_start_re.search(text, i)
        if not m_start:
            output_parts.append(text[i:])
            break

        # Find matching end
        m_end = tikz_end_re.search(text, m_start.end())
        if not m_end:
            output_parts.append(text[i:])
            break

        # Check if there is a \begin{figure} before this tikzpicture (within 500 chars)
        preceding = text[max(0, m_start.start()-500):m_start.start()]
        # Count begin{figure} vs end{figure} in preceding context
        fig_opens = len(re.findall(r'\\begin\{figure\}', preceding))
        fig_closes = len(re.findall(r'\\end\{figure\}', preceding))
        inside_figure = fig_opens > fig_closes

        if inside_figure:
            # Already wrapped — pass through as-is
            output_parts.append(text[i:m_end.end()])
        else:
            # Not wrapped — add figure wrapper. No caption: a generic
            # "Figur"-caption looks worse than none and pollutes numbering.
            tikz_block = text[m_start.start():m_end.end()]
            wrapped = (
                '\\begin{figure}[H]\n'
                '\\centering\n'
                + tikz_block
                + '\n\\end{figure}'
            )
            output_parts.append(text[i:m_start.start()])
            output_parts.append(wrapped)
            count += 1

        i = m_end.end()

    return ''.join(output_parts), count


def _wrap_bare_axis(body: str) -> tuple[str, int]:
    """
    Wrap any \\begin{axis}...\\end{axis} that is NOT inside a figure.
    """
    count = 0
    text = body
    output_parts = []
    i = 0
    axis_start_re = re.compile(r'\\begin\{axis\}')
    axis_end_re = re.compile(r'\\end\{axis\}')

    while True:
        m_start = axis_start_re.search(text, i)
        if not m_start:
            output_parts.append(text[i:])
            break

        m_end = axis_end_re.search(text, m_start.end())
        if not m_end:
            output_parts.append(text[i:])
            break

        # Check for surrounding figure env — need tikzpicture wrapping axis too
        preceding = text[max(0, m_start.start()-600):m_start.start()]
        fig_opens = len(re.findall(r'\\begin\{figure\}', preceding))
        fig_closes = len(re.findall(r'\\end\{figure\}', preceding))
        inside_figure = fig_opens > fig_closes

        if inside_figure:
            output_parts.append(text[i:m_end.end()])
        else:
            axis_block = text[m_start.start():m_end.end()]
            wrapped = (
                '\\begin{figure}[H]\n'
                '\\centering\n'
                '\\begin{tikzpicture}\n'
                + axis_block
                + '\n\\end{tikzpicture}\n'
                '\\end{figure}'
            )
            output_parts.append(text[i:m_start.start()])
            output_parts.append(wrapped)
            count += 1

        i = m_end.end()

    return ''.join(output_parts), count


def _replace_pytagoras_squares(body: str) -> tuple[str, int]:
    """
    Detect the specific anti-pattern where AI draws squares on ALL FOUR sides of a
    Pythagorean triangle (a^2, b^2, c^2 as filled rectangles extending far off-page).

    This is a very conservative heuristic — only triggers when ALL of:
    1. Figure has all three square-area labels WITH numeric values (e.g. $a^2 = 16$)
    2. Figure has many nodes (10+) suggesting squares are drawn as separate shapes
    3. Figure has extreme out-of-bounds coordinates (abs > 9)

    Avoids false positives on creative scenes, 3D figures, vector diagrams, etc.
    """
    count = 0

    fig_re = re.compile(
        r'\\begin\{figure\}.*?\\end\{figure\}',
        re.DOTALL,
    )

    def replace_figure(m: re.Match) -> str:
        nonlocal count
        fig_text = m.group(0)

        # Must have a tikzpicture
        if '\\begin{tikzpicture}' not in fig_text:
            return fig_text

        # Must have all three Pythagorean area labels WITH numeric values
        # e.g. "$a^2 = 16$" or "node at (...) {$a^2 = 9$}"
        has_a2 = bool(re.search(r'[$]a\^2\s*=\s*\d', fig_text))
        has_b2 = bool(re.search(r'[$]b\^2\s*=\s*\d', fig_text))
        has_c2 = bool(re.search(r'[$]c\^2\s*=\s*\d', fig_text))

        if not (has_a2 and has_b2 and has_c2):
            return fig_text  # Not the Pytagoras-squares anti-pattern

        # Must also have many node/draw commands (squares take many lines)
        node_count = len(re.findall(r'\\(?:node|draw|fill)\b', fig_text))
        if node_count < 10:
            return fig_text  # Too few elements — not the squares pattern

        # Must have coordinates with extreme out-of-bounds (abs > 9)
        # Normal scenes with people/flags/etc. may have x up to 16 (width), but
        # the Pytagoras squares pattern specifically creates negative y < -8
        coords = re.findall(
            r'\((-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\)',
            fig_text,
        )
        extreme_oob = any(
            abs(float(x)) > 9 or abs(float(y)) > 9
            for x, y in coords
        )

        if not extreme_oob:
            return fig_text  # Coordinates within bounds — leave it alone

        # All conditions met: this is the problematic squares-on-all-sides pattern
        caption_m = re.search(r'\\caption\{([^}]*)\}', fig_text)
        caption = caption_m.group(1) if caption_m else 'Rettvinklet trekant med Pytagoras\\textquotesingle{} setning.'
        count += 1
        return (
            '\\begin{figure}[H]\n'
            '\\centering\n'
            '\\MMArettvinklet{3}{4}{5}\n'
            f'\\caption{{{caption}}}\n'
            '\\end{figure}'
        )

    new_body = fig_re.sub(replace_figure, body)
    return new_body, count


def _fix_double_caption(body: str) -> tuple[str, int]:
    """
    Fix the double-figure / double-caption bug where AI generates:

    Pattern A (most common — seen in tettt.pdf and vektorer.pdf):
        \\begin{figure}[H]
          ...tikzpicture or axis...
        \\caption{Figur}          <- generic placeholder
        \\end{figure}
                                  <- blank lines
        Figur N: Real caption.   <- orphaned line OUTSIDE figure

    Pattern B:
        \\begin{figure}[H]...\\caption{Figur}\\end{figure}
                                  <- blank lines
        \\begin{figure}[H]
        Figur N: Real caption.   <- orphaned figure-env, no tikzpicture inside
        \\end{figure}

    Two-pass approach:
    Pass 1: Remove orphaned figure-envs that contain only a caption line (Pattern B preprocess).
    Pass 2: Replace \\caption{Figur} with the real orphaned caption line (Pattern A).
    """
    count = 0

    # --- Pass 1: Remove figure-envs that contain ONLY a "Figur N: ..." line ---
    # These are the orphaned wrappers from Pattern B
    def remove_caption_only_figures(text: str) -> tuple[str, int]:
        """
        Find and remove figure environments that contain no tikzpicture/axis,
        only a bare text line starting with 'Figur N:'.
        Return (modified_text, caption_extracted) where caption_extracted is
        a dict mapping position → real caption text for use in Pass 2.
        """
        removed = 0
        # Match figure envs that have NO tikzpicture or axis inside
        # \begin{figure} optionally followed by [H] or similar specifier, then content
        fig_re = re.compile(r'\\begin\{figure\}(?:\[[^\]]*\])?(.*?)\\end\{figure\}', re.DOTALL)

        def check_and_remove(m: re.Match) -> str:
            nonlocal removed
            content = m.group(1)
            if '\\begin{tikzpicture}' in content or '\\begin{axis}' in content:
                return m.group(0)  # Real figure — keep it
            # Check if it's an orphaned caption-only wrapper
            cap_m = re.search(r'Figur\s+\d+\s*:\s*([^\n]+)', content)
            if cap_m:
                removed += 1
                # Convert the figure-env wrapper into a bare orphaned caption line
                # so that Pass 2 (fix_orphaned_lines) can pick it up
                return '\n' + cap_m.group(0).strip()
            return m.group(0)

        new_text = fig_re.sub(check_and_remove, text)
        return new_text, removed

    # --- Pass 2: Replace \caption{Figur} with orphaned standalone caption lines ---
    def fix_orphaned_lines(text: str) -> tuple[str, int]:
        """
        Find \\caption{Figur} (or Graf/empty) inside a figure, followed after
        \\end{figure} by a standalone 'Figur N: Real text.' line, and merge them.
        """
        fixed = 0
        fig_re = re.compile(r'\\begin\{figure\}.*?\\end\{figure\}', re.DOTALL)

        # Generic words that indicate a placeholder caption
        _GENERIC_CAPTIONS = {'figur', 'graf', 'figur.', 'graf.', '', 'figure', 'graph'}

        def has_generic_caption(fig_text: str) -> bool:
            m = re.search(r'\\caption\{([^}]*)\}', fig_text)
            if not m:
                return False
            return m.group(1).strip().lower() in _GENERIC_CAPTIONS

        output = []
        pos = 0

        for m in fig_re.finditer(text):
            fig_start, fig_end = m.start(), m.end()
            fig_text = m.group(0)
            output.append(text[pos:fig_start])

            if has_generic_caption(fig_text):
                rest = text[fig_end:]
                ma = re.match(r'\s*\n+Figur\s+\d+\s*:\s*([^\n]+)', rest)
                if ma:
                    real_caption = ma.group(1).strip()
                    fixed_fig = re.sub(
                        r'\\caption\{[^}]*\}',
                        '\\\\caption{' + real_caption + '}',
                        fig_text,
                        count=1,
                    )
                    output.append(fixed_fig)
                    pos = fig_end + ma.end()
                    fixed += 1
                    continue

            output.append(fig_text)
            pos = fig_end

        output.append(text[pos:])
        return ''.join(output), fixed

    # --- Pass 3: Remove remaining orphaned "Figur N: ..." lines that are
    #             still floating outside any figure environment (generic or not).
    def remove_orphaned_figur_lines(text: str) -> tuple[str, int]:
        """
        After passes 1 and 2, any remaining bare lines like
            'Figur 2: Grafen til ...'
        outside a figure environment are spurious and must be removed.
        """
        removed = 0

        # Build a set of positions that are inside a figure env
        figure_ranges = []
        for fm in re.finditer(r'\\begin\{figure\}.*?\\end\{figure\}', text, re.DOTALL):
            figure_ranges.append((fm.start(), fm.end()))

        def is_inside_figure(pos: int) -> bool:
            return any(s <= pos < e for s, e in figure_ranges)

        def remove_line(m: re.Match) -> str:
            nonlocal removed
            if not is_inside_figure(m.start()):
                removed += 1
                return ''
            return m.group(0)

        # Match lines like "Figur 2: something" or "Figur 2: Figur"
        pattern = re.compile(r'^Figur\s+\d+\s*:[^\n]+$', re.MULTILINE)
        new_text = pattern.sub(remove_line, text)
        return new_text, removed

    body, n1 = remove_caption_only_figures(body)
    body, n2 = fix_orphaned_lines(body)
    body, n3 = remove_orphaned_figur_lines(body)
    count = n1 + n2 + n3
    return body, count


def _move_figures_out_of_taskbox(body: str) -> tuple[str, int]:
    """
    Detect figure environments nested inside taskbox and move them AFTER
    the closing \\end{taskbox}.

    The AI sometimes places \\begin{figure}...\\end{figure} inside
    \\begin{taskbox}{...}...\\end{taskbox}, which breaks tcolorbox layout.

    Strategy: for each taskbox, extract any embedded figures and append
    them immediately after \\end{taskbox}.
    """
    count = 0

    taskbox_re = re.compile(
        r'(\\begin\{taskbox\}\{[^}]*\})(.*?)(\\end\{taskbox\})',
        re.DOTALL,
    )
    figure_re = re.compile(
        r'\\begin\{figure\}.*?\\end\{figure\}',
        re.DOTALL,
    )

    def extract_figures(m: re.Match) -> str:
        nonlocal count
        open_tag = m.group(1)
        content = m.group(2)
        close_tag = m.group(3)

        # Find all figures inside taskbox
        figures_found = figure_re.findall(content)
        if not figures_found:
            return m.group(0)

        # Remove figures from inside taskbox content
        cleaned_content = figure_re.sub('', content)
        # Collapse excess blank lines created by removal
        cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)

        count += len(figures_found)
        figures_block = '\n\n' + '\n\n'.join(figures_found)
        return open_tag + cleaned_content + close_tag + figures_block

    new_body = taskbox_re.sub(extract_figures, body)
    return new_body, count


def _fix_figure_placement(body: str) -> tuple[str, int]:
    """
    Ensure all \\begin{figure} have [H] placement specifier.
    """
    pattern = re.compile(r'\\begin\{figure\}(?!\[)')
    new_body, count = pattern.subn(r'\\begin{figure}[H]', body)
    return new_body, count


def _add_missing_centering(body: str) -> tuple[str, int]:
    """
    Add \\centering after \\begin{figure}[H] if missing.
    """
    count = 0

    def add_centering(m: re.Match) -> str:
        nonlocal count
        full = m.group(0)
        # Check if centering is already present
        after = full[len('\\begin{figure}[H]'):]
        if '\\centering' not in after[:60]:
            count += 1
            return '\\begin{figure}[H]\n\\centering'
        return full

    pattern = re.compile(r'\\begin\{figure\}\[H\]')
    new_body = pattern.sub(add_centering, body)
    return new_body, count


def _fix_quoted_math_in_tikz(body: str) -> tuple[str, int]:
    """
    Fix ``"$\\alpha$"`` style labels inside TikZ (breaks parsing → error at
    ``\\end{tikzpicture}``).
    """
    count = 0
    tikz_re = re.compile(
        r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}",
        re.DOTALL,
    )

    def fix_block(m: re.Match) -> str:
        nonlocal count
        block = m.group(0)
        new = re.sub(r'"(\$.*?\$)"', r"\1", block)
        new = re.sub(r'"\\?\$([^"]*?)\\?\$"', r"$\1$", new)
        if new != block:
            count += 1
        return new

    return tikz_re.sub(fix_block, body), count


def strip_tikz_and_plots(body: str) -> str:
    """Remove TikZ/pgfplots blocks when compilation cannot be salvaged."""
    body = re.sub(
        r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}",
        "% [Figur fjernet — kunne ikke kompileres]",
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"\\begin\{axis\}.*?\\end\{axis\}",
        "% [Graf fjernet — kunne ikke kompileres]",
        body,
        flags=re.DOTALL,
    )
    return body


def sanitize_latex_body(body: str) -> tuple[str, list[str]]:
    """
    Run all rule-based TikZ/figure fixes on a LaTeX body.

    Used by the pipeline TikZ validator and by export/compile paths that
    bypass the graph.
    """
    fixes: list[str] = []

    body, n = _strip_includegraphics(body)
    if n:
        fixes.append(f"Removed {n} \\includegraphics")

    body, n = _brace_box_titles(body)
    if n:
        fixes.append(f"Braced {n} box title(s) with special characters")

    body, n = _fix_quoted_math_in_tikz(body)
    if n:
        fixes.append(f"Fixed quoted math in {n} tikzpicture(s)")

    body, n = _fix_double_caption(body)
    if n:
        fixes.append(f"Fixed {n} double-caption figure(s)")

    body, n = _move_figures_out_of_taskbox(body)
    if n:
        fixes.append(f"Moved {n} figure(s) out of taskbox")

    body, n = _fix_figure_placement(body)
    if n:
        fixes.append(f"Added [H] to {n} figure(s)")

    body, n = _add_missing_centering(body)
    if n:
        fixes.append(f"Added \\centering to {n} figure(s)")

    body, n = _wrap_bare_tikzpicture(body)
    if n:
        fixes.append(f"Wrapped {n} bare tikzpicture(s)")

    body, n = _wrap_bare_axis(body)
    if n:
        fixes.append(f"Wrapped {n} bare axis environment(s)")

    body, n = _replace_pytagoras_squares(body)
    if n:
        fixes.append(f"Replaced {n} Pytagoras figure(s) with macro")

    return body.strip(), fixes


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

def run_tikz_validator(state: PipelineState) -> PipelineState:
    """
    Rule-based TikZ figure validator / auto-fixer.

    Reads:  state.edited_latex_body
    Writes: state.edited_latex_body (cleaned), state.steps
    """
    step = AgentStep(agent=AgentRole.TIKZ_VALIDATOR)
    state.current_agent = AgentRole.TIKZ_VALIDATOR

    logger.info("tikz_validator_start", job_id=state.job_id)

    try:
        body = state.edited_latex_body or state.verified_latex_body or state.raw_latex_body
        body, fixes = sanitize_latex_body(body)
        state.edited_latex_body = body

        summary = "; ".join(fixes) if fixes else "No changes needed"
        step.output_summary = summary
        logger.info(
            "tikz_validator_complete",
            job_id=state.job_id,
            fixes=fixes,
            num_fixes=len(fixes),
        )

    except Exception as e:
        step.error = str(e)
        logger.error("tikz_validator_failed", job_id=state.job_id, error=str(e))
        # Non-fatal: leave body unchanged

    finally:
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        state.steps.append(step)

    return state
