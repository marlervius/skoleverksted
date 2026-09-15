"""Review drafts terminate and survive restart, without any approval bypass."""

from contextlib import nullcontext
from io import BytesIO
import os
import shutil
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.job_store import persist_terminal_job, load_job_from_disk
from app.models.state import GenerationRequest, PipelineState, PipelineStatus, LatexCompilationResult
from app.pipeline.agents import release_repair
from app.verification.latex_checker import LatexChecker


@pytest.fixture
def draft(monkeypatch):
    state = PipelineState(
        owner_id="teacher", request=GenerationRequest(grade="VG1 1T", topic="Funksjoner", include_exercises=False, include_theory=False),
        full_document=r"\documentclass{article}\begin{document}$f(0)=4$\end{document}",
        pdf_base64="stale", pdf_path="stale.pdf", source_approved=True,
        teacher_approved_at="old", release_manifest={"file_hash": "old"},
        latex_compilation=LatexCompilationResult(success=True, pdf_base64="stale"),
    )
    model = Mock()
    model.invoke.return_value = '{"edits": []}'
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kwargs: model)
    assert not release_repair.prepare_release(state)
    assert state.status == PipelineStatus.REVIEW_REQUIRED
    assert model.invoke.call_count == 2
    persist_terminal_job(state)
    return state


@pytest.fixture
def client(monkeypatch, draft):
    monkeypatch.setattr(main, "_jobs", {draft.job_id: draft})
    main.app.dependency_overrides[main.get_current_user] = lambda: "teacher"
    main.app.dependency_overrides[main.require_stream_access] = lambda: "teacher"
    with TestClient(main.app) as client:
        yield client
    main.app.dependency_overrides.clear()


def test_review_state_preserves_exact_draft_and_clears_all_release_proof(draft):
    assert not draft.source_approved and not draft.teacher_approved_at
    assert not draft.pdf_base64 and not draft.pdf_path and not draft.release_manifest
    assert not draft.latex_compilation.pdf_base64
    assert not draft.current_agent
    persist_terminal_job(draft)
    restored = load_job_from_disk(draft.job_id)
    assert restored.status == PipelineStatus.REVIEW_REQUIRED
    assert restored.full_document == draft.full_document
    assert restored.math_verification.claims_unparseable == 1


def test_review_status_result_stream_and_export_gates(client, draft):
    url = f"/generate/{draft.job_id}"
    status = client.get(url + "/status").json()
    assert status["ready"] and status["status"] == "review_required"
    result = client.get(url + "/result?include_pdf_base64=true").json()
    assert result["full_document"] == draft.full_document
    assert not result["pdf_available"] and not result["pdf_base64"]
    assert '"status": "review_required"' in client.get(url + "/stream").text
    assert client.get(url + "/pdf").status_code == 409
    assert client.get(url + "/pdf?preview=true").status_code == 409
    assert client.post(url + "/approve").status_code == 409
    assert client.post("/sharing", json={"resource_type": "generation", "resource_id": draft.job_id}).status_code == 409


def test_draft_preview_compiles_watermarked_copy_without_changing_source(client, draft, monkeypatch):
    original = draft.full_document
    def compile_draft(self, text):
        assert r"\SetWatermarkText{UTKAST -- IKKE GODKJENT}" in text
        assert "$f(0)=4$" in text
        return LatexCompilationResult(success=True, pdf_bytes=b"%PDF-draft")
    monkeypatch.setattr(LatexChecker, "check", compile_draft)
    response = client.get(f"/generate/{draft.job_id}/draft-preview")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert draft.full_document == original
    assert not draft.source_approved and not draft.pdf_base64


def test_draft_preview_requires_owner(client, draft):
    main.app.dependency_overrides[main.get_current_user] = lambda: "different-teacher"
    assert client.get(f"/generate/{draft.job_id}/draft-preview").status_code == 403


def test_malformed_draft_preview_returns_actionable_error(client, draft):
    draft.full_document = "$f(0)=4$"
    response = client.get(f"/generate/{draft.job_id}/draft-preview")
    assert response.status_code == 422
    assert "LaTeX-teksten er bevart" in response.json()["detail"]


def test_durable_queue_terminates_as_needs_review(draft, monkeypatch):
    queue = Mock()
    queue.claim.return_value = nullcontext()
    monkeypatch.setattr(main, "get_durable_job_queue", lambda: queue)
    monkeypatch.setattr(main, "_jobs", {draft.job_id: draft})
    monkeypatch.setattr(main, "_run_job_body", lambda *args: None)
    main._run_job(draft.job_id, draft.request, draft.owner_id)
    queue.needs_review.assert_called_once()
    queue.finish.assert_not_called()


def test_real_draft_pdf_marks_every_page(client, draft):
    if not shutil.which("pdflatex"):
        if os.getenv("CI"):
            pytest.fail("Required CI must install pdflatex")
        pytest.skip("Real watermark compilation runs in required CI")
    draft.full_document = r"\documentclass{article}\begin{document}Page one\newpage Page two\end{document}"
    response = client.get(f"/generate/{draft.job_id}/draft-preview")
    assert response.status_code == 200, response.text
    from pypdf import PdfReader
    pages = PdfReader(BytesIO(response.content)).pages
    assert len(pages) == 2
    for page in pages:
        text = page.extract_text()
        assert "UTKAST" in text and "IKKE GODKJENT" in text
