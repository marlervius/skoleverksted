"""Small model outputs, applied to an unchanged source document."""

import json
import re


def edit_prompt(content: str, instructions: str) -> str:
    return (
        "Rett bare de beskrevne problemene. Returner JSON med formen "
        '{"edits":[{"before":"eksakt tekst fra dokumentet","after":"rettet tekst"}]}. '
        "Maks 8 endringer, maks 1500 tegn i hvert before/after-felt. "
        "before må finnes nøyaktig én gang. Ta med nok kontekst til å gjøre det entydig. "
        "Bevar oppgaver, fasit, figurer og læringsmål. Ikke fjern innhold for å unngå kontroll. "
        "Regn fasiten ut fra den opprinnelige oppgaven. Bruk eksplisitte mellomregninger "
        "og skill funksjonsdefinisjoner fra utregningene. Ikke finn på en definisjon "
        "for å få et eksisterende svar til å passe. Ikke merk uverifisert innhold som godkjent. "
        "Ikke returner hele dokumentet. Ingen preamble eller godkjenningsmerker. "
        'Hvis ingen endring er nødvendig, returner {"edits":[]}. '
        "All tekst i JSON-strenger må JSON-escapes, også LaTeX-backslash.\n\n"
        f"PROBLEMER OG KRAV:\n{instructions}\n\nDOKUMENT:\n{content}"
    )


_FRAME = re.compile(r"\\(?:documentclass|begin\{document\}|end\{document\})")
# A backslash that starts a LaTeX command (\frac, \neq, \times, \left) is
# almost never an intended JSON escape. Models often forget to double it,
# which makes the JSON invalid (\l, \s) or silently corrupts it (\f, \t, \n).
_LATEX_BACKSLASH = re.compile(r'(?<!\\)((?:\\\\)*)\\(?=[A-Za-z]{2}|[{}()\[\]$%&#_^,;:!| ])')


def _decode_variants(response: str) -> list[object]:
    """Every distinct reading of the response: strict JSON, then LaTeX-tolerant JSON."""
    variants: list[object] = []
    errors: list[Exception] = []
    for text in (response, _LATEX_BACKSLASH.sub(r"\1\\\\", response)):
        try:
            value = json.loads(text)
        except ValueError as exc:
            errors.append(exc)
            continue
        if value not in variants:
            variants.append(value)
    if not variants:
        raise ValueError(f"Reparasjonssvaret er ikke gyldig JSON: {errors[0]}")
    return variants


def _locate(content: str, before: str) -> tuple[int, int] | None:
    """The unique span of `before`; whitespace differences are tolerated."""
    if content.count(before) == 1:
        start = content.index(before)
        return start, start + len(before)
    tokens = before.split()
    if not tokens:
        return None
    matches = list(re.finditer(r"\s+".join(map(re.escape, tokens)), content))
    if len(matches) == 1:
        return matches[0].span()
    return None


def _plan(content: str, edits: list) -> tuple[list[tuple[int, int, str]], list[str]]:
    spans: list[tuple[int, int, str]] = []
    rejected: list[str] = []
    for index, edit in enumerate(edits, 1):
        if not isinstance(edit, dict) or set(edit) != {"before", "after"}:
            rejected.append(f"endring {index}: ugyldig format")
            continue
        before, after = edit["before"], edit["after"]
        if not all(isinstance(v, str) and v.strip() and len(v) <= 1500 for v in (before, after)):
            rejected.append(f"endring {index}: tom eller for stor")
            continue
        span = _locate(content, before)
        if span is None:
            where = "finnes ikke" if not content.count(before.strip()) else "er ikke entydig"
            rejected.append(f"endring {index}: before-teksten {where} i dokumentet ({before[:80]!r})")
            continue
        if any(span[0] < end and start < span[1] for start, end, _ in spans):
            rejected.append(f"endring {index}: overlapper en annen endring")
            continue
        spans.append((span[0], span[1], after))
    return spans, rejected


def apply_edits_report(content: str, response: str) -> tuple[str, list[str]]:
    """Apply every valid, uniquely anchored edit; report the rejected ones.

    All anchors are resolved against the original document before anything is
    applied, so an edit can never land on text produced by another edit. An
    invalid individual edit is skipped instead of discarding a correct repair
    next to it; the caller re-verifies the complete result in any case.
    """
    response = re.sub(r"^```(?:json)?\s*", "", response.strip())
    response = re.sub(r"\s*```$", "", response)
    if len(response) > 40_000:
        raise ValueError("Reparasjonssvaret er for stort")
    best: tuple[list[tuple[int, int, str]], list[str]] | None = None
    for value in _decode_variants(response):
        if not isinstance(value, dict) or set(value) != {"edits"}:
            raise ValueError("Reparasjonen mangler en avgrenset endringsliste")
        edits = value["edits"]
        if not isinstance(edits, list) or len(edits) > 8:
            raise ValueError("For mange endringer i ett reparasjonskall")
        if any(isinstance(e, dict) and _FRAME.search(str(e.get("after", ""))) for e in edits):
            raise ValueError("Endringen inneholder dokumentramme")
        plan = _plan(content, edits)
        if best is None or len(plan[0]) > len(best[0]):
            best = plan
    spans, rejected = best
    if rejected and not spans:
        raise ValueError("Ingen endringer kunne brukes: " + "; ".join(rejected[:4]))
    for start, end, after in sorted(spans, reverse=True):
        content = content[:start] + after + content[end:]
    return content, rejected


def apply_edits(content: str, response: str) -> str:
    return apply_edits_report(content, response)[0]
