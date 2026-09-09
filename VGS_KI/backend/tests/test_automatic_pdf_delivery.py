"""Offline recovery -> job completion -> real PDF -> existing download gate."""
import asyncio
import json
import shutil
import time
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from VGS_KI.backend import main
from VGS_KI.backend.laeringsark_renderer import coerce_structured_lesson
from VGS_KI.backend.job_manager import get_job, pop_job, register_job, run_job_in_thread
from Skoleverksted.backend.platform import compendium
from Skoleverksted.backend.platform.models import TruthSource
from Skoleverksted.backend.platform.quality_gate import run_quality_pipeline
from Skoleverksted.backend.platform.quality_runtime import QualityLayerTimeout


@pytest.mark.skipif(shutil.which("typst") is None, reason="typst CLI not installed")
@pytest.mark.parametrize("available_on_retry", [True, False])
@pytest.mark.parametrize("failure_mode", ["timeout", "missing_grounding_metadata"])
def test_automatic_recovery_reaches_pdf_or_safe_terminal_failure(monkeypatch, available_on_retry, failure_mode):
    text = "Unionen mellom Norge og Sverige ble oppløst i 1905."
    structured = coerce_structured_lesson({"tittel": "Historie", "ingress": "Undersøk historiske kilder.", "seksjoner": [
        {"overskrift": "Unionsoppløsningen", "avsnitt": [text], "begreper": [], "kjeder": []},
    ]})
    content = json.dumps({"canonical": structured, "worksheet": "FORSTÅELSE OG ANALYSE\n1. Når ble unionen oppløst?"}, ensure_ascii=False)
    calls = []

    def provider(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1 or not available_on_retry:
            raise QualityLayerTimeout("temporary provider timeout")
        url = "https://www.stortinget.no/no/Stortinget-og-demokratiet/Historikk/1905/"
        return {
            "summary": "Kontrollen er bestått.",
            "coverage": {"complete": True, "covered_node_paths": ["$"]},
            "claims": [{"claim": text, "exact_text": text, "status": "verified", "action": "keep",
                        "content_type": "fact", "source_urls": [url], "evidence": text,
                        "field_path": "$.canonical.seksjoner[0].avsnitt[0]", "confidence": 0.99}],
        }, [TruthSource(title="Stortinget", url=url, origin="grounding", fetch_status="fetched",
                        snapshot_id="snapshot", snapshot_hash="a" * 64, excerpt=text)]

    def writer(**kwargs):
        result = run_quality_pipeline(
            generator_id="fag.learning_sheet", content=content,
            topic=kwargs["topic"], subject=kwargs["subject"], level=kwargs["level"],
            cancel_check=kwargs["cancel_check"],
        )
        return {
            "text": text, "structured": structured, "worksheet": json.loads(content)["worksheet"],
            "quality_status": result.quality_status, "verification_content": result.approved_content,
            "truth_passport": result.passport.model_dump(), "release_manifest": result.release_manifest.model_dump(),
            "quality_stop_reason": result.stop_reason, "quality_rounds": [], "quarantine": [],
        }

    if failure_mode == "timeout":
        monkeypatch.setattr(compendium, "_call_google_json", provider)
    else:
        from Skoleverksted.backend.tests.test_source_research import install_research_provider
        calls, _ = install_research_provider(
            monkeypatch, fact=text, content=content, field_path="$.canonical.seksjoner[0].avsnitt[0]",
            available_on_retry=available_on_retry,
        )
    monkeypatch.setattr(main, "generate_lesson_content", writer)
    monkeypatch.setattr(main, "_resolve_source", lambda *args: (None, None, None))
    client = TestClient(main.app)

    async def scenario():
        job_id, queue = register_job()
        try:
            request = main.LessonRequest(topic="Unionsoppløsningen", subject="Historie", level="VG2", image_mode="none", use_ndla=False)
            run_job_in_thread(job_id, queue, request, main._lesson_worker)
            deadline = time.monotonic() + 25
            while not get_job(job_id).done and time.monotonic() < deadline:
                await asyncio.sleep(0.02)
            job = get_job(job_id)
            assert job.done
            assert len(calls) == (2 if failure_mode == "timeout" else 4)
            if not available_on_retry:
                assert job.status == "needs_teacher_review"
                assert job.pdf is None
                assert client.get(f"/generate-lesson-download/{job_id}?preview=true").status_code == 409
                assert client.post(f"/generation/{job_id}/approve").status_code == 409
                return
            assert job.status == "source_approved"
            preview = client.get(f"/generate-lesson-download/{job_id}?preview=true")
            assert preview.status_code == 200
            assert "filename*=UTF-8''" in preview.headers["content-disposition"]
            assert "%C3%B8" in preview.headers["content-disposition"]
            pages = PdfReader(BytesIO(preview.content)).pages
            pdf_text = "\n".join(page.extract_text() for page in pages)
            assert "1905" in pdf_text
            assert "Automatisk kontrollert av AI-crewet" in pdf_text
            assert "modellens kunnskap" not in pdf_text
            # Mirrors the existing Last ned PDF click, without editing or
            # asking the user to perform a fact check.
            assert client.get(f"/generate-lesson-download/{job_id}").status_code == 409
            assert client.post(f"/generation/{job_id}/approve").status_code == 200
            download = client.get(f"/generate-lesson-download/{job_id}")
            assert download.status_code == 200
            assert download.content == preview.content
            assert download.headers["x-quality-status"] == "export_ready"
        finally:
            pop_job(job_id)

    asyncio.run(scenario())
