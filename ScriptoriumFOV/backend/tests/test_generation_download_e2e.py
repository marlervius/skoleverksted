import io
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from ScriptoriumFOV.backend import main
from ScriptoriumFOV.backend.progress_store import clear_progress, initialize_progress
from Skoleverksted.backend.platform.quality_gate import content_digest
from Skoleverksted.backend.platform.models import ReleaseManifest
from ScriptoriumFOV.backend.tests.pdf_fixture import build_valid_pdf_bytes


PDF_FIXTURE = build_valid_pdf_bytes()


def _manifest(content: str) -> dict[str, object]:
    return ReleaseManifest(
        document_revision_id="fixture-revision",
        document_hash=content_digest(content),
        renderer_version="test",
    ).model_dump(mode="json")


def test_norsk_generation_publishes_and_serves_a_valid_pdf(monkeypatch):
    job_id = "norsk-e2e-download"
    clear_progress(job_id)
    initialize_progress(job_id, 4, "Starter", request_id="request-e2e")
    monkeypatch.setattr(
        main,
        "generate_lesson_content",
        lambda **_kwargs: {
            "text": "Norge er et land i Europa.",
            "worksheet": "a) VIKTIGE BEGREPER\nEuropa: et kontinent.",
            "verification_content": "Kontrollert innhold",
            "truth_passport": {
                "status": "verified",
                "version": "3.0",
                "content_revision": content_digest("Kontrollert innhold"),
            },
            "release_manifest": _manifest("Kontrollert innhold"),
            "quality_status": "source_approved",
        },
    )
    monkeypatch.setattr(
        main,
        "_materialize_pedagogical_image",
        lambda *_args, **_kwargs: (None, None, "", ""),
    )
    monkeypatch.setattr(main, "create_lesson_pdf", lambda **_kwargs: PDF_FIXTURE)
    monkeypatch.setattr(main, "_cleanup_image", lambda _path: None)
    monkeypatch.setattr(main, "_require_norsk_documents", lambda *_args, **_kwargs: None)

    try:
        request = main.LessonRequest(topic="Arbeidsliv", subject="Norsk", level="A2.1")
        main.generate_lesson_background(job_id, request)

        state = main.get_progress(job_id)
        assert state["job_status"] == "completed"
        assert state["artifact"]["id"].startswith(f"{job_id}:student_pdf:")
        assert state["artifact"]["download_url"].endswith(f"/download-pdf/{job_id}")
        status = main.get_generation_status(job_id, None)
        assert status["status"] == "completed"
        assert status["event_type"] == "done"
        assert status["artifact"]["id"] == state["artifact"]["id"]

        response = main.download_pdf(job_id, None)
        assert response.media_type == "application/pdf"
        assert response.headers["content-length"] == str(len(response.body))
        assert response.headers["x-artifact-id"] == state["artifact"]["id"]
        reader = PdfReader(io.BytesIO(response.body))
        assert len(reader.pages) >= 1
    finally:
        clear_progress(job_id)


def test_preview_download_is_available_before_final_quality_approval():
    job_id = "norsk-preview-before-approval"
    clear_progress(job_id)
    initialize_progress(job_id, 4, "Starter", request_id="request-preview")
    artifact = main.ValidatedArtifact(
        content=PDF_FIXTURE,
        content_type="application/pdf",
        filename="Arbeidsliv.pdf",
        kind="student_pdf",
    )

    try:
        main._publish_validated_artifact(
            job_id,
            artifact,
            payload_key="pdf_bytes",
            total_steps=4,
            quality_documents=[
                {
                    "content": "Kontrollert innhold",
                    "truth_passport": {"status": "needs_review", "version": "1.0"},
                    "quarantine": [],
                }
            ],
            ready_message="PDF klar for lærerens kontroll.",
        )

        preview = main.download_pdf(job_id, None, preview=True)
        assert preview.media_type == "application/pdf"
        assert preview.headers["content-disposition"].startswith("inline;")
        assert preview.body == PDF_FIXTURE

        with pytest.raises(main.HTTPException) as blocked:
            main.download_pdf(job_id, None)
        assert blocked.value.status_code == 409
    finally:
        clear_progress(job_id)


def test_source_approved_preview_requires_teacher_approval_then_downloads():
    job_id = "norsk-approved-export"
    clear_progress(job_id)
    initialize_progress(job_id, 4, "Starter", request_id="request-approved")
    content = "Kontrollert innhold"
    quality_document = {
        "content": content,
        "truth_passport": {
            "status": "verified",
            "version": "3.0",
            "content_revision": content_digest(content),
        },
        "release_manifest": _manifest(content),
        "quarantine": [],
        "quality_rounds": [],
        "quality_stop_reason": "source_approved",
        "teacher_approved_at": None,
        "approved_digest": "",
    }
    artifact = main.ValidatedArtifact(
        content=PDF_FIXTURE,
        content_type="application/pdf",
        filename="Arbeidsliv.pdf",
        kind="student_pdf",
    )
    try:
        main._publish_validated_artifact(
            job_id,
            artifact,
            payload_key="pdf_bytes",
            total_steps=4,
            quality_documents=[quality_document],
            ready_message="PDF klar for lærerens kontroll.",
        )
        preview = main.download_pdf(job_id, None, preview=True)
        assert preview.body == PDF_FIXTURE
        with pytest.raises(main.HTTPException) as blocked:
            main.download_pdf(job_id, None)
        assert blocked.value.status_code == 409

        approved = main.approve_generation(job_id, None)
        assert approved["status"] == "approved"
        response = main.download_pdf(job_id, None)
        assert response.body == PDF_FIXTURE
        assert response.headers["content-disposition"].startswith("attachment;")
    finally:
        clear_progress(job_id)


def test_teacher_revision_invalidates_previous_approval():
    job_id = "norsk-approval-revision"
    clear_progress(job_id)
    initialize_progress(job_id, 4, "Starter")
    original = "Kontrollert innhold"
    revised = "Kontrollert innhold, redigert av lærer"
    quality_document = {
        "content": revised,
        "truth_passport": {
            "status": "verified",
            "version": "2.0",
            "content_revision": content_digest(revised),
        },
        "quarantine": [],
        "teacher_approved_at": "2026-08-25T20:00:00Z",
        "approved_digest": content_digest(original),
    }
    artifact = main.ValidatedArtifact(
        content=PDF_FIXTURE,
        content_type="application/pdf",
        filename="Arbeidsliv.pdf",
        kind="student_pdf",
    )
    try:
        main._publish_validated_artifact(
            job_id,
            artifact,
            payload_key="pdf_bytes",
            total_steps=4,
            quality_documents=[quality_document],
            ready_message="PDF klar.",
        )
        with pytest.raises(main.HTTPException) as blocked:
            main.download_pdf(job_id, None)
        assert blocked.value.status_code == 409
        assert "annen innholdsversjon" in str(blocked.value.detail)
    finally:
        clear_progress(job_id)


def test_preview_pdf_finishes_for_manual_review_and_needs_explicit_approval(monkeypatch):
    job_id = "norsk-preview-manual-review"
    clear_progress(job_id)
    initialize_progress(job_id, 3, "Starter")
    monkeypatch.setattr(main, "create_lesson_pdf", lambda **kwargs: PDF_FIXTURE)
    try:
        request = main.PreviewPDFRequest(topic="Arbeidsliv", subject="Norsk", level="A2.1",
            text="Lærerens tekst.", worksheet="a) Oppgave", options={})
        main.generate_pdf_from_json_background(job_id, request)
        state = main.get_progress(job_id)
        assert state["job_status"] == "completed"
        assert state["last_event"]["type"] == "done"
        assert state["quality_review"]["status"] == "teacher_review"
        assert not state["quality_documents"][0].get("truth_passport")
        assert main.download_pdf(job_id, None, preview=True).body == PDF_FIXTURE
        with pytest.raises(main.HTTPException) as blocked:
            main.download_pdf(job_id, None)
        assert blocked.value.status_code == 409
        with pytest.raises(main.HTTPException):
            main.approve_generation(job_id, None)
        main.approve_generation(job_id, None, main.TeacherApproval(content_reviewed=True))
        assert main.download_pdf(job_id, None).body == PDF_FIXTURE
    finally:
        clear_progress(job_id)
