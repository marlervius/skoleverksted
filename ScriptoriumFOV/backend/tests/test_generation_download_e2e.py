import io
from pathlib import Path

import pytest
from pypdf import PdfReader

from ScriptoriumFOV.backend import main
from ScriptoriumFOV.backend.progress_store import clear_progress, initialize_progress


PDF_FIXTURE = Path(__file__).resolve().parents[3] / "test_laeringsark.pdf"


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
            "truth_passport": {"status": "verified", "version": "2.0"},
            "verification_content": "Kontrollert innhold",
            "quarantine": [],
            "quality_rounds": [],
            "quality_stop_reason": "source_approved",
        },
    )
    monkeypatch.setattr(
        main,
        "_materialize_pedagogical_image",
        lambda *_args, **_kwargs: (None, None, "", ""),
    )
    monkeypatch.setattr(main, "create_lesson_pdf", lambda **_kwargs: PDF_FIXTURE.read_bytes())
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
    """A teacher can inspect a valid PDF before the final export gate opens."""

    job_id = "norsk-preview-before-approval"
    clear_progress(job_id)
    initialize_progress(job_id, 4, "Starter", request_id="request-preview")
    pdf_bytes = PDF_FIXTURE.read_bytes()
    artifact = main.ValidatedArtifact(
        content=pdf_bytes,
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
        assert preview.body == pdf_bytes

        with pytest.raises(main.HTTPException) as blocked:
            main.download_pdf(job_id, None)
        assert blocked.value.status_code == 409
    finally:
        clear_progress(job_id)
