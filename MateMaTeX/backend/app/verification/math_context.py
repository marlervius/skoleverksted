"""Read complete math islands and isolate examples and numbered solutions.

Offsets refer to the original text. In particular, a closing dollar must never
be reused as the opening delimiter of an equation spanning ordinary prose.
"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class MathIsland:
    start: int
    end: int
    text: str


_MATH = re.compile(
    r"(?<!\\)\$\$(.*?)(?<!\\)\$\$"
    r"|(?<!\\)\$(?!\$)((?:\\.|[^$\\])*)(?<!\\)\$"
    r"|\\\[(.*?)\\\]|\\\((.*?)\\\)",
    re.S,
)


def math_islands(content: str) -> list[MathIsland]:
    # Preserve offsets when removing comments, and preserve escaped percent.
    text = re.sub(r"(?m)(?<!\\)%[^\n]*", lambda m: " " * len(m[0]), content)
    islands = []
    for match in _MATH.finditer(text):
        group = next(i for i, value in enumerate(match.groups(), 1) if value is not None)
        raw = match[group]
        # Implications separate equations; they are never operands of '='.
        for part in re.finditer(r".+?(?=\\(?:Rightarrow|Leftrightarrow|implies|iff)\b|$)", raw, re.S):
            value = re.sub(r"^\\(?:Rightarrow|Leftrightarrow|implies|iff)\s*", "", part[0]).strip()
            if value:
                islands.append(MathIsland(match.start(group)+part.start(), match.start(group)+part.end(), value))
    # Worked solutions normally use align without dollar delimiters. Keep
    # annotation text separate and carry the previous expression over '&='.
    for block in re.finditer(r"\\begin\{(?:align\*?|aligned|equation\*?)\}(.*?)\\end\{(?:align\*?|aligned|equation\*?)\}", text, re.S):
        previous = ""
        for row in re.finditer(r"(.*?)(?:\\\\|\Z)", block[1], re.S):
            value = row[1].split("&&", 1)[0].replace("&", "").strip()
            value = re.split(r"\\(?:forklaring|text)\b", value, maxsplit=1)[0].strip()
            if not value:
                continue
            if value.startswith("="):
                value = previous + value
            for part in re.split(r"\\(?:Rightarrow|Leftrightarrow|implies|iff)\b", value):
                if part.strip():
                    islands.append(MathIsland(block.start(1)+row.start(), block.start(1)+row.end(), part.strip()))
            if "=" in value:
                previous = value.rsplit("=", 1)[-1].strip()
    return sorted(islands, key=lambda island: island.start)


def context_ranges(content: str) -> list[tuple[int, int, str]]:
    """An example has its own definitions; a solution inherits only its task."""
    ranges = []
    tasks = {}
    task_matches = {}
    for m in re.finditer(r"\\begin\{(eksempel|taskbox)\}(.*?)\\end\{\1\}", content, re.S):
        ranges.append((m.start(), m.end(), m[0]))
        if m[1] == "taskbox":
            number = re.match(r"\{Oppgave\s+(\d+)\}", m[2])
            if number:
                tasks[number[1]] = m[0]
                task_matches[number[1]] = m
    solutions = re.search(r"\\section\*?\{(?:Løsningsforslag|Fasit)\}", content, re.I)
    if solutions:
        headings = list(re.finditer(r"\\textbf\{Oppgave\s+(\d+)\}", content[solutions.end():]))
        for index, heading in enumerate(headings):
            start = solutions.end() + heading.start()
            end = (solutions.end() + headings[index + 1].start()
                   if index + 1 < len(headings) else len(content))
            ranges.append((start, end, tasks.get(heading[1], "") + "\n" + content[start:end]))
            task = task_matches.get(heading[1])
            if task:
                combined = task[0] + "\n" + content[start:end]
                # Both the question and its answer use the same evidence.
                ranges.insert(0, (task.start(), task.end(), combined))
                task_parts = _subparts(task[0])
                solution_parts = _subparts(content[start:end])
                if task_parts and solution_parts and set(task_parts) == set(solution_parts):
                    prefix = task[0][:min(v[0] for v in task_parts.values())]
                    for label, (part_start, part_end) in task_parts.items():
                        sol_start, sol_end = solution_parts[label]
                        scope = prefix + "\n" + task[0][part_start:part_end] + "\n" + content[start+sol_start:start+sol_end]
                        ranges.insert(0, (task.start()+part_start, task.start()+part_end, scope))
                        ranges.insert(0, (start+sol_start, start+sol_end, scope))
    # Section context is used only outside the narrower example/task ranges.
    sections = list(re.finditer(r"\\(?:sub)*section\*?\{", content))
    for index, section in enumerate(sections):
        end = sections[index + 1].start() if index + 1 < len(sections) else len(content)
        text = content[section.start():end]
        text = re.sub(r"\\begin\{(eksempel|taskbox)\}.*?\\end\{\1\}", "", text, flags=re.S)
        ranges.append((section.start(), end, text))
    return ranges


def _subparts(text: str) -> dict[str, tuple[int, int]]:
    """Find printed a)/b) or enumerate items without matching inside math."""
    visible = list(text)
    for island in math_islands(text):
        visible[island.start:island.end] = " " * (island.end - island.start)
    matches = list(re.finditer(r"\\item(?:\[[^\]]*\])?|(?<!\w)([a-h])\)", "".join(visible)))
    return {
        match[1] or chr(97 + index): (match.start(), matches[index+1].start() if index+1 < len(matches) else len(text))
        for index, match in enumerate(matches)
    }


def local_context(content: str, position: int, ranges: list[tuple[int, int, str]]) -> str:
    for start, end, text in ranges:
        if start <= position < end:
            return text
    return content
