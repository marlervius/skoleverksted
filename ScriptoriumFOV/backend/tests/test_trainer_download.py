"""The concept trainer is released under exactly the PDF's rules.

A final download needs source approval and the teacher's approval of the exact
verified revision; a draft job yields only a watermarked teacher preview; and
the trainer is built from the verified document, never from request fields.
"""

import json
from types import SimpleNamespace

import pytest

from ScriptoriumFOV.backend import main
from ScriptoriumFOV.backend.progress_store import clear_progress, initialize_progress
from ScriptoriumFOV.backend.tests.pdf_fixture import build_valid_pdf_bytes
from Skoleverksted.backend.platform.models import ReleaseManifest, TruthPassport
from Skoleverksted.backend.platform.quality_gate import (
    EXPORT_CONTRACTS,
    QualityGateResult,
    content_digest,
)

PDF_FIXTURE = build_valid_pdf_bytes()
JOB = "norsk-trainer-gate"
META = {"topic": "Demokrati i Norge", "subject": "Samfunnsfag", "level": "A2.1"}
TEXT = "Norge er et demokrati. I et demokrati kan alle stemme. Folket velger politikere."
WORKSHEET = (
    "a) VIKTIGE BEGREPER\nDemokrati: Folket bestemmer sammen.\n"
    "Politiker: En person som jobber med politikk.\nStemme: Å velge noe ved valg."
)


def _sheet(text: str = TEXT, worksheet: str = WORKSHEET) -> str:
    return json.dumps({"text": text, "worksheet": worksheet, "language_exercises": None}, ensure_ascii=False)


def _manifest(content: str) -> dict:
    return ReleaseManifest(
        document_revision_id="fixture-revision",
        document_hash=content_digest(content),
        renderer_version="test",
    ).model_dump(mode="json")


def _document(content: str, *, verified: bool = True, approved_digest: str = "", approved: bool = False) -> dict:
    return {
        "content": content,
        "truth_passport": {
            "status": "verified" if verified else "needs_review",
            "version": "3.0",
            "content_revision": content_digest(content),
        },
        "release_manifest": _manifest(content),
        "quarantine": [],
        "quality_rounds": [],
        "quality_stop_reason": "source_approved" if verified else "truth_layer_unresolved_claims",
        "teacher_approved_at": "2026-10-05T10:00:00Z" if approved else None,
        "approved_digest": approved_digest,
    }


@pytest.fixture
def job():
    clear_progress(JOB)
    initialize_progress(JOB, 4, "Starter", request_id="request-trainer")
    yield JOB
    clear_progress(JOB)


def _publish(job_id, documents, *, draft=False, meta=META, review_preview=None):
    artifact = main.ValidatedArtifact(
        content=PDF_FIXTURE,
        content_type="application/pdf",
        filename="Demokrati.pdf",
        kind="student_pdf",
    )
    main._publish_validated_artifact(
        job_id,
        artifact,
        payload_key="pdf_bytes",
        total_steps=4,
        quality_documents=documents,
        ready_message="PDF klar.",
        terminal_status="needs_teacher_review" if draft else "completed",
        draft=draft,
        review_preview=review_preview,
        lesson_meta=meta,
    )


def test_the_trainer_is_a_registered_export_under_the_global_quality_contract():
    assert "norsk.trainer" in EXPORT_CONTRACTS


def test_a_final_download_needs_the_teachers_approval_of_the_exact_revision(job):
    content = _sheet()
    _publish(job, [_document(content)])

    with pytest.raises(main.HTTPException) as blocked:
        main.download_trainer(job, None)
    assert blocked.value.status_code == 409
    assert "lærergodkjenning mangler" in str(blocked.value.detail)

    assert main.approve_generation(job, None)["status"] == "approved"
    response = main.download_trainer(job, None)

    assert response.media_type == "text/html"
    assert response.headers["content-disposition"].startswith("attachment;")
    # Same filename rules as the PDF: spaces are kept and percent-encoded in the header.
    assert "Demokrati%20i%20Norge_begrepstrener.html" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-length"] == str(len(response.body))
    html = response.body.decode("utf-8")
    assert "Politiker" in html and "UTKAST" not in html


def test_an_edit_after_approval_invalidates_it_for_the_trainer_too(job):
    revised = _sheet(worksheet=WORKSHEET + "\nLover: Regler som gjelder for alle.")
    original = _sheet()
    _publish(job, [_document(revised, approved=True, approved_digest=content_digest(original))])

    with pytest.raises(main.HTTPException) as blocked:
        main.download_trainer(job, None)
    assert blocked.value.status_code == 409
    assert "annen innholdsversjon" in str(blocked.value.detail)


def test_a_draft_job_has_no_final_trainer_only_a_watermarked_teacher_preview(job):
    _publish(job, [_document(_sheet(), verified=False)], draft=True)

    with pytest.raises(main.HTTPException) as blocked:
        main.download_trainer(job, None)
    assert blocked.value.status_code == 409
    assert "lærergjennomgang kreves" in str(blocked.value.detail)

    preview = main.download_trainer(job, None, preview=True)
    assert preview.headers["x-preview-draft"] == "true"
    assert preview.headers["cache-control"] == "no-store"
    assert preview.headers["content-disposition"].startswith("inline;")
    assert "UTKAST_" in preview.headers["content-disposition"]
    html = preview.body.decode("utf-8")
    assert "UTKAST – IKKE KILDEGODKJENT" in html


def test_a_completed_job_whose_passport_is_not_green_is_not_previewable_either(job):
    _publish(job, [_document(_sheet(), verified=False)])

    with pytest.raises(main.HTTPException) as blocked:
        main.download_trainer(job, None, preview=True)
    assert blocked.value.status_code == 409
    assert "ikke kildegodkjent" in str(blocked.value.detail)


def test_a_source_approved_preview_is_allowed_before_the_teacher_approves(job):
    _publish(job, [_document(_sheet())])

    preview = main.download_trainer(job, None, preview=True)

    assert preview.headers["x-preview-draft"] == "false"
    assert "UTKAST" not in preview.body.decode("utf-8")


def test_the_trainer_is_built_from_the_verified_document_not_from_other_fields(job):
    verified = _sheet(worksheet=WORKSHEET)
    leaked = _sheet(worksheet="a) VIKTIGE BEGREPER\nUverifisert: Noe som ikke er kontrollert.\nEnnå: Mer som ikke er kontrollert.")
    _publish(
        job,
        [_document(verified, approved=True, approved_digest=content_digest(verified))],
        review_preview={"topic": "x", "text": leaked, "worksheet": json.loads(leaked)["worksheet"]},
    )

    html = main.download_trainer(job, None).body.decode("utf-8")

    assert "Uverifisert" not in html
    assert "Demokrati" in html


def test_unknown_and_unfinished_jobs_are_reported_like_the_pdf(job):
    with pytest.raises(main.HTTPException) as unknown:
        main.download_trainer("finnes-ikke", None)
    assert unknown.value.status_code == 404

    with pytest.raises(main.HTTPException) as running:
        main.download_trainer(job, None)
    assert running.value.status_code == 202


def test_a_job_without_lesson_metadata_or_with_several_documents_is_unsupported(job):
    content = _sheet()
    approved = _document(content, approved=True, approved_digest=content_digest(content))
    _publish(job, [approved], meta=None)
    with pytest.raises(main.HTTPException) as no_meta:
        main.download_trainer(job, None)
    assert no_meta.value.status_code == 409

    clear_progress(job)
    initialize_progress(job, 4, "Starter")
    _publish(job, [approved, approved])
    with pytest.raises(main.HTTPException) as several:
        main.download_trainer(job, None)
    assert several.value.status_code == 409
    assert "ett nivå om gangen" in str(several.value.detail)


def test_a_sheet_without_enough_terms_gives_a_clear_422_not_an_empty_trainer(job):
    content = _sheet(worksheet="a) LESEFORSTÅELSE\n1. Hva er et demokrati?")
    _publish(job, [_document(content, approved=True, approved_digest=content_digest(content))])

    with pytest.raises(main.HTTPException) as unavailable:
        main.download_trainer(job, None)
    assert unavailable.value.status_code == 422
    assert "minst to begreper" in str(unavailable.value.detail)


# ---------------------------------------------------------------------------
# The generation paths record the metadata the trainer needs
# ---------------------------------------------------------------------------


def _content(content: str) -> dict:
    return {
        "text": TEXT,
        "worksheet": WORKSHEET,
        "verification_content": content,
        "truth_passport": {"status": "verified", "version": "3.0", "content_revision": content_digest(content)},
        "release_manifest": _manifest(content),
        "quality_status": "source_approved",
    }


def test_the_direct_generation_path_stores_lesson_metadata_and_yields_a_trainer(monkeypatch, job):
    content = _sheet()
    monkeypatch.setattr(main, "generate_lesson_content", lambda **_kwargs: _content(content))
    monkeypatch.setattr(main, "_materialize_pedagogical_image", lambda *_a, **_k: (None, None, "", ""))
    monkeypatch.setattr(main, "create_lesson_pdf", lambda **_kwargs: PDF_FIXTURE)
    monkeypatch.setattr(main, "_cleanup_image", lambda _path: None)

    main.generate_lesson_background(
        job, main.LessonRequest(topic="Demokrati i Norge", subject="Samfunnsfag", level="A2.1")
    )

    state = main.get_progress(job)
    assert state["job_status"] == "completed"
    assert state["lesson_meta"] == META
    main.approve_generation(job, None)
    assert b"Politiker" in main.download_trainer(job, None).body


def test_the_preview_to_pdf_path_stores_lesson_metadata_and_uses_the_revised_content(monkeypatch, job):
    revised = _sheet(worksheet=WORKSHEET + "\nLover: Regler som gjelder for alle.")
    passport = TruthPassport(
        version="3.0", status="verified", content_revision=content_digest(revised),
        claims=[], sources=[], register_complete=True,
    )
    quality = QualityGateResult(
        approved_content=revised,
        passport=passport,
        rounds=[],
        quarantine=[],
        stop_reason="source_approved",
        deterministic_failures=[],
        release_manifest=ReleaseManifest(
            document_revision_id="fixture-revision",
            document_hash=content_digest(revised),
            renderer_version="test",
        ),
    )
    monkeypatch.setattr(main, "run_quality_pipeline", lambda **_kwargs: quality)
    monkeypatch.setattr(main, "create_lesson_pdf", lambda **_kwargs: PDF_FIXTURE)

    request = main.PreviewPDFRequest(
        topic="Demokrati i Norge",
        subject="Samfunnsfag",
        level="A2.1",
        text=TEXT,
        worksheet=WORKSHEET,
        options={"grammar_tasks": True},
    )
    main.generate_pdf_from_json_background(job, request)

    state = main.get_progress(job)
    assert state["job_status"] == "completed"
    assert state["lesson_meta"] == META
    main.approve_generation(job, None)
    html = main.download_trainer(job, None).body.decode("utf-8")
    assert "Lover" in html  # the gate's revised wording, not the request's original
