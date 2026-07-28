import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from Skoleverksted.backend.platform.compendium import (
    _extract_json,
    generate_compendium_chapter,
    plan_compendium,
    repair_compendium_chapter,
)
from Skoleverksted.backend.platform.compendium_renderer import (
    build_docx,
    build_typst_document,
    render_compendium,
)
from Skoleverksted.backend.platform.models import (
    CompendiumChapter,
    CompendiumPlanRequest,
    CompendiumSource,
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


def test_json_extractor_uses_the_first_complete_object():
    payload = _extract_json(
        '```json\n{"content_markdown":"## Kapittel","sources":[]}\n```\n'
        "Grounding metadata: {ikke del av svaret}"
    )
    assert payload["content_markdown"] == "## Kapittel"


def test_failed_regeneration_keeps_the_previous_chapter(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        compendium = PlatformStore(Path(tmp) / "platform.sqlite3").create_compendium(_proposal())
        chapter = compendium.chapters[0]
        previous_content = (
            "## Kontrollert utkast\n\n"
            "Dette er lærerens eksisterende kapitteltekst, og den må ikke bli overskrevet "
            "dersom en ny KI-generering feiler."
        )
        chapter.content_markdown = previous_content
        chapter.sources = [CompendiumSource(title="Eksisterende kilde", url="https://example.org")]
        chapter.status = "needs_revision"

        def fail_json(*_args, **_kwargs):
            raise json.JSONDecodeError("Expecting property name enclosed in double quotes", "{", 1)

        monkeypatch.setattr(
            "Skoleverksted.backend.platform.compendium._call_google_json",
            fail_json,
        )

        regenerated = generate_compendium_chapter(compendium, chapter.id)
        assert regenerated.status == "needs_revision"
        assert regenerated.content_markdown == previous_content
        assert regenerated.sources[0].title == "Eksisterende kilde"
        assert "bevart" in regenerated.verification_notes[0]
        assert "Expecting property" not in regenerated.verification_notes[0]


def test_failed_fact_check_keeps_the_new_research(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        compendium = PlatformStore(Path(tmp) / "platform.sqlite3").create_compendium(_proposal())
        chapter = compendium.chapters[0]
        new_content = "## Ny research\n\n" + ("Dokumentert faglig framstilling. " * 30)
        calls = 0

        def research_then_fail(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return ({
                    "content_markdown": new_content,
                    "key_facts": ["Et kontrollpunkt"],
                    "glossary": ["Begrep – forklaring"],
                    "sources": [{
                        "title": "Dokumentert kilde",
                        "url": "https://example.org/source",
                        "publisher": "Eksempel",
                    }],
                }, [])
            raise RuntimeError("midlertidig kontrollfeil")

        monkeypatch.setattr(
            "Skoleverksted.backend.platform.compendium._call_google_json",
            research_then_fail,
        )

        regenerated = generate_compendium_chapter(compendium, chapter.id)
        assert regenerated.status == "needs_revision"
        assert regenerated.content_markdown == new_content.strip()
        assert regenerated.sources[0].title == "Dokumentert kilde"
        assert "produsert og lagret" in regenerated.verification_notes[0]


def test_automatic_repair_revises_checks_and_keeps_previous_version(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        compendium = store.create_compendium(_proposal())
        chapter = compendium.chapters[0]
        before = "## Aktører\n\n" + (
            "Store deler av middelklassen støttet fascismen uten forbehold. " * 20
        )
        chapter.content_markdown = before
        chapter.status = "needs_revision"
        chapter.verification_notes = [
            "Påstanden om middelklassen er for generell og mangler en konkret kilde."
        ]
        chapter.sources = [
            CompendiumSource(title="Generell kilde", url="https://example.org/general")
        ]
        saved = store.replace_compendium_chapter(compendium.id, chapter)
        assert saved is not None
        compendium = saved
        after = "## Aktører\n\n" + (
            "Deler av middelklassen støttet fascistiske partier, men mønsteret "
            "varierte mellom land og grupper (Kilde: Konkret artikkel). " * 12
        )
        calls = 0

        def repair_then_verify(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return ({
                    "content_markdown": after,
                    "changes": [
                        "Påstanden om middelklassen ble avgrenset og nyansert."
                    ],
                    "key_facts": ["Støtten varierte mellom land og grupper."],
                    "glossary": [],
                    "sources": [{
                        "title": "Konkret artikkel",
                        "url": "https://example.org/specific",
                        "publisher": "Faglig utgiver",
                    }],
                }, [])
            return ({
                "approved": True,
                "notes": [],
                "unsafe_claims": [],
            }, [])

        monkeypatch.setattr(
            "Skoleverksted.backend.platform.compendium._call_google_json",
            repair_then_verify,
        )

        repaired = repair_compendium_chapter(compendium, chapter.id)
        assert repaired.status == "generated"
        assert repaired.content_markdown == after.strip()
        assert repaired.revision_summary == [
            "Påstanden om middelklassen ble avgrenset og nyansert."
        ]
        assert "klart til lærerkontroll" in repaired.verification_notes[0]

        stored = store.replace_compendium_chapter(compendium.id, repaired)
        assert stored is not None
        stored_chapter = stored.chapters[0]
        assert stored_chapter.previous_content_markdown == before
        assert stored_chapter.revision_count == 1


def test_automatic_repair_keeps_unresolved_claims_for_teacher_control(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        compendium = PlatformStore(Path(tmp) / "platform.sqlite3").create_compendium(_proposal())
        chapter = compendium.chapters[0]
        chapter.content_markdown = "## Kapittel\n\n" + ("En historisk framstilling. " * 30)
        chapter.status = "needs_revision"
        chapter.verification_notes = ["Et årstall mangler dokumentasjon."]
        calls = 0

        def repair_with_remaining_issue(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return ({
                    "content_markdown": chapter.content_markdown,
                    "changes": ["Årstallet ble undersøkt."],
                    "key_facts": [],
                    "glossary": [],
                    "sources": [{
                        "title": "Kontrollkilde",
                        "url": "https://example.org/check",
                        "publisher": "Utgiver",
                    }],
                }, [])
            return ({
                "approved": False,
                "notes": ["Kilden avklarer ikke det nøyaktige årstallet."],
                "unsafe_claims": ["Det nøyaktige årstallet."],
            }, [])

        monkeypatch.setattr(
            "Skoleverksted.backend.platform.compendium._call_google_json",
            repair_with_remaining_issue,
        )

        repaired = repair_compendium_chapter(compendium, chapter.id)
        assert repaired.status == "needs_revision"
        assert any("nøyaktige årstallet" in note for note in repaired.verification_notes)
        assert repaired.content_markdown == chapter.content_markdown.strip()


def test_automatic_repair_failure_never_overwrites_the_chapter(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        compendium = PlatformStore(Path(tmp) / "platform.sqlite3").create_compendium(_proposal())
        chapter = compendium.chapters[0]
        original = "## Kapittel\n\n" + ("Lærerens kapitteltekst skal bevares. " * 20)
        chapter.content_markdown = original
        chapter.status = "needs_revision"
        chapter.verification_notes = ["En påstand må dokumenteres."]

        monkeypatch.setattr(
            "Skoleverksted.backend.platform.compendium._call_google_json",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("midlertidig feil")),
        )

        repaired = repair_compendium_chapter(compendium, chapter.id)
        assert repaired.status == "needs_revision"
        assert repaired.content_markdown == original
        assert "bevart uendret" in repaired.verification_notes[-1]


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
