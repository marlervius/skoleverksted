"""Renderer for the redesigned læringsark + separate faktarapport PDFs.

Implements DEL 2 (Typst layout via templates/laeringsark.typ) and DEL 3
(structured data contract) of SPEC_laeringsark_redesign.

The writer agent delivers structured JSON:

    {
      "tittel": "...",
      "ingress": "...",                       # optional
      "seksjoner": [
        {
          "tittel": "...",
          "avsnitt": ["...", "..."],          # may contain [K] markers
          "begreper": [{"term": "...", "def": "..."}],
          "kjeder": [{"steg": ["...", "..."]}]
        }
      ],
      "verk": ["The Sleepwalkers"]            # english-lint whitelist
    }

This module turns that into Typst source built on the component library in
templates/laeringsark.typ, and renders the teacher fact report as its OWN
document (never appended to the student PDF).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

if __package__:
    from .text_pipeline import clean_field, normalize_text, strip_emoji, typst_escape
else:
    from text_pipeline import clean_field, normalize_text, strip_emoji, typst_escape

logger = logging.getLogger(__name__)

MAX_MARGIN_BEGREPER = 4  # > 4 begreper → full-width begrepsboks fallback


# ── Field-level helpers ───────────────────────────────────────────────────────

def _esc(s: str) -> str:
    """Plain field: hygiene + Typst escaping (no markup allowed)."""
    return typst_escape(clean_field(s))


def _esc_prose(s: str) -> str:
    """Prose field: hygiene + escaping, but *italic*/**bold** survive as
    Typst #emph/#strong, and [K] markers become the #K component."""
    if not s:
        return ""
    s = strip_emoji(normalize_text(s))

    # Protect markdown emphasis spans before stripping/escaping
    spans: list[str] = []

    def _protect(content: str, kind: str) -> str:
        spans.append(f"#{kind}[{typst_escape(content)}]")
        return f"\x00{len(spans) - 1}\x00"

    s = re.sub(r"\*\*(.+?)\*\*", lambda m: _protect(m.group(1), "strong"), s)
    s = re.sub(r"(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)", lambda m: _protect(m.group(1), "emph"), s)

    s = typst_escape(re.sub(r"[ \t]+", " ", s.replace("`", "")).strip())

    # [K] citation markers → muted superscript component (escaped as \[K\])
    s = s.replace(" \\[K\\]", "#K").replace("\\[K\\]", "#K")

    for idx, span in enumerate(spans):
        s = s.replace(f"\x00{idx}\x00", span)
    return s


def _limit_words(s: str, max_words: int) -> str:
    words = s.split()
    if len(words) <= max_words:
        return s
    return " ".join(words[:max_words]).rstrip(",.;:") + " …"


def _typst_str(s: str) -> str:
    """Quote a string for a Typst string literal."""
    s = strip_emoji(normalize_text(s or ""))
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# ── Structured-lesson validation ──────────────────────────────────────────────

def coerce_structured_lesson(data: Any) -> Optional[dict]:
    """Validate/normalise the writer's JSON. Returns None if unusable."""
    if not isinstance(data, dict):
        return None
    seksjoner_raw = data.get("seksjoner")
    if not isinstance(seksjoner_raw, list) or not seksjoner_raw:
        return None

    seksjoner = []
    for sek in seksjoner_raw:
        if not isinstance(sek, dict):
            continue
        avsnitt = [str(a).strip() for a in (sek.get("avsnitt") or []) if str(a).strip()]
        if not avsnitt:
            continue
        begreper = []
        for b in (sek.get("begreper") or []):
            if isinstance(b, dict) and b.get("term") and b.get("def"):
                begreper.append({"term": str(b["term"]).strip(),
                                 "def": str(b["def"]).strip()})
        kjeder = []
        for k in (sek.get("kjeder") or []):
            steg = k.get("steg") if isinstance(k, dict) else k
            if isinstance(steg, list):
                steg = [str(s).strip() for s in steg if str(s).strip()]
                if len(steg) >= 2:
                    kjeder.append(steg)
        seksjoner.append({
            "tittel": str(sek.get("tittel") or "").strip() or "Uten tittel",
            "avsnitt": avsnitt,
            "begreper": begreper,
            "kjeder": kjeder,
        })

    if not seksjoner:
        return None

    verk = [str(v).strip() for v in (data.get("verk") or []) if str(v).strip()]
    return {
        "tittel": str(data.get("tittel") or "").strip(),
        "ingress": str(data.get("ingress") or "").strip(),
        "seksjoner": seksjoner,
        "verk": verk,
    }


def structured_to_plain_text(data: dict) -> str:
    """Plain-text rendering of the structured lesson, used as context for the
    downstream agents (worksheet, exercises, fact report) and as basis_text."""
    parts: list[str] = []
    if data.get("tittel"):
        parts.append(data["tittel"])
    if data.get("ingress"):
        parts.append(data["ingress"])
    for sek in data["seksjoner"]:
        parts.append(f"## {sek['tittel']}")
        parts.extend(sek["avsnitt"])
        for steg in sek["kjeder"]:
            parts.append("Årsakskjede: " + " → ".join(steg))
        if sek["begreper"]:
            parts.append("Begreper: " + "; ".join(
                f"{b['term']}: {b['def']}" for b in sek["begreper"]))
    return "\n\n".join(parts)


def collect_text_fields(data: dict) -> str:
    """All human-readable text in the structured lesson (for linting)."""
    parts = [data.get("tittel", ""), data.get("ingress", "")]
    for sek in data.get("seksjoner", []):
        parts.append(sek.get("tittel", ""))
        parts.extend(sek.get("avsnitt", []))
        for b in sek.get("begreper", []):
            parts.extend([b.get("term", ""), b.get("def", "")])
        for steg in sek.get("kjeder", []):
            parts.extend(steg)
    return "\n".join(p for p in parts if p)


# ── Oppgave parsing (worksheet text → oppgaveboks data) ───────────────────────

_TASK_LINE_RE = re.compile(r"^\s*(\d+)\s*[.)]\s*(★{1,3})?\s*(.*)$")


def parse_oppgaver(comprehension: str, discussion: str) -> list[dict]:
    """Parse worksheet question blocks into structured oppgaver.

    Each task: {"niva": 1-3, "tekst": str, "linjer": int}. Difficulty comes
    from the ★ markers the worksheet agent is instructed to add; tasks without
    markers default to level 2 (comprehension) / 3 (discussion).
    """
    oppgaver: list[dict] = []

    def _parse_block(text: str, default_niva: int, default_linjer: int) -> None:
        if not text or not text.strip():
            return
        current: Optional[dict] = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            m = _TASK_LINE_RE.match(line)
            if m and m.group(3):
                if current:
                    oppgaver.append(current)
                stars = m.group(2)
                niva = len(stars) if stars else default_niva
                current = {
                    "niva": max(1, min(3, niva)),
                    "tekst": m.group(3).strip(),
                    "linjer": default_linjer,
                    "alternativer": [],
                }
            elif current is not None:
                # a)/b)/c) options or continuation lines
                opt = re.match(r"^[a-d]\)\s*(.+)$", line, flags=re.IGNORECASE)
                if opt:
                    current["alternativer"].append(line)
                    current["linjer"] = 0  # MCQ → no writing lines
                else:
                    current["tekst"] += " " + line
        if current:
            oppgaver.append(current)

    _parse_block(comprehension, default_niva=2, default_linjer=3)
    _parse_block(discussion, default_niva=3, default_linjer=6)

    # Strip leftover star markers inside the text and trailing answer markers
    for o in oppgaver:
        o["tekst"] = re.sub(r"[★☆]+", "", o["tekst"]).strip()
        o["alternativer"] = [re.sub(r"\s*\*+\s*$", "", a) for a in o["alternativer"]]

    return oppgaver


# ── Læringsark document ───────────────────────────────────────────────────────

def build_laeringsark_doc(
    data: dict,
    *,
    fag: str,
    tema: str,
    niva: str,
    modus: str,
    kilde: Optional[str] = None,
    har_k_markorer: bool = False,
    laeringsmaal: str = "",
    oppgaver: Optional[list[dict]] = None,
    image_filename: Optional[str] = None,
) -> str:
    """Build the full Typst source for the redesigned student læringsark."""
    fag_s = _typst_str(fag)
    tema_s = _typst_str(tema)
    tittel = _esc(data.get("tittel") or tema)

    lines: list[str] = [
        '#import "laeringsark.typ": *',
        f"#show: doc => laeringsark-oppsett(doc, fag: {fag_s}, tema: {tema_s})",
        f"#set document(title: {_typst_str('Læringsark: ' + (data.get('tittel') or tema))}, author: \"Scriptorium for VGS\")",
        "",
        f"#tittelblokk([{tittel}], [{_esc(niva)}], [{_esc(modus)}], fag: {fag_s}, "
        + (f"kilde: [{_esc(kilde)}])" if kilde else "kilde: none)"),
        "",
    ]

    if image_filename:
        lines += [
            "#align(center)[",
            f'  #block(clip: true, radius: 6pt, width: 88%)[#image("{image_filename}", width: 100%)]',
            "  #v(2pt)",
            "  #text(size: 8pt, fill: gray-400)[Foto: Wikimedia Commons]",
            "]",
            "#v(8pt)",
            "",
        ]

    if data.get("ingress"):
        lines += [f"#text(size: 11pt, fill: gray-600)[{_esc_prose(data['ingress'])}]", "#v(6pt)", ""]

    if laeringsmaal and laeringsmaal.strip():
        goals = _render_laeringsmaal(laeringsmaal)
        if goals:
            lines += [goals, ""]

    # ── Fagseksjoner med margbegreper ──
    for sek in data["seksjoner"]:
        body_parts: list[str] = []
        for avsnitt in sek["avsnitt"]:
            body_parts.append(_esc_prose(avsnitt))
            body_parts.append("")
        for steg in sek["kjeder"]:
            steg_args = ", ".join(_typst_str(clean_field(s)) for s in steg)
            body_parts.append(f"#kjede(({steg_args},))")
            body_parts.append("")
        body = "\n".join(body_parts).rstrip()

        begreper = sek["begreper"]
        if begreper and len(begreper) <= MAX_MARGIN_BEGREPER:
            begrep_args = ", ".join(
                f"(term: {_typst_str(clean_field(b['term']))}, "
                f"def: {_typst_str(_limit_words(clean_field(b['def']), 14))})"
                for b in begreper
            )
            lines += [
                f"#fagseksjon([{_esc(sek['tittel'])}], begreper: ({begrep_args},))[",
                body,
                "]",
                "",
            ]
        elif begreper:
            # Fallback: > 4 begreper → full-width box under the section title
            begrep_args = ", ".join(
                f"(term: {_typst_str(clean_field(b['term']))}, "
                f"def: {_typst_str(_limit_words(clean_field(b['def']), 14))})"
                for b in begreper
            )
            lines += [
                f"#seksjonstittel([{_esc(sek['tittel'])}])",
                f"#begrepsboks(({begrep_args},))",
                body,
                "",
            ]
        else:
            lines += [
                f"#seksjonstittel([{_esc(sek['tittel'])}])",
                body,
                "",
            ]

    # K-marker legend — only when the text actually carries [K] markers
    if har_k_markorer:
        legend_kilde = f"kilde: [{_esc(kilde)}]" if kilde else "kilde: none"
        lines += [f"#k-legende({legend_kilde})", ""]

    # ── Oppgaver ──
    if oppgaver:
        lines += ["#seksjonstittel([Oppgaver])", ""]
        for nr, opp in enumerate(oppgaver, 1):
            tekst = _esc_prose(opp["tekst"])
            if opp.get("alternativer"):
                alt_lines = " \\\n  ".join(_esc_prose(a) for a in opp["alternativer"])
                tekst = f"{tekst} \\\n  {alt_lines}"
            lines += [
                f"#oppgaveboks({nr}, {int(opp['niva'])}, [{tekst}], linjer: {int(opp.get('linjer', 0))})",
                "",
            ]

    return "\n".join(lines)


def _render_laeringsmaal(text: str) -> str:
    """Render learning goals as a subtle list under the title block."""
    items = []
    for raw in text.splitlines():
        line = re.sub(r"^\s*(?:\d+[.)]|[-•*])\s*", "", raw).strip()
        if line and len(line) > 3 and not line.lower().startswith(("etter denne", "after this")):
            items.append(line)
    if not items:
        return ""
    rows = "\n".join(f"  #text(size: 9pt, fill: gray-600)[‣ {_esc_prose(i)}] \\" for i in items[:5])
    return (
        "#block(fill: blue-50, radius: 4pt, inset: 9pt, width: 100%)[\n"
        "  #text(size: 7.5pt, fill: blue-600, tracking: 0.6pt, weight: 500)[LÆRINGSMÅL]\n"
        "  #v(1.5mm)\n"
        f"{rows}\n"
        "]\n#v(6pt)"
    )


# ── Faktarapport (separate teacher PDF) ───────────────────────────────────────

STATUS_KEYS = {"dekket": "st-dekket", "strid": "st-strid",
               "utenfor": "st-utenfor", "usikker": "st-usikker"}

# Legacy emoji statuses → etiketter, for free-text fallback reports.
_LEGACY_STATUS_MAP = [
    ("📗", "#st-dekket "),
    ("📕", "#st-strid "),
    ("📘", "#st-utenfor "),
    ("✅", '#etikett("HØY SIKKERHET", green-50, green-800) '),
    ("⚠️", "#st-usikker "),
    ("⚠", "#st-usikker "),
    ("🔶", '#etikett("FORENKLING", amber-50, amber-800) '),
]


def coerce_structured_rapport(data: Any) -> Optional[dict]:
    """Validate the fact-check agent's structured JSON. None if unusable."""
    if not isinstance(data, dict):
        return None
    if not data.get("konklusjon") and not data.get("punkter"):
        return None

    punkter = []
    for p in (data.get("punkter") or []):
        if not isinstance(p, dict) or not p.get("pastand"):
            continue
        status = str(p.get("status") or "usikker").strip().lower()
        if status not in STATUS_KEYS:
            status = "usikker"
        punkter.append({
            "status": status,
            "pastand": str(p["pastand"]).strip(),
            "kommentar": str(p.get("kommentar") or "").strip(),
        })

    def _str_list(key: str) -> list[str]:
        return [str(x).strip() for x in (data.get(key) or []) if str(x).strip()]

    return {
        "konklusjon": str(data.get("konklusjon") or "").strip(),
        "punkter": punkter,
        "kausalitet": _str_list("kausalitet"),
        "perspektiver": _str_list("perspektiver"),
        "ikke_dekket": _str_list("ikke_dekket"),
        "kilder": _str_list("kilder"),
        "verk": _str_list("verk"),
    }


def build_faktarapport_doc(
    rapport: Any,
    *,
    fag: str,
    tema: str,
    kilde: Optional[str] = None,
) -> str:
    """Build the Typst source for the SEPARATE teacher fact-report PDF.

    `rapport` is either the structured dict from `coerce_structured_rapport`
    or a plain string (legacy fallback)."""
    fag_s = _typst_str(fag)
    tema_s = _typst_str(tema)

    lines: list[str] = [
        '#import "laeringsark.typ": *',
        f"#show: doc => laeringsark-oppsett(doc, fag: {fag_s}, tema: {tema_s})",
        f"#set document(title: {_typst_str('Faktarapport: ' + tema)}, author: \"Scriptorium for VGS\")",
        "",
        f"#faktarapport-topp([{_esc(tema)}], fag: {fag_s})",
        "",
    ]

    if isinstance(rapport, dict):
        if rapport.get("konklusjon"):
            lines += [f"#konklusjonslinje([{_esc_prose(rapport['konklusjon'])}])", ""]

        if rapport.get("punkter"):
            lines += ["#seksjonstittel([Faktapåstander])", ""]
            for p in rapport["punkter"]:
                etikett_ref = STATUS_KEYS[p["status"]]
                kommentar = (
                    f" \\\n  #text(size: 8.5pt, fill: gray-600)[{_esc_prose(p['kommentar'])}]"
                    if p.get("kommentar") else ""
                )
                lines += [
                    "#block(breakable: false, below: 0.8em)[",
                    f"  #{etikett_ref} #h(4pt) #text(size: 9.5pt)[{_esc_prose(p['pastand'])}]{kommentar}",
                    "]",
                    "",
                ]

        _rapport_list_section(lines, "Kausalnarrativ som overforenkler", rapport.get("kausalitet"))
        _rapport_list_section(lines, "Utelatte perspektiver", rapport.get("perspektiver"))
        _rapport_list_section(lines, "Hva teksten ikke dekker", rapport.get("ikke_dekket"))
        _rapport_list_section(lines, "Kilder for verifisering", rapport.get("kilder"))

        if not kilde:
            lines += [
                "#v(1em)",
                "#text(size: 8.5pt, fill: gray-400, style: \"italic\")[Tips: Lim inn kildemateriale, "
                "så kan neste rapport kryssjekke faktaene mot en faktisk kilde.]",
                "",
            ]
    else:
        # Free-text fallback: map legacy emoji statuses to etiketter, then
        # render paragraph by paragraph.
        text = normalize_text(str(rapport or ""))
        snippets: list[str] = []
        for emoji_ch, replacement in _LEGACY_STATUS_MAP:
            if emoji_ch in text:
                snippets.append(replacement)
                text = text.replace(emoji_ch, f"\x00{len(snippets) - 1}\x00")
        rendered = _esc_prose(text)
        for idx, snippet in enumerate(snippets):
            rendered = rendered.replace(f"\x00{idx}\x00", snippet)
        for para in rendered.split("\n\n"):
            para = para.strip()
            if para:
                lines += [para.replace("\n", " \\\n"), ""]

    return "\n".join(lines)


def _rapport_list_section(lines: list[str], tittel: str, items: Optional[list[str]]) -> None:
    if not items:
        return
    lines += [f"#seksjonstittel([{_esc(tittel)}])", ""]
    for item in items:
        lines += [f"- {_esc_prose(item)}"]
    lines += [""]
