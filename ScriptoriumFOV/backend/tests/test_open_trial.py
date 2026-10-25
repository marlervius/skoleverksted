"""The real Norsk routes are code-free only for new capability-scoped work."""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ScriptoriumFOV.backend import main
from ScriptoriumFOV.backend.progress_store import clear_progress
from ScriptoriumFOV.backend.tests.pdf_fixture import build_valid_pdf_bytes
from Skoleverksted.backend.platform.access import AccessGateMiddleware
from Skoleverksted.backend.platform.models import ReleaseManifest
from Skoleverksted.backend.platform.quality_gate import content_digest


@pytest.fixture
def trial(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "private-pilot-test-code")
    monkeypatch.setenv("NORSK_OPEN_ACCESS", "1")
    # No model or worker call: this tests HTTP auth and ID assignment only.
    monkeypatch.setattr(main, "_run_durable_fov_job", lambda job_id, *_: main.cancel_progress(job_id))
    app = FastAPI()
    app.add_middleware(AccessGateMiddleware)
    app.mount("/api/norsk", main.app)
    return TestClient(app)


def test_real_preview_endpoint_creates_a_public_job_without_a_code(trial):
    response = trial.post("/api/norsk/generate-lesson-json", json={
        "subject": "Norsk", "topic": "Biblioteket", "level": "A2.1",
    })
    assert response.status_code == 200
    job_id = response.json()["generation_id"]
    try:
        assert job_id.startswith("open-")
        assert trial.get(f"/api/norsk/generation-status/{job_id}").status_code == 200
        assert trial.get("/api/norsk/download-json/private-pilot-id").status_code == 401
    finally:
        clear_progress(job_id)


def test_open_pdf_still_requires_source_and_exact_revision_teacher_approval(trial):
    job_id = f"open-{uuid4()}"
    main.initialize_progress(job_id, 4, "Test")
    content = "Kontrollert innhold"
    document = {
        "content": content,
        "truth_passport": {"status": "verified", "version": "3.0", "content_revision": content_digest(content)},
        "release_manifest": ReleaseManifest(
            document_revision_id="open-fixture", document_hash=content_digest(content), renderer_version="test",
        ).model_dump(mode="json"),
        "quarantine": [], "quality_rounds": [], "quality_stop_reason": "source_approved",
        "teacher_approved_at": None, "approved_digest": "",
    }
    pdf = build_valid_pdf_bytes()
    artifact = main.ValidatedArtifact(content=pdf, content_type="application/pdf", filename="Test.pdf", kind="student_pdf")
    try:
        main._publish_validated_artifact(
            job_id, artifact, payload_key="pdf_bytes", total_steps=4,
            quality_documents=[document], ready_message="Klar for kontroll",
        )
        url = f"/api/norsk/download-pdf/{job_id}"
        assert trial.get(url + "?preview=true").status_code == 200
        assert trial.get(url).status_code == 409
        assert trial.post(f"/api/norsk/generation/{job_id}/approve").status_code == 200
        assert trial.get(url).content == pdf
        main.merge_progress(job_id, quality_documents=[{**document, "content": "Endret innhold"}])
        assert trial.get(url).status_code == 409
    finally:
        clear_progress(job_id)
