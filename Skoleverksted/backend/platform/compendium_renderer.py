from __future__ import annotations

import io
import logging
import os
import re
from pathlib import Path
from typing import Iterable

from .models import Compendium, CompendiumSource


logger = logging.getLogger(__name__)


def safe_filename(value: str, suffix: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9æøåÆØÅ_-]+", "-", value).strip("-").lower()
    return f"{stem[:100] or 'kompendium'}.{suffix}"


def _typst_escape(value: str) -> str:
    value = value.replace("\\", "\\\\")
    value = re.sub(r"([#\[\]$<>@*_~`])", r"\\\1", value)
    return value


def _clean_markdown(value: str) -> str:
    value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
    value = re.sub(r"__(.*?)__", r"\1", value)
    value = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", value)
    value = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"\1", value)
    value = re.sub(r"\[(.*?)\]\((https?://[^)]+)\)", r"\1 (\2)", value)
    return value.strip()


def _normalize_markdown_newlines(value: str) -> str:
    """Turn model-produced escaped line breaks into real Markdown lines."""
    return (
        value.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
    )


def _table_to_typst(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    columns = max(len(row) for row in rows)
    cells: list[str] = []
    for row_index, row in enumerate(rows):
        padded = row + [""] * (columns - len(row))
        for value in padded:
            content = _typst_escape(_clean_markdown(value))
            if row_index == 0:
                cells.append(f"[#strong[{content}]]")
            else:
                cells.append(f"[{content}]")
    return (
        f"#table(columns: {columns}, inset: 5pt, stroke: 0.35pt + rgb(\"#D8DDE5\"),\n"
        + ",\n".join(cells)
        + ")\n#v(8pt)"
    )


def markdown_to_typst(markdown: str, chapter_title: str = "") -> str:
    lines = _normalize_markdown_newlines(markdown).replace("\r\n", "\n").splitlines()
    output: list[str] = []
    index = 0
    first_heading_skipped = False
    while index < len(lines):
        raw = lines[index].rstrip()
        stripped = raw.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines: list[str] = []
            while index < len(lines):
                candidate = lines[index].strip()
                if not (candidate.startswith("|") and candidate.endswith("|")):
                    break
                table_lines.append(candidate)
                index += 1
            rows = [
                [cell.strip() for cell in row.strip("|").split("|")]
                for row in table_lines
                if not re.fullmatch(r"\|?[\s:|-]+\|?", row)
            ]
            output.append(_table_to_typst(rows))
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            title = _clean_markdown(heading.group(2))
            if not first_heading_skipped and chapter_title and title.casefold() == chapter_title.casefold():
                first_heading_skipped = True
            else:
                source_level = len(heading.group(1)) - (1 if chapter_title else 0)
                level = min(3, max(2, source_level))
                output.append(f"{'=' * level} {_typst_escape(title)}")
            index += 1
            continue
        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet:
            output.append(f"- {_typst_escape(_clean_markdown(bullet.group(1)))}")
            index += 1
            continue
        numbered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if numbered:
            output.append(f"+ {_typst_escape(_clean_markdown(numbered.group(1)))}")
            index += 1
            continue
        if stripped.startswith(">"):
            output.append(
                '#block(fill: rgb("#F4F6F8"), inset: 8pt, stroke: (left: 2pt + rgb("#356A8A")))['
                + _typst_escape(_clean_markdown(stripped.lstrip("> ")))
                + "]"
            )
            index += 1
            continue
        if stripped:
            output.append(_typst_escape(_clean_markdown(stripped)))
        else:
            output.append("#v(5pt)")
        index += 1
    return "\n".join(output)


def _unique_sources(compendium: Compendium) -> list[CompendiumSource]:
    result: list[CompendiumSource] = []
    seen: set[str] = set()
    for chapter in compendium.chapters:
        for source in chapter.sources:
            key = (source.url or source.title).casefold()
            if key and key not in seen:
                seen.add(key)
                result.append(source)
    return result


def _scope_label(value: str) -> str:
    return {
        "complete": "Fullstendig innenfor kriteriene",
        "documented": "Dokumentert oversikt",
        "selected": "Faglig utvalg",
    }.get(value, "Faglig utvalg")


def build_typst_document(compendium: Compendium, *, image_path: str = "", image_credit: str = "") -> str:
    scope = compendium.scope_contract
    chapters = sorted(compendium.chapters, key=lambda item: item.order)
    source_items = _unique_sources(compendium)
    image_block = ""
    if image_path and Path(image_path).is_file():
        image_name = _typst_escape(Path(image_path).name)
        image_block = f"""
#v(14pt)
#figure(
  image("{image_name}", width: 82%),
  caption: [{_typst_escape(image_credit or "Pedagogisk illustrasjon")}],
)
"""
    chapter_blocks: list[str] = []
    for chapter in chapters:
        content = markdown_to_typst(chapter.content_markdown, chapter.title)
        glossary = ""
        if compendium.include_glossary and chapter.glossary:
            terms = "\n".join(f"- {_typst_escape(item)}" for item in chapter.glossary)
            glossary = f"\n== Begreper\n{terms}\n"
        chapter_blocks.append(
            f"= {_typst_escape(chapter.title)}\n"
            f"#text(fill: rgb(\"#5A6572\"), style: \"italic\")[{_typst_escape(chapter.purpose)}]\n"
            f"#v(8pt)\n{content}\n{glossary}"
        )

    inclusion = "\n".join(f"- {_typst_escape(item)}" for item in scope.inclusion_criteria) or "- Ikke spesifisert"
    exclusions = "\n".join(f"- {_typst_escape(item)}" for item in scope.exclusions) or "- Ikke spesifisert"
    bibliography = "\n".join(
        f"+ {_typst_escape(source.title)}"
        + (f" — {_typst_escape(source.publisher)}" if source.publisher else "")
        + (f" — {_typst_escape(source.url)}" if source.url else "")
        for source in source_items
    ) or "Ingen eksterne kilder er registrert. Dokumentet må kildekontrolleres før bruk."
    tasks = ""
    if compendium.include_reflection_tasks:
        tasks = f"""
= Videre arbeid

#block(fill: rgb("#F3F0FA"), inset: 12pt, radius: 4pt)[
+ Hvilke deler av framstillingen er best dokumentert, og hvor er usikkerheten størst?
+ Sammenlign to aktører, områder eller perioder fra kompendiet.
+ Velg én kilde fra litteraturlisten og vurder hva den kan og ikke kan fortelle.
+ Formuler et nytt fordypningsspørsmål som avgrensningskontrakten ikke dekker.
]
"""

    return f"""
#set document(title: "{_typst_escape(compendium.title)}", author: "Skoleverksted")
#set page(
  paper: "a4",
  margin: (top: 22mm, bottom: 20mm, left: 22mm, right: 18mm),
  header: context if counter(page).get().first() > 2 [
    #set text(size: 8pt, fill: rgb("#687583"))
    {_typst_escape(compendium.subject)} · {_typst_escape(compendium.title)}
    #h(1fr) {_typst_escape(compendium.level)}
    #line(length: 100%, stroke: 0.35pt + rgb("#D8DDE5"))
  ],
  footer: context [
    #line(length: 100%, stroke: 0.35pt + rgb("#D8DDE5"))
    #set text(size: 8pt, fill: rgb("#87919B"))
    Skoleverksted #h(1fr) Side #counter(page).display()
  ],
)
#set text(font: ("Source Sans 3", "Noto Sans", "Liberation Sans"), size: 10.5pt, lang: "nb", fill: rgb("#22272B"))
#set par(justify: true, leading: 0.68em)
#set heading(numbering: "1.1")
#show heading.where(level: 1): it => block(above: 20pt, below: 10pt)[
  #text(size: 19pt, weight: 600, fill: rgb("#174D6C"))[#it.body]
  #line(length: 100%, stroke: 1.2pt + rgb("#3E8E9B"))
]
#show heading.where(level: 2): it => block(above: 13pt, below: 6pt)[
  #text(size: 13pt, weight: 600, fill: rgb("#235F72"))[#it.body]
]
#show heading.where(level: 3): it => block(above: 10pt, below: 4pt)[
  #text(size: 11pt, weight: 600)[#it.body]
]

#align(center)[
  #v(20mm)
  #text(size: 10pt, weight: 600, fill: rgb("#3E8E9B"))[SKOLEVERKSTED · {_typst_escape(compendium.subject.upper())}]
  #v(7mm)
  #text(size: 28pt, weight: 650, fill: rgb("#173F55"))[{_typst_escape(compendium.title)}]
  #v(5mm)
  #text(size: 13pt, fill: rgb("#596875"))[{_typst_escape(compendium.level)} · {_typst_escape(compendium.audience)}]
  #v(8mm)
  #block(width: 80%, fill: rgb("#EFF5F6"), inset: 12pt, radius: 5pt)[
    #text(size: 10.5pt)[{_typst_escape(compendium.purpose or compendium.topic)}]
  ]
  {image_block}
]
#pagebreak()

= Om kompendiet

Dette dokumentet er laget som {_typst_escape(_scope_label(scope.completeness_label).lower())}.
Det må vurderes av lærer før bruk og oppdateres når faggrunnlaget endrer seg.

== Avgrensningskontrakt

#table(
  columns: (35mm, 1fr),
  inset: 6pt,
  stroke: 0.35pt + rgb("#D8DDE5"),
  [#strong[Referansetid]], [{_typst_escape(scope.reference_date or "Ikke spesifisert")}],
  [#strong[Geografi]], [{_typst_escape(scope.geography or "Ikke spesifisert")}],
  [#strong[Dekningsnivå]], [{_typst_escape(_scope_label(scope.completeness_label))}],
)

{_typst_escape(scope.completeness_note)}

=== Tas med
{inclusion}

=== Tas ikke med
{exclusions}

#pagebreak()
#outline(title: [Innhold], depth: 1, indent: auto)
#pagebreak()

{"\n#pagebreak()\n".join(chapter_blocks)}

{tasks}

= Kilder og videre lesning

{bibliography}

#v(12pt)
#block(fill: rgb("#FFF4DD"), inset: 10pt, radius: 4pt)[
  #strong[Lærerens sluttkontroll:] Kontroller særlig absolutte formuleringer,
  historiske grenser, tall, sitater og om kildene faktisk støtter framstillingen.
]
"""


def _add_markdown_to_docx(document, markdown: str, chapter_title: str) -> None:
    lines = _normalize_markdown_newlines(markdown).replace("\r\n", "\n").splitlines()
    first_heading_skipped = False
    index = 0
    while index < len(lines):
        raw = lines[index].strip()
        if raw.startswith("|") and raw.endswith("|"):
            table_lines: list[str] = []
            while index < len(lines):
                candidate = lines[index].strip()
                if not (candidate.startswith("|") and candidate.endswith("|")):
                    break
                table_lines.append(candidate)
                index += 1
            rows = [
                [_clean_markdown(cell.strip()) for cell in row.strip("|").split("|")]
                for row in table_lines
                if not re.fullmatch(r"\|?[\s:|-]+\|?", row)
            ]
            if rows:
                columns = max(len(row) for row in rows)
                table = document.add_table(rows=len(rows), cols=columns)
                table.style = "Table Grid"
                for row_index, row in enumerate(rows):
                    for column_index, value in enumerate(row):
                        cell = table.cell(row_index, column_index)
                        cell.text = value
                        if row_index == 0:
                            for run in cell.paragraphs[0].runs:
                                run.bold = True
            continue
        stripped = _clean_markdown(raw)
        if not stripped:
            index += 1
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            title = _clean_markdown(heading.group(2))
            if not first_heading_skipped and title.casefold() == chapter_title.casefold():
                first_heading_skipped = True
                continue
            source_level = len(heading.group(1)) - (1 if chapter_title else 0)
            document.add_heading(title, level=min(3, max(2, source_level)))
        elif re.match(r"^[-*]\s+", stripped):
            document.add_paragraph(re.sub(r"^[-*]\s+", "", stripped), style="List Bullet")
        elif re.match(r"^\d+[.)]\s+", stripped):
            document.add_paragraph(re.sub(r"^\d+[.)]\s+", "", stripped), style="List Number")
        elif re.fullmatch(r"\|?[\s:|-]+\|?", stripped):
            continue
        else:
            document.add_paragraph(stripped.strip("| "))
        index += 1


def build_docx(compendium: Compendium, *, image_path: str = "", image_credit: str = "") -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt

    document = Document()
    styles = document.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"].font.size = Pt(10.5)
    title = document.add_heading(compendium.title, 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle = document.add_paragraph(f"{compendium.subject} · {compendium.level} · {compendium.audience}")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if compendium.purpose:
        purpose = document.add_paragraph(compendium.purpose)
        purpose.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if image_path and Path(image_path).is_file():
        document.add_picture(image_path, width=Inches(5.5))
        caption = document.add_paragraph(image_credit or "Pedagogisk illustrasjon")
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_page_break()

    document.add_heading("Om kompendiet", level=1)
    scope = compendium.scope_contract
    document.add_paragraph(scope.completeness_note)
    table = document.add_table(rows=4, cols=2)
    table.style = "Table Grid"
    rows = [
        ("Referansetid", scope.reference_date or "Ikke spesifisert"),
        ("Geografi", scope.geography or "Ikke spesifisert"),
        ("Dekningsnivå", _scope_label(scope.completeness_label)),
        ("Utelatelser", "; ".join(scope.exclusions) or "Ikke spesifisert"),
    ]
    for row, values in zip(table.rows, rows):
        row.cells[0].text, row.cells[1].text = values

    for chapter in sorted(compendium.chapters, key=lambda item: item.order):
        document.add_heading(chapter.title, level=1)
        if chapter.purpose:
            paragraph = document.add_paragraph(chapter.purpose)
            paragraph.style = document.styles["Quote"]
        _add_markdown_to_docx(document, chapter.content_markdown, chapter.title)
        if compendium.include_glossary and chapter.glossary:
            document.add_heading("Begreper", level=2)
            for item in chapter.glossary:
                document.add_paragraph(item, style="List Bullet")

    if compendium.include_reflection_tasks:
        document.add_heading("Videre arbeid", level=1)
        for task in (
            "Hvilke deler av framstillingen er best dokumentert, og hvor er usikkerheten størst?",
            "Sammenlign to aktører, områder eller perioder fra kompendiet.",
            "Velg én kilde fra litteraturlisten og vurder hva den kan og ikke kan fortelle.",
            "Formuler et nytt fordypningsspørsmål som avgrensningskontrakten ikke dekker.",
        ):
            document.add_paragraph(task, style="List Number")

    document.add_heading("Kilder og videre lesning", level=1)
    sources = _unique_sources(compendium)
    if sources:
        for source in sources:
            value = source.title
            if source.publisher:
                value += f" — {source.publisher}"
            if source.url:
                value += f" — {source.url}"
            document.add_paragraph(value, style="List Number")
    else:
        document.add_paragraph("Ingen eksterne kilder er registrert. Dokumentet må kildekontrolleres før bruk.")

    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()


def render_compendium(
    compendium: Compendium,
    *,
    image_path: str = "",
    image_credit: str = "",
) -> tuple[bytes, bytes, str, str]:
    from VGS_KI.backend.pdf_service import compile_typst

    try:
        typst = build_typst_document(compendium, image_path=image_path, image_credit=image_credit)
        pdf = compile_typst(typst, image_path=image_path or None)
        docx = build_docx(compendium, image_path=image_path, image_credit=image_credit)
    except Exception as exc:
        if not image_path:
            raise
        logger.warning(
            "Kompendiumbildet kunne ikke bygges inn; lager dokumentene uten bilde: %s",
            exc,
        )
        typst = build_typst_document(compendium)
        pdf = compile_typst(typst)
        docx = build_docx(compendium)
    return (
        pdf,
        docx,
        safe_filename(compendium.title, "pdf"),
        safe_filename(compendium.title, "docx"),
    )
