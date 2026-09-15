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
    return [MathIsland(m.start(), m.end(), next(g for g in m.groups() if g is not None).strip())
            for m in _MATH.finditer(text)]


def context_ranges(content: str) -> list[tuple[int, int, str]]:
    """An example has its own definitions; a solution inherits only its task."""
    ranges = []
    tasks = {}
    for m in re.finditer(r"\\begin\{(eksempel|taskbox)\}(.*?)\\end\{\1\}", content, re.S):
        ranges.append((m.start(), m.end(), m[0]))
        if m[1] == "taskbox":
            number = re.match(r"\{Oppgave\s+(\d+)\}", m[2])
            if number:
                tasks[number[1]] = m[0]
    solutions = re.search(r"\\section\*?\{(?:Løsningsforslag|Fasit)\}", content, re.I)
    if solutions:
        headings = list(re.finditer(r"\\textbf\{Oppgave\s+(\d+)\}", content[solutions.end():]))
        for index, heading in enumerate(headings):
            start = solutions.end() + heading.start()
            end = (solutions.end() + headings[index + 1].start()
                   if index + 1 < len(headings) else len(content))
            ranges.append((start, end, tasks.get(heading[1], "") + "\n" + content[start:end]))
    # Section context is used only outside the narrower example/task ranges.
    sections = list(re.finditer(r"\\(?:sub)*section\*?\{", content))
    for index, section in enumerate(sections):
        end = sections[index + 1].start() if index + 1 < len(sections) else len(content)
        text = content[section.start():end]
        text = re.sub(r"\\begin\{(eksempel|taskbox)\}.*?\\end\{\1\}", "", text, flags=re.S)
        ranges.append((section.start(), end, text))
    return ranges


def local_context(content: str, position: int, ranges: list[tuple[int, int, str]]) -> str:
    for start, end, text in ranges:
        if start <= position < end:
            return text
    return content
