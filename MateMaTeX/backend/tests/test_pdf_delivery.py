"""Release gates and restoration, plus an actual compiler check in CI."""
import os
import shutil

import pytest
from fastapi.testclient import TestClient

from app import main
from app.job_store import load_job_from_disk, persist_terminal_job
from app.models.state import GenerationRequest, LatexCompilationResult, PipelineState, PipelineStatus
from app.pipeline.agents.latex_fixer import run_latex_fixer
from app.pipeline.agents.latex_validator import run_latex_validator
from app.pipeline.graph import finalize
from app.verification.latex_checker import LatexChecker
from app.verification.math_checker import MathChecker


BODY = r"""
\section*{Funksjoner}
\textbf{Regn ut funksjonsverdien. $f(x)=\frac{2x+4}{x-1}$ og
$f(0)=\frac{2 \cdot 0 + 4}{0-1}=\frac{4}{-1}=-4$.
Fortegn: $(-4)^2-9=7>0$.
Regnekjede: $2 \cdot (3 + 1) = 6 + 2 = 8$.
Desimaltall: $1 - 0{,}85 = 0{,}15$.
"""


@pytest.fixture
def client(monkeypatch):
    main.app.dependency_overrides[main.get_current_user] = lambda: "test-teacher"
    monkeypatch.setattr(main, "_jobs", {})
    value = TestClient(main.app, raise_server_exceptions=True)
    yield value
    value.close()
    main.app.dependency_overrides.pop(main.get_current_user, None)


def prepare_job(monkeypatch, *, real_compiler=False):
    def forbid_ai(*args, **kwargs):
        pytest.fail("PDF repair/delivery regression must not call a paid model")
    monkeypatch.setattr("app.pipeline.agents.latex_fixer.LLMInterface", forbid_ai)
    if not real_compiler:
        def compile_document(self, doc):
            if doc.count("{") != doc.count("}"):
                return LatexCompilationResult(errors=["Missing } inserted"])
            return LatexCompilationResult(success=True, pdf_bytes=b"%PDF-1.4\nfixture")
        monkeypatch.setattr(LatexChecker, "check", compile_document)
    state = PipelineState(
        owner_id="test-teacher", request=GenerationRequest(grade="VG1 1T", topic="Funksjoner"),
        raw_latex_body=BODY, edited_latex_body=BODY,
        math_verification=MathChecker().verify(BODY),
    )
    assert state.math_verification.claims_incorrect == 0
    assert state.math_verification.claims_unparseable == 0
    run_latex_validator(state)
    assert not state.latex_compilation.success
    run_latex_fixer(state)
    assert not state.steps[-1].error
    run_latex_validator(state)
    assert state.latex_compilation.success
    state = finalize(state)
    assert state.status in (PipelineStatus.COMPLETED, PipelineStatus.COMPLETED_WITH_WARNINGS)
    assert state.source_approved
    assert not state.used_latex_fallback
    persist_terminal_job(state)
    restored = load_job_from_disk(state.job_id)
    assert restored is not None
    assert restored.release_manifest == state.release_manifest
    assert restored.pdf_path == state.pdf_path
    main._jobs[state.job_id] = restored
    return restored


def test_repaired_pdf_survives_restart_and_passes_the_actual_export_routes(client, monkeypatch):
    state = prepare_job(monkeypatch)
    url = f"/generate/{state.job_id}"
    assert client.get(url + "/status").json()["ready"] is True
    assert client.get(url + "/result").json()["pdf_available"] is True
    preview = client.get(url + "/pdf?preview=true")
    assert preview.status_code == 200, preview.text
    assert preview.content.startswith(b"%PDF-")
    assert client.get(url + "/pdf").status_code == 409
    assert client.post(url + "/approve").status_code == 200
    assert client.get(url + "/pdf").content == preview.content


@pytest.mark.parametrize("mutation", ["body", "document", "manifest", "file"])
def test_changed_or_unproven_results_remain_blocked(client, monkeypatch, mutation):
    state = prepare_job(monkeypatch)
    if mutation == "body":
        state.verification_content += " 2 + 3 = 9"
    elif mutation == "document":
        state.full_document += "changed"
    elif mutation == "manifest":
        state.release_manifest = {}
    else:
        from pathlib import Path
        Path(state.pdf_path).write_bytes(b"changed PDF")
    response = client.get(f"/generate/{state.job_id}/pdf?preview=true")
    assert response.status_code == 409


def test_real_pdflatex_repair_produces_a_downloadable_pdf(client, monkeypatch):
    if not shutil.which("pdflatex"):
        if os.getenv("CI"):
            pytest.fail("CI must install the production mathematics PDF compiler")
        pytest.skip("pdflatex is exercised by the required CI job")
    monkeypatch.setenv("LATEX_ENGINE", "pdflatex")
    from app.config import get_settings
    get_settings.cache_clear()
    state = prepare_job(monkeypatch, real_compiler=True)
    pdf = client.get(f"/generate/{state.job_id}/pdf?preview=true")
    assert pdf.status_code == 200, pdf.text
    from io import BytesIO
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(pdf.content))
    assert len(reader.pages) > 0
    assert "Funksjoner" in reader.pages[0].extract_text()
    if os.getenv("TEST_DATA_DIR"):
        from pathlib import Path
        (Path(os.environ["TEST_DATA_DIR"]) / "math-repair-verified.pdf").write_bytes(pdf.content)


@pytest.mark.parametrize("environment", ["tikzpicture", "examplebox", "center"])
def test_tabular_context_is_preserved_in_long_figures_and_boxes(environment):
    from app.pipeline.agents.table_validator import _wrap_tabular_in_center
    body = (rf"\begin{{{environment}}}" + "\n" + "% padding\n" * 100
            + r"\node {\begin{tabular}{cc}x & f(x) \\ 1 & 4\end{tabular}};"
            + rf"\end{{{environment}}}")
    fixed, count = _wrap_tabular_in_center(body)
    assert fixed == body
    assert count == 0


def test_plain_tabular_is_still_centered():
    from app.pipeline.agents.table_validator import _wrap_tabular_in_center
    fixed, count = _wrap_tabular_in_center(r"\begin{tabular}{cc}1 & 4\end{tabular}")
    assert fixed.startswith(r"\begin{center}")
    assert count == 1
