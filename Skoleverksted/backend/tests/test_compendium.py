import os
import shutil
import tempfile
from pathlib import Path

import pytest

from Skoleverksted.backend.platform.compendium import plan_compendium
from Skoleverksted.backend.platform.compendium_renderer import (
    build_docx,
    build_typst_document,
    render_compendium,
)
from Skoleverksted.backend.platform.models import (
    CompendiumChapter,
    CompendiumPlanRequest,
    YearPlanCreate,
    YearPlanPeriod,
)
from Skoleverksted.backend.platform.router import approve_compendium as approve_compendium_endpoint
from Skoleverksted.backend.platform.store import PlatformStore


def _proposal():
    return plan_compendium(CompendiumPlanRequest(
        topic="Alle kongedømmer i Europa omkring 1450",
        subject="Historie",
        level="VG2",
        kind="reference",
        target_pages=18,
        chapter_count=6,
        use_ai=False,
    ))


def test_fallback_outline_has_scope_contract_and_requested_chapters():
    proposal = _proposal()
    assert proposal.planning_source == "fallback"
    assert len(proposal.chapters) == 6
    assert proposal.scope_contract.completeness_label == "documented"
    assert "1450" in proposal.scope_contract.reference_date
    assert all(chapter.guiding_questions for chapter in proposal.chapters)


def test_compendium_and_versioned_artifacts_are_durable():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        compendium = store.create_compendium(_proposal())
        assert store.get_compendium(compendium.id) is not None

        first = compendium.chapters[0]
        updated = CompendiumChapter.model_validate({
            **first.model_dump(),
            "content_markdown": "## Innledning\n\nDette er en kontrollert kapitteltekst med tilstrekkelig innhold.",
            "status": "approved",
        })
        saved = store.replace_compendium_chapter(compendium.id, updated)
        assert saved is not None
        assert saved.status == "writing"
        assert saved.chapters[0].status == "approved"

        built = store.store_compendium_artifacts(
            compendium.id,
            pdf=b"%PDF-1.4\nkompendium\n%%EOF",
            docx=b"PK\x03\x04docx",
            pdf_filename="test.pdf",
            docx_filename="test.docx",
        )
        assert built is not None
        assert built.artifact_version == 1
        assert built.status == "review"
        assert store.get_compendium_artifact(compendium.id, "pdf")[1].read_bytes().startswith(b"%PDF")  # type: ignore[index]

        approved = store.approve_compendium(compendium.id)
        assert approved is not None
        assert approved.status == "approved"
        assert approved.approved_at

        reopened = PlatformStore(Path(tmp) / "platform.sqlite3")
        loaded = reopened.get_compendium(compendium.id)
        assert loaded is not None
        assert loaded.artifact_version == 1


def test_approval_attaches_the_pdf_to_the_selected_year_plan_period(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        period = YearPlanPeriod(title="Middelalderen", theme="Middelalderen")
        plan = store.create_year_plan(YearPlanCreate(
            title="Historie VG2",
            subject="Historie",
            level="VG2",
            school_year="2026-2027",
            periods=[period],
        ))
        proposal = _proposal()
        proposal.year_plan_id = plan.id
        proposal.period_ids = [period.id]
        compendium = store.create_compendium(proposal)
        for chapter in compendium.chapters:
            chapter.content_markdown = "## Kontrollert tekst\n\nEt ferdigstilt kapittel med faglig innhold."
            chapter.status = "approved"
            store.replace_compendium_chapter(compendium.id, chapter)
        store.store_compendium_artifacts(
            compendium.id,
            pdf=b"%PDF-1.4\nkompendium\n%%EOF",
            docx=b"PK\x03\x04docx",
            pdf_filename="middelalderen.pdf",
            docx_filename="middelalderen.docx",
        )
        monkeypatch.setattr(
            "Skoleverksted.backend.platform.router.get_platform_store",
            lambda: store,
        )

        approved = approve_compendium_endpoint(compendium.id)
        assert approved.status == "approved"
        reloaded_plan = store.get_year_plan(plan.id)
        assert reloaded_plan is not None
        assert len(reloaded_plan.periods[0].materials) == 1
        assert reloaded_plan.periods[0].materials[0].kind == "compendium"


def test_renderer_builds_structured_source_and_word_document():
    pytest.importorskip("docx")
    proposal = _proposal()
    compendium = PlatformStore(Path(tempfile.mkdtemp()) / "platform.sqlite3").create_compendium(proposal)
    for chapter in compendium.chapters:
        chapter.content_markdown = (
            f"## {chapter.title}\n\n### Bakgrunn\n\nEt faglig avsnitt om temaet.\n\n"
            "| Område | Kjennetegn |\n|---|---|\n| Eksempel | Forklaring |\n"
        )
        chapter.glossary = ["Len – en politisk og økonomisk forbindelse"]
        chapter.status = "approved"
    typst = build_typst_document(compendium)
    assert "#outline" in typst
    assert "Avgrensningskontrakt" in typst
    assert "#table(columns: 2" in typst
    docx = build_docx(compendium)
    assert docx.startswith(b"PK")
    assert len(docx) > 10_000


def test_compendium_typst_compiles_when_typst_is_available():
    executable = shutil.which(os.getenv("TYPST_PATH", "typst"))
    if not executable:
        pytest.skip("Typst er ikke installert i denne testjobben")
    pytest.importorskip("docx")
    proposal = _proposal()
    with tempfile.TemporaryDirectory() as tmp:
        compendium = PlatformStore(Path(tmp) / "platform.sqlite3").create_compendium(proposal)
        for chapter in compendium.chapters:
            chapter.content_markdown = f"## {chapter.title}\n\nKort, kontrollert brødtekst for kompilering."
            chapter.status = "approved"
        pdf, docx, pdf_name, docx_name = render_compendium(compendium)
        assert pdf.startswith(b"%PDF")
        assert docx.startswith(b"PK")
        assert pdf_name.endswith(".pdf")
        assert docx_name.endswith(".docx")
