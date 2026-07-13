r"""
Table Validator — rule-based post-processing of LaTeX tabular environments.

No LLM calls. Runs after TikZ Validator, before LaTeX Validator.
Catches and auto-fixes the most common AI table mistakes.

Rules applied (in order):
1.  Convert \hline to booktabs (\toprule / \midrule / \bottomrule)
    -- Exception: posisjonsskjema (positional tables with c|c|c column spec) kept as-is
2.  Remove vertical bars | from column specs
    -- Exception: posisjonsskjema column specs kept as-is
3.  Ensure tabular is wrapped in \begin{center}...\end{center}
4.  Fix column count mismatch (too many & in a row)
5.  Add missing booktabs structure to completely unstructured tables
6.  Ensure tabular environments inside tcolorbox/taskbox are NOT wrapped
    in an extra center (tcolorbox handles centering)
7.  Log a summary of all changes made
"""

from __future__ import annotations

import re
from datetime import datetime

import structlog

from app.models.state import AgentRole, AgentStep, PipelineState

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_posisjonsskjema(tabular_text: str) -> bool:
    r"""
    Posisjonsskjema (place-value / decimal position tables) are the one
    legitimate exception where | and \hline are allowed.

    We detect them by:
    - Column spec contains ONLY c|c (all cells centred, separated by bars)
    - OR table content contains Norwegian position headers like
      'Hundrer', 'Tiere', 'Enere', 'Tideler', 'Hundredeler'
    """
    # Column spec like {c|c|c|c|c} — all c's separated by |
    col_spec_m = re.search(r'\\begin\{tabular\}\{([^}]+)\}', tabular_text)
    if col_spec_m:
        spec = col_spec_m.group(1)
        # Pure position spec: only c and | characters
        if re.fullmatch(r'[c|]+', spec):
            return True

    # Content heuristic: Norwegian decimal position header words
    position_words = ('Hundrer', 'Tiere', 'Enere', 'Tideler', 'Hundredeler',
                      'Tusener', 'Titusen', 'Hundreder')
    for word in position_words:
        if word in tabular_text:
            return True

    return False


def _count_columns_from_spec(spec: str) -> int:
    """Count the number of columns from a tabular column spec string."""
    # Remove alignment chars that don't count as columns: @{}, >{}, <{}, p{}, *{}
    cleaned = re.sub(r'[@><]\{[^}]*\}', '', spec)
    cleaned = re.sub(r'\*\{\d+\}\{[^}]*\}', '', cleaned)  # *{N}{spec}
    # Remove | and space
    cleaned = cleaned.replace('|', '').replace(' ', '')
    # Count remaining column letters: l, r, c, p, m, b, X
    return len(re.findall(r'[lrcpmbX]', cleaned))


# ---------------------------------------------------------------------------
# Rule 1 + 2: Convert \hline to booktabs AND strip | from column specs
# ---------------------------------------------------------------------------

def _fix_hline_and_pipes(body: str) -> tuple[str, int]:
    r"""
    For each tabular environment that is NOT a posisjonsskjema:
    - Replace column spec pipes | with nothing
    - Convert \hline sequence to \toprule / \midrule / \bottomrule pattern

    Strategy:
    - First \hline after \begin{tabular}{...} → \toprule
    - Last \hline before \end{tabular} → \bottomrule
    - All remaining \hline → \midrule
    """
    count = 0

    tabular_re = re.compile(
        r'(\\begin\{tabular\}\{)([^}]+)(\})(.*?)(\\end\{tabular\})',
        re.DOTALL,
    )

    def fix_table(m: re.Match) -> str:
        nonlocal count
        begin_tag = m.group(1)
        col_spec = m.group(2)
        close_brace = m.group(3)
        content = m.group(4)
        end_tag = m.group(5)

        full = m.group(0)

        if _is_posisjonsskjema(full):
            return full  # Leave posisjonsskjema intact

        changed = False

        # --- Fix column spec: remove | ---
        new_spec = col_spec.replace('|', '')
        if new_spec != col_spec:
            col_spec = new_spec
            changed = True

        # --- Fix \hline → booktabs ---
        hlines = list(re.finditer(r'\\hline', content))
        if hlines:
            changed = True
            if len(hlines) == 1:
                # Only one \hline — treat as \toprule
                content = content.replace('\\hline', '\\toprule', 1)
            elif len(hlines) == 2:
                # Two \hlines — top and bottom
                content = content[:hlines[0].start()] + '\\toprule' + content[hlines[0].end():]
                # Recalculate positions after first replacement
                hlines2 = list(re.finditer(r'\\hline', content))
                if hlines2:
                    last = hlines2[-1]
                    content = content[:last.start()] + '\\bottomrule' + content[last.end():]
            else:
                # Three or more: first → \toprule, last → \bottomrule, rest → \midrule
                # Work backwards to preserve positions
                positions = [(h.start(), h.end()) for h in hlines]
                replacements = {}
                replacements[positions[0]] = '\\toprule'
                replacements[positions[-1]] = '\\bottomrule'
                for pos in positions[1:-1]:
                    replacements[pos] = '\\midrule'

                # Rebuild content with replacements (reverse order to preserve indices)
                for (start, end) in sorted(replacements.keys(), reverse=True):
                    content = content[:start] + replacements[(start, end)] + content[end:]

        if changed:
            count += 1
            return begin_tag + col_spec + close_brace + content + end_tag

        return full

    new_body = tabular_re.sub(fix_table, body)
    return new_body, count


# ---------------------------------------------------------------------------
# Rule 3: Ensure tabular is wrapped in \begin{center}...\end{center}
# ---------------------------------------------------------------------------

def _wrap_tabular_in_center(body: str) -> tuple[str, int]:
    """
    Any \begin{tabular} that is not already inside \begin{center} should
    be wrapped. Exception: tabular inside tcolorbox environments (taskbox,
    definisjon, eksempel, merk, losning) — tcolorbox centres content itself.

    We detect "inside tcolorbox" by checking the 400 chars before the tabular
    for an unclosed tcolorbox begin tag.
    """
    count = 0
    tcolorbox_envs = ('taskbox', 'definisjon', 'eksempel', 'definitionbox',
                      'examplebox', 'tipbox', 'merk', 'losning', 'tcolorbox')

    tabular_re = re.compile(
        r'\\begin\{tabular\}.*?\\end\{tabular\}',
        re.DOTALL,
    )

    output_parts = []
    pos = 0

    for m in tabular_re.finditer(body):
        tab_start, tab_end = m.start(), m.end()
        tab_text = m.group(0)

        output_parts.append(body[pos:tab_start])

        # Check preceding 600 chars for unclosed center / tcolorbox
        preceding = body[max(0, tab_start - 600):tab_start]

        # Already inside \begin{center}?
        center_opens = len(re.findall(r'\\begin\{center\}', preceding))
        center_closes = len(re.findall(r'\\end\{center\}', preceding))
        inside_center = center_opens > center_closes

        # Inside a tcolorbox-derived env?
        inside_tcolorbox = any(
            len(re.findall(rf'\\begin\{{{env}\}}', preceding)) >
            len(re.findall(rf'\\end\{{{env}\}}', preceding))
            for env in tcolorbox_envs
        )

        if inside_center or inside_tcolorbox:
            output_parts.append(tab_text)
        else:
            output_parts.append('\\begin{center}\n' + tab_text + '\n\\end{center}')
            count += 1

        pos = tab_end

    output_parts.append(body[pos:])
    return ''.join(output_parts), count


# ---------------------------------------------------------------------------
# Rule 4: Fix rows with too many cells (& count mismatch)
# ---------------------------------------------------------------------------

def _fix_column_count_mismatch(body: str) -> tuple[str, int]:
    """
    For each tabular, detect the declared column count from the column spec.
    Then scan each data row: if a row has MORE cells than columns, truncate
    the excess. If a row has FEWER cells, pad with empty cells.

    Only fixes rows that are clearly wrong (difference > 0). Conservative:
    does not touch rows inside multicolumn commands.

    A 'row' is defined as content between \\ (double backslash) separators.
    """
    count = 0

    tabular_re = re.compile(
        r'(\\begin\{tabular\}\{)([^}]+)(\})(.*?)(\\end\{tabular\})',
        re.DOTALL,
    )

    def fix_table_rows(m: re.Match) -> str:
        nonlocal count
        begin_tag = m.group(1)
        col_spec = m.group(2)
        close_brace = m.group(3)
        content = m.group(4)
        end_tag = m.group(5)

        full = m.group(0)

        if _is_posisjonsskjema(full):
            return full

        num_cols = _count_columns_from_spec(col_spec)
        if num_cols == 0:
            return full

        # Split content into rows by \\
        # Keep the \\ in the output by splitting on \\\\ and re-joining
        row_sep = re.compile(r'(\\\\(?:\[[^\]]*\])?)')
        parts = row_sep.split(content)

        # parts alternates: [row_content, \\, row_content, \\, ...]
        changed_here = False
        new_parts = []

        for i, part in enumerate(parts):
            if row_sep.fullmatch(part):
                # This is a \\ separator — keep as-is
                new_parts.append(part)
                continue

            # Skip booktabs rules and empty/whitespace
            stripped = part.strip()
            if not stripped or re.match(
                r'^\\(toprule|midrule|bottomrule|hline)\s*$', stripped
            ):
                new_parts.append(part)
                continue

            # Skip rows containing \multicolumn (complex — leave alone)
            if '\\multicolumn' in part:
                new_parts.append(part)
                continue

            # Count cells in this row
            cells = part.split('&')
            actual_cols = len(cells)

            if actual_cols == num_cols:
                new_parts.append(part)
                continue

            # Too many columns: trim trailing empty cells
            if actual_cols > num_cols:
                # Only trim if the extra cells are empty/whitespace
                excess = cells[num_cols:]
                if all(c.strip() == '' for c in excess):
                    cells = cells[:num_cols]
                    new_parts.append('&'.join(cells))
                    changed_here = True
                    continue

            # Too few: pad with empty cells (don't pad — less destructive to leave as-is)
            new_parts.append(part)

        if changed_here:
            count += 1
            return begin_tag + col_spec + close_brace + ''.join(new_parts) + end_tag

        return full

    new_body = tabular_re.sub(fix_table_rows, body)
    return new_body, count


# ---------------------------------------------------------------------------
# Rule 5: Ensure \toprule/\midrule/\bottomrule present if booktabs used
# ---------------------------------------------------------------------------

def _ensure_booktabs_structure(body: str) -> tuple[str, int]:
    r"""
    If a tabular has NO \hline and NO \toprule/\midrule/\bottomrule,
    it may be missing structure entirely. Add a minimal toprule + bottomrule.

    Only adds rules to tables that have at least one data row (\\).
    Does not touch posisjonsskjema.
    """
    count = 0

    tabular_re = re.compile(
        r'(\\begin\{tabular\}\{)([^}]+)(\})(.*?)(\\end\{tabular\})',
        re.DOTALL,
    )

    def add_rules(m: re.Match) -> str:
        nonlocal count
        full = m.group(0)
        begin_tag = m.group(1)
        col_spec = m.group(2)
        close_brace = m.group(3)
        content = m.group(4)
        end_tag = m.group(5)

        if _is_posisjonsskjema(full):
            return full

        has_rules = any(kw in content for kw in
                        ('\\toprule', '\\midrule', '\\bottomrule', '\\hline'))
        has_rows = '\\\\' in content

        if has_rules or not has_rows:
            return full

        # Add minimal toprule after opening, bottomrule before closing
        # Find first \\ to place toprule before header row
        first_row_end = content.find('\\\\')
        if first_row_end == -1:
            return full

        new_content = (
            '\n\\toprule\n'
            + content[:first_row_end + 2]   # header row + \\
            + '\n\\midrule'
            + content[first_row_end + 2:]
            + '\\bottomrule\n'
        )
        count += 1
        return begin_tag + col_spec + close_brace + new_content + end_tag

    new_body = tabular_re.sub(add_rules, body)
    return new_body, count


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

def run_table_validator(state: PipelineState) -> PipelineState:
    """
    Rule-based table validator / auto-fixer.

    Reads:  state.edited_latex_body
    Writes: state.edited_latex_body (cleaned), state.steps
    """
    step = AgentStep(agent=AgentRole.TABLE_VALIDATOR)
    state.current_agent = AgentRole.TABLE_VALIDATOR

    logger.info("table_validator_start", job_id=state.job_id)

    try:
        body = state.edited_latex_body or state.verified_latex_body or state.raw_latex_body

        fixes: list[str] = []

        # Rule 1+2: Convert \hline → booktabs + remove | from column specs
        body, n = _fix_hline_and_pipes(body)
        if n:
            fixes.append(f"Converted \\hline→booktabs and removed pipes in {n} table(s)")

        # Rule 3: Wrap bare tabular in \begin{center}
        body, n = _wrap_tabular_in_center(body)
        if n:
            fixes.append(f"Wrapped {n} tabular(s) in \\begin{{center}}")

        # Rule 4: Fix column count mismatch
        body, n = _fix_column_count_mismatch(body)
        if n:
            fixes.append(f"Trimmed excess cells in {n} table row(s)")

        # Rule 5: Add missing booktabs structure
        body, n = _ensure_booktabs_structure(body)
        if n:
            fixes.append(f"Added booktabs rules to {n} unstructured table(s)")

        state.edited_latex_body = body.strip()

        summary = "; ".join(fixes) if fixes else "No table issues found"
        step.output_summary = summary

        logger.info(
            "table_validator_complete",
            job_id=state.job_id,
            fixes=fixes,
            num_fixes=len(fixes),
        )

    except Exception as e:
        step.error = str(e)
        logger.error("table_validator_failed", job_id=state.job_id, error=str(e))
        # Non-fatal: leave body unchanged

    finally:
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        state.steps.append(step)

    return state
