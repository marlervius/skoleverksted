"""Manual language review: no model audit, explicit approval, immutable file."""
import io
import json
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from ScriptoriumFOV.backend import main
from ScriptoriumFOV.backend.pdf_service import create_lesson_pdf
from ScriptoriumFOV.backend.progress_store import clear_progress, initialize_progress, merge_progress
from ScriptoriumFOV.backend.teacher_review import REVIEW_MODE
from ScriptoriumFOV.backend.tests.pdf_fixture import build_valid_pdf_bytes
from Skoleverksted.backend.platform import quality_gate

TEXT = "Lærerens tekst om et syntetisk tema."
WORKSHEET = "a) VIKTIGE BEGREPER\nBuss: Et stort kjøretøy.\nSkole: Et sted for læring.\nLærer: En person som underviser."
PDF = build_valid_pdf_bytes()


@pytest.fixture
def manual_job(monkeypatch):
    job = "manual-review-regression"
    clear_progress(job)
    initialize_progress(job, 3, "Starter")
    def forbidden(**kwargs):
        raise AssertionError("No automatic source or fact audit may run for this product")
    monkeypatch.setattr(quality_gate, "run_quality_pipeline", forbidden)
    monkeypatch.setattr(main, "create_lesson_pdf", lambda **kwargs: PDF)
    request = main.PreviewPDFRequest(topic="Syntetisk", subject="Norsk", level="A2.1",
        text=TEXT, worksheet=WORKSHEET, teacher_key_content="Lærerens fasit.", options={})
    main.generate_pdf_from_json_background(job, request)
    yield job
    clear_progress(job)


def approve(job):
    return main.approve_generation(job, None, main.TeacherApproval(content_reviewed=True))


def test_new_job_is_preserved_for_manual_review_without_a_verified_passport(manual_job):
    state = main.get_progress(manual_job)
    assert state["job_status"] == "completed"
    document = state["quality_documents"][0]
    assert document["review_mode"] == REVIEW_MODE
    assert not document.get("truth_passport")
    assert not document.get("release_manifest")
    content = json.loads(document["content"])
    assert content["text"] == TEXT
    assert content["worksheet"] == WORKSHEET
    assert content["teacher_key_content"] == "Lærerens fasit."
    assert state["quality_review"]["status"] == "teacher_review"
    assert main.download_pdf(manual_job, None, preview=True).body == PDF
    with pytest.raises(main.HTTPException) as error:
        main.download_pdf(manual_job, None)
    assert error.value.status_code == 409


@pytest.mark.parametrize("body", [None, main.TeacherApproval(content_reviewed=False)])
def test_manual_review_is_an_explicit_human_decision(manual_job, body):
    with pytest.raises(main.HTTPException) as error:
        main.approve_generation(manual_job, None, body)
    assert error.value.status_code == 409
    assert not main.get_progress(manual_job)["quality_documents"][0]["teacher_approved_at"]


def test_http_approval_requires_a_real_boolean_and_releases_the_exact_pdf(manual_job, monkeypatch):
    monkeypatch.setitem(main.app.dependency_overrides, main.require_app_password, lambda: None)
    client = TestClient(main.app)
    try:
        url = f"/generation/{manual_job}/approve"
        assert client.post(url).status_code == 409
        assert client.post(url, json={"content_reviewed": "true"}).status_code == 422
        assert client.post(url, json={"content_reviewed": True}).status_code == 200
        response = client.get(f"/download-pdf/{manual_job}")
        assert response.status_code == 200
        assert response.content == PDF
    finally:
        client.close()


@pytest.mark.parametrize("change", ["content", "file", "pending"])
def test_a_changed_revision_file_or_job_state_invalidates_approval(manual_job, change):
    approve(manual_job)
    state = main.get_progress(manual_job)
    if change == "content":
        docs = [dict(item) for item in state["quality_documents"]]
        docs[0]["content"] = docs[0]["content"].replace(TEXT, "Endret tekst.")
        merge_progress(manual_job, quality_documents=docs)
    elif change == "file":
        merge_progress(manual_job, pdf_bytes=PDF + b"changed")
    else:
        merge_progress(manual_job, job_status="running")
    with pytest.raises(main.HTTPException) as error:
        main.download_pdf(manual_job, None)
    assert error.value.status_code in {202, 409}


def test_trainer_uses_the_manually_approved_material(manual_job):
    with pytest.raises(main.HTTPException):
        main.download_trainer(manual_job, None)
    approve(manual_job)
    response = main.download_trainer(manual_job, None)
    html = response.body.decode("utf-8")
    assert "Buss" in html and "Skole" in html
    assert "Innholdet kontrolleres av lærer" in html
    assert "IKKE KILDEGODKJENT" not in html


@pytest.mark.parametrize("mode", ["dual", "multi"])
def test_every_level_in_a_zip_is_bound_to_the_manual_approval(monkeypatch, mode):
    job = f"manual-{mode}"
    clear_progress(job)
    initialize_progress(job, 4, "Starter")
    def generated(**kwargs):
        return {"text": TEXT, "worksheet": WORKSHEET, "review_mode": REVIEW_MODE,
                "verification_content": json.dumps({"text": TEXT, "worksheet": WORKSHEET})}
    monkeypatch.setattr(main, "generate_lesson_content", generated)
    monkeypatch.setattr(main, "create_lesson_pdf", lambda **kwargs: PDF)
    monkeypatch.setattr(main, "_materialize_pedagogical_image", lambda *a, **k: (None, None, "", ""))
    pool = ThreadPoolExecutor(max_workers=3)
    monkeypatch.setattr(main, "_executor", pool)
    try:
        if mode == "dual":
            main._generate_dual_background(job, main.LessonRequest(topic="Syntetisk", subject="Norsk", level="A2.1"))
            count = 2
        else:
            main._generate_multi_level_background(job, main.MultiLevelLessonRequest(
                topic="Syntetisk", subject="Norsk", levels=["A1.1", "A2.1", "B1.1"]))
            count = 3
        state = main.get_progress(job)
        assert state["job_status"] == "completed"
        assert len(state["quality_documents"]) == count
        with pytest.raises(main.HTTPException):
            main.download_zip(job, None)
        approve(job)
        response = main.download_zip(job, None)
        assert len(zipfile.ZipFile(io.BytesIO(response.body)).namelist()) == count
        merge_progress(job, zip_bytes=response.body + b"changed")
        with pytest.raises(main.HTTPException):
            main.download_zip(job, None)
    finally:
        pool.shutdown(wait=True)
        clear_progress(job)


def test_manual_language_approval_cannot_open_other_modules_gates(manual_job):
    approve(manual_job)
    with pytest.raises(main.HTTPException):
        main._require_norsk_documents(main.get_progress(manual_job), "fag.pdf", teacher=True)
    with pytest.raises(PermissionError):
        quality_gate.require_export_ready(
            export_id="fag.pdf", content=TEXT, verification_status="not_evaluated",
            verified_revision="", verification_version="", teacher_approved=True, approved_revision="",
        )


@pytest.mark.skipif(shutil.which("typst") is None, reason="typst is required for PDF rendering")
def test_manual_pdf_renders_without_a_source_gate_banner_and_has_a_small_review_note():
    pdf = create_lesson_pdf(content_text=TEXT, worksheet_text=WORKSHEET, topic="Syntetisk",
                            subject="Norsk", level="A2.1", manual_review=True)
    text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    assert "Innholdet kontrolleres av lærer" in text
    assert "IKKE KILDEGODKJENT" not in text
    assert "Lærerens tekst" in text
