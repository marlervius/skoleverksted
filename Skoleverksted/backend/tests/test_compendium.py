import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import ModuleType

import pytest
from fastapi import HTTPException

from Skoleverksted.backend.platform import compendium_renderer
from Skoleverksted.backend.platform.compendium import (
    _extract_json,
    _teacher_sources,
    _source_quality_notes,
    _source_payload,
    generate_compendium_chapter,
    plan_compendium,
    repair_compendium_chapter,
)
from Skoleverksted.backend.platform.compendium_renderer import (
    build_docx,
    build_typst_document,
    markdown_to_typst,
    render_compendium,
)
from Skoleverksted.backend.platform.models import (
    CompendiumChapter,
    CompendiumChapterUpdate,
    CompendiumPlanRequest,
    CompendiumSource,
    TruthPassport,
    YearPlanCreate,
    YearPlanPeriod,
)
from Skoleverksted.backend.platform.router import approve_compendium as approve_compendium_endpoint
from Skoleverksted.backend.platform.router import (
    RepairInProgressError,
    RepairTimeoutError,
    _run_repair_with_timeout,
)
from Skoleverksted.backend.platform.router import update_compendium_chapter as update_chapter_endpoint
from Skoleverksted.backend.platform.store import PlatformStore
from Skoleverksted.backend.platform.truth import TruthAudit


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


def _verified_truth(content: str) -> TruthAudit:
    return TruthAudit(
        content=content,
        passport=TruthPassport(
            status="verified",
            topic="Testtema",
            subject="Historie",
            coverage_percent=100,
            verified_claims=1,
            total_claims=1,
            summary="Testkontrollen er grønn.",
        ),
    )


def test_fallback_outline_has_scope_contract_and_requested_chapters():
    proposal = _proposal()
    assert proposal.planning_source == "fallback"
    assert len(proposal.chapters) == 6
    assert proposal.scope_contract.completeness_label == "documented"
    assert "1450" in proposal.scope_contract.reference_date
    assert all(chapter.guiding_questions for chapter in proposal.chapters)


def test_fallback_outline_understands_century_and_avoids_internal_placeholders():
    proposal = plan_compendium(CompendiumPlanRequest(
        topic="Politiske ideologier i det 20. århundre",
        subject="Historie",
        level="VG2",
        use_ai=False,
    ))

    assert proposal.scope_contract.reference_date == "1901–2000"
    assert proposal.scope_contract.geography == ""
    assert "læreren" not in proposal.scope_contract.completeness_note.casefold()


def test_json_extractor_uses_the_first_complete_object():
    payload = _extract_json(
        '```json\n{"content_markdown":"## Kapittel","sources":[]}\n```\n'
        "Grounding metadata: {ikke del av svaret}"
    )
    assert payload["content_markdown"] == "## Kapittel"


def test_source_payload_keeps_canonical_pages_and_drops_search_redirects():
    sources = _source_payload([
        {
            "title": "Ideologi",
            "url": "https://snl.no/ideologi?utm_source=search",
            "publisher": "Store norske leksikon",
        },
        {
            "title": "Midlertidig søketreff",
            "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/temporary",
            "publisher": "",
        },
    ])

    assert [source.url for source in sources] == ["https://snl.no/ideologi"]


def test_teacher_urls_are_promoted_to_truth_sources():
    sources = _teacher_sources(
        "Kilder: https://snl.no/den_franske_revolusjonen og "
        "https://www.udir.no/lk20/his01-03/kompetansemaal-og-vurdering/kv103"
    )
    assert [source.origin for source in sources] == ["teacher", "teacher"]
    assert all(source.fetch_status == "provided" for source in sources)


def test_source_quality_notes_reject_weak_sources_and_generic_homepages():
    notes = _source_quality_notes([
        CompendiumSource(
            title="Political ideology",
            url="https://en.wikipedia.org/wiki/Political_ideology",
        ),
        CompendiumSource(
            title="NDLA",
            url="https://ndla.no/",
        ),
        CompendiumSource(
            title="Ideologi",
            url="https://snl.no/ideologi",
            publisher="Store norske leksikon",
        ),
    ])

    assert len(notes) == 2
    assert any("primærkilde" in note for note in notes)
    assert any("forside" in note for note in notes)
    assert not any("Ideologi" in note for note in notes)
    assert "mangler et konkret kildegrunnlag" in _source_quality_notes([])[0]


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
        assert regenerated.status == "parse_failure"
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
        assert regenerated.status == "verification_failed"
        assert regenerated.content_markdown == new_content.strip()
        assert regenerated.sources[0].title == "Dokumentert kilde"
        assert "produsert og lagret" in regenerated.verification_notes[0]


def test_generation_passes_teacher_sources_and_blocks_broken_language(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        compendium = PlatformStore(Path(tmp) / "platform.sqlite3").create_compendium(_proposal())
        compendium.source_brief = "https://snl.no/den_franske_revolusjonen"
        chapter = compendium.chapters[0]
        captured: dict[str, object] = {}
        content = "## Årsaker\n\n" + ("Særlig ble en finansiell katastrofe. " * 12)

        def fake_google(*_args, **kwargs):
            if kwargs.get("response_schema", {}).get("properties", {}).get("approved"):
                return ({"approved": True, "notes": [], "unsafe_claims": []}, [])
            return ({
                "content_markdown": content,
                "key_facts": ["En påstand"],
                "glossary": ["Begrep – forklaring"],
                "sources": [],
            }, [])

        def fake_audit(**kwargs):
            captured["provided_sources"] = kwargs["provided_sources"]
            return _verified_truth(kwargs["content"])

        monkeypatch.setattr("Skoleverksted.backend.platform.compendium._call_google_json", fake_google)
        monkeypatch.setattr("Skoleverksted.backend.platform.compendium.audit_truth", fake_audit)
        result = generate_compendium_chapter(compendium, chapter.id)
        assert result.status == "language_quality_failed"
        assert result.truth_passport is not None
        provided = captured["provided_sources"]
        assert provided and provided[0].origin == "teacher"


def test_repair_timeout_is_explicit_and_does_not_return_a_fake_success(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        compendium = PlatformStore(Path(tmp) / "platform.sqlite3").create_compendium(_proposal())
        monkeypatch.setattr("Skoleverksted.backend.platform.router._REPAIR_TIMEOUT_SECONDS", 0.01)

        def hangs(*_args, **_kwargs):
            time.sleep(0.1)

        monkeypatch.setattr("Skoleverksted.backend.platform.router.repair_compendium_chapter", hangs)
        with pytest.raises(RepairTimeoutError) as error:
            _run_repair_with_timeout(compendium, compendium.chapters[0].id, operation_id="test-timeout")
        assert error.value.operation_id == "test-timeout"


def test_repair_lock_rejects_parallel_requests(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        compendium = PlatformStore(Path(tmp) / "platform.sqlite3").create_compendium(_proposal())
        monkeypatch.setattr("Skoleverksted.backend.platform.router._REPAIR_TIMEOUT_SECONDS", 1)
        started = threading.Event()

        def slow_success(*_args, **_kwargs):
            started.set()
            time.sleep(0.15)
            return compendium.chapters[0]

        monkeypatch.setattr("Skoleverksted.backend.platform.router.repair_compendium_chapter", slow_success)
        outcome: list[object] = []
        worker = threading.Thread(
            target=lambda: outcome.append(
                _run_repair_with_timeout(compendium, compendium.chapters[0].id, operation_id="first")
            ),
            daemon=True,
        )
        worker.start()
        assert started.wait(1)
        with pytest.raises(RepairInProgressError) as error:
            _run_repair_with_timeout(compendium, compendium.chapters[0].id, operation_id="second")
        assert error.value.operation_id == "first"
        worker.join(timeout=2)
        assert len(outcome) == 1


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
        monkeypatch.setattr(
            "Skoleverksted.backend.platform.compendium.audit_truth",
            lambda **kwargs: _verified_truth(kwargs["content"]),
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


def test_automatic_repair_can_upgrade_weak_sources_without_existing_notes(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        compendium = PlatformStore(Path(tmp) / "platform.sqlite3").create_compendium(_proposal())
        chapter = compendium.chapters[0]
        chapter.content_markdown = "## Kapittel\n\n" + (
            "Ideologier påvirket politiske konflikter og samfunnsendringer. " * 20
        )
        chapter.status = "approved"
        chapter.sources = [
            CompendiumSource(
                title="Political ideology – Wikipedia",
                url="https://en.wikipedia.org/wiki/Political_ideology",
            )
        ]
        calls = 0

        def upgrade_then_verify(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return ({
                    "content_markdown": chapter.content_markdown,
                    "changes": ["Wikipedia ble erstattet med en konkret fagartikkel."],
                    "key_facts": ["Ideologier gir ulike svar på politiske spørsmål."],
                    "glossary": ["Ideologi – et sammenhengende sett av politiske ideer"],
                    "sources": [{
                        "title": "Ideologi",
                        "url": "https://snl.no/ideologi",
                        "publisher": "Store norske leksikon",
                    }],
                }, [])
            return ({
                "approved": True,
                "notes": [],
                "unsafe_claims": [],
            }, [])

        monkeypatch.setattr(
            "Skoleverksted.backend.platform.compendium._call_google_json",
            upgrade_then_verify,
        )
        monkeypatch.setattr(
            "Skoleverksted.backend.platform.compendium.audit_truth",
            lambda **kwargs: _verified_truth(kwargs["content"]),
        )

        repaired = repair_compendium_chapter(compendium, chapter.id)
        assert repaired.status == "generated"
        assert repaired.sources[0].url == "https://snl.no/ideologi"
        assert repaired.revision_summary == [
            "Wikipedia ble erstattet med en konkret fagartikkel."
        ]
        assert not _source_quality_notes(repaired.sources)


def test_automatic_repair_keeps_unresolved_claims_for_teacher_control(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        compendium = PlatformStore(Path(tmp) / "platform.sqlite3").create_compendium(_proposal())
        chapter = compendium.chapters[0]
        chapter.content_markdown = "## Kapittel\n\n" + ("En historisk framstilling. " * 50)
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
        assert repaired.status == "source_grounding_failed"
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
        assert repaired.status == "verification_failed"
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


def test_manual_edit_invalidates_truth_passport_and_blocks_approval(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        compendium = store.create_compendium(_proposal())
        chapter = compendium.chapters[0]
        chapter.content_markdown = "## Kontrollert tekst\n\n" + ("Dokumentert innhold. " * 20)
        chapter.status = "generated"
        chapter.truth_passport = TruthPassport(
            status="verified",
            topic=compendium.topic,
            subject=compendium.subject,
            coverage_percent=100,
            verified_claims=1,
            total_claims=1,
        )
        saved = store.replace_compendium_chapter(compendium.id, chapter)
        assert saved is not None
        monkeypatch.setattr(
            "Skoleverksted.backend.platform.router.get_platform_store",
            lambda: store,
        )

        edited = update_chapter_endpoint(
            compendium.id,
            chapter.id,
            CompendiumChapterUpdate(
                content_markdown=chapter.content_markdown + "\n\nEn ny opplysning.",
                status="generated",
            ),
        )
        assert edited.chapters[0].truth_passport is None

        with pytest.raises(HTTPException) as error:
            update_chapter_endpoint(
                compendium.id,
                chapter.id,
                CompendiumChapterUpdate(status="approved"),
            )
        assert getattr(error.value, "status_code", None) == 409


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
            "| Område | Kjennetegn |\n|---|---|\n"
            "| Eksempel | Første poeng<br>Andre poeng om produjonsmidlene |\n"
        )
        chapter.key_facts = ["Et kort, kontrollert hovedpoeng."]
        chapter.glossary = ["Len – en politisk og økonomisk forbindelse"]
        chapter.status = "approved"
    compendium.chapters[0].sources = [
        CompendiumSource(
            title="Ideologi",
            url="https://snl.no/ideologi?utm_source=test",
            publisher="Store norske leksikon",
        ),
        CompendiumSource(
            title="snl.no",
            url="https://vertexaisearch.cloud.google.com/grounding-api-redirect/temporary",
        ),
    ]
    typst = build_typst_document(compendium)
    assert "#outline(title: [Innhold], depth: 1" in typst
    assert "Ramme for framstillingen" in typst
    assert "Avgrensningskontrakt" not in typst
    assert "Avgrenses av læreren før produksjon" not in typst
    assert "Lærerens sluttkontroll" not in typst
    assert "#table(columns: 2" in typst
    assert "<br>" not in typst
    assert "produksjonsmidlene" in typst
    assert "produjonsmidlene" not in typst
    assert "vertexaisearch.cloud.google.com" not in typst
    assert '#link("https://snl.no/ideologi")' in typst
    assert "Spørsmål å ha med seg" in typst
    assert "Kort oppsummert" in typst
    assert typst.count("#pagebreak()") == 3
    assert "#block(breakable: false" in typst
    docx = build_docx(compendium)
    assert docx.startswith(b"PK")
    assert len(docx) > 10_000


def test_renderer_normalizes_escaped_markdown_line_breaks_and_heading_depth():
    rendered = markdown_to_typst(
        r"## Kapitteltittel\n\n### Første del\n\nEt vanlig avsnitt.",
        "Kapitteltittel",
    )

    assert "\\n" not in rendered
    assert "== Første del" in rendered
    assert "=== Første del" not in rendered
    assert "Et vanlig avsnitt." in rendered


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


def test_renderer_retries_without_an_invalid_optional_image(tmp_path, monkeypatch):
    bad_image = tmp_path / "generated.png"
    bad_image.write_bytes(b"RIFF\x10\x00\x00\x00WEBP-invalid")
    proposal = _proposal()
    compendium = PlatformStore(tmp_path / "platform.sqlite3").create_compendium(proposal)
    for chapter in compendium.chapters:
        chapter.content_markdown = f"## {chapter.title}\n\nKontrollert kapitteltekst."
        chapter.status = "approved"

    compile_calls: list[str | None] = []
    docx_calls: list[str] = []

    def fake_compile(_source: str, image_path: str | None = None) -> bytes:
        compile_calls.append(image_path)
        if image_path:
            raise RuntimeError("failed to decode image")
        return b"%PDF-1.4\nuten bilde\n%%EOF"

    def fake_docx(_compendium, *, image_path: str = "", image_credit: str = "") -> bytes:
        docx_calls.append(image_path)
        return b"PK\x03\x04docx"

    fake_pdf_service = ModuleType("VGS_KI.backend.pdf_service")
    fake_pdf_service.compile_typst = fake_compile
    monkeypatch.setitem(sys.modules, "VGS_KI.backend.pdf_service", fake_pdf_service)
    monkeypatch.setattr(compendium_renderer, "build_docx", fake_docx)

    pdf, docx, _, _ = compendium_renderer.render_compendium(
        compendium,
        image_path=str(bad_image),
        image_credit="KI-generert illustrasjon",
    )

    assert pdf.startswith(b"%PDF")
    assert docx.startswith(b"PK")
    assert compile_calls == [str(bad_image), None]
    assert docx_calls == [""]
