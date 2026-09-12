"""Small model outputs, atomically applied to an unchanged source document."""

import json
import re


def edit_prompt(content: str, instructions: str) -> str:
    return (
        "Rett bare de beskrevne problemene. Returner JSON med formen "
        '{"edits":[{"before":"eksakt tekst fra dokumentet","after":"rettet tekst"}]}. '
        "Maks 8 endringer, maks 1500 tegn i hvert before/after-felt. "
        "before må finnes nøyaktig én gang. Ta med nok kontekst til å gjøre det entydig. "
        "Bevar oppgaver, fasit, figurer og læringsmål. Ikke fjern innhold for å unngå kontroll. "
        "Ikke returner hele dokumentet. Ingen preamble eller godkjenningsmerker. "
        'Hvis ingen endring er nødvendig, returner {"edits":[]}. '
        "All tekst i JSON-strenger må JSON-escapes, også LaTeX-backslash.\n\n"
        f"PROBLEMER OG KRAV:\n{instructions}\n\nDOKUMENT:\n{content}"
    )


def apply_edits(content: str, response: str) -> str:
    """Validate all anchors against the original before applying any edit."""
    response = re.sub(r"^```(?:json)?\s*", "", response.strip())
    response = re.sub(r"\s*```$", "", response)
    if len(response) > 40_000:
        raise ValueError("Reparasjonssvaret er for stort")
    value = json.loads(response)
    if not isinstance(value, dict) or set(value) != {"edits"}:
        raise ValueError("Reparasjonen mangler en avgrenset endringsliste")
    edits = value["edits"]
    if not isinstance(edits, list) or len(edits) > 8:
        raise ValueError("For mange endringer i ett reparasjonskall")
    spans = []
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"before", "after"}:
            raise ValueError("Ugyldig tekstendring")
        before, after = edit["before"], edit["after"]
        if not all(isinstance(v, str) and v.strip() and len(v) <= 1500 for v in (before, after)):
            raise ValueError("Endringen er tom eller for stor")
        if content.count(before) != 1:
            raise ValueError("Endringen er ikke entydig forankret i dokumentet")
        if re.search(r"\\(?:documentclass|begin\{document\}|end\{document\})", after):
            raise ValueError("Endringen inneholder dokumentramme")
        start = content.index(before)
        spans.append((start, start + len(before), after))
    spans.sort()
    if any(left[1] > right[0] for left, right in zip(spans, spans[1:])):
        raise ValueError("Overlappende tekstendringer")
    for start, end, after in reversed(spans):
        content = content[:start] + after + content[end:]
    return content
