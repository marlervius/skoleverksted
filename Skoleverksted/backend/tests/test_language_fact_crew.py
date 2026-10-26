"""Run all three language agents, retrieval and the repair/export gates offline."""
import json
import threading
from types import SimpleNamespace

import pytest
from google import genai

from Skoleverksted.backend.platform import compendium
from Skoleverksted.backend.platform.models import TruthSource
from Skoleverksted.backend.platform.quality_gate import (
    content_digest, require_export_ready, run_quality_pipeline,
)
from Skoleverksted.backend.platform.quality_runtime import QualityLayerCancelled


URL = "https://example.org/synthetic-council"
WRONG = "Det syntetiske rådet har 99 medlemmer."
RIGHT = "Det syntetiske rådet har 3 medlemmer."
CONTENT = json.dumps({"text": WRONG + " Les teksten og snakk sammen om rådet.",
                      "worksheet": "Skriv en setning med ordet råd."}, ensure_ascii=False)
PATHS = ["$.text", "$.worksheet"]


def install_agents(monkeypatch, *, missing_snapshot=False, omission=False, disagreement=False,
                   incomplete=False, mapper_error=False, cancelled=None):
    calls = []
    snapshots = []

    def fetch(candidates, **kwargs):
        snapshots.append(list(candidates))
        return [TruthSource(
            url=URL, title="Syntetisk testkilde", origin="grounding",
            fetch_status="timeout" if missing_snapshot else "fetched",
            snapshot_id="" if missing_snapshot else "synthetic-snapshot",
            snapshot_hash="" if missing_snapshot else "a" * 64,
            excerpt="" if missing_snapshot else RIGHT,
        )]

    class Client:
        def __init__(self, **kwargs):
            self.models = self

        def close(self):
            pass

        def generate_content(self, *, contents, config, **kwargs):
            if "FAKTAKARTLEGGER" in contents:
                calls.append("mapper")
                assert not config.tools
                if mapper_error:
                    raise RuntimeError("synthetic mapper failure")
                # Prompt contains one canonical candidate and no model verdicts.
                data = json.loads(contents.split("Returner bare JSON.\n", 1)[1])
                text = data["document_nodes"][0]["text"]
                fact = RIGHT if RIGHT in text else WRONG
                payload = {
                    "coverage": {"complete": not incomplete, "covered_node_paths": PATHS},
                    "claims": [{"claim": fact, "exact_text": fact, "field_path": "$.text",
                                "content_type": "external_factual_claim"}],
                }
                if cancelled:
                    cancelled.set()
            elif config.tools:
                calls.append("researcher")
                assert "KILDEGRANSKEREN" in contents
                assert "claim_inventory" in contents
                assert config.response_mime_type is None
                return SimpleNamespace(text="Syntetisk researchnotat.", candidates=[SimpleNamespace(
                    grounding_metadata=SimpleNamespace(grounding_chunks=[
                        SimpleNamespace(web=SimpleNamespace(uri=URL, title="Syntetisk testkilde")),
                    ]),
                )])
            else:
                calls.append("corrector")
                assert "KORREKTØREN" in contents
                assert "<KILDEUTDRAG>" in contents
                candidate = contents.split("<TEKST>", 1)[1].split("</TEKST>", 1)[0]
                fixed = RIGHT in json.loads(candidate)["text"]
                fact = RIGHT if fixed else WRONG
                payload = {
                    "summary": "Syntetisk kontrollrapport.",
                    "coverage": {"complete": True, "covered_node_paths": PATHS},
                    "claims": [] if omission else [{
                        "claim": fact, "exact_text": fact, "field_path": "$.text",
                        "content_type": "fictional_language_example" if disagreement else "external_factual_claim",
                        "status": "verified" if fixed or missing_snapshot else "unsupported",
                        "action": "keep" if fixed or missing_snapshot else "qualify",
                        "replacement": "" if fixed or missing_snapshot else RIGHT,
                        "source_urls": [URL], "evidence": RIGHT, "confidence": 0.99,
                    }],
                }
            return SimpleNamespace(text=json.dumps(payload), candidates=[])

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-not-used")
    monkeypatch.setattr(genai, "Client", Client)
    monkeypatch.setattr(compendium, "collect_source_snapshots", fetch)
    return calls, snapshots


def run(**kwargs):
    return run_quality_pipeline(generator_id="norsk.preview_pdf", content=CONTENT,
                                topic="Syntetisk råd", subject="Norsk", level="Pre-A1", **kwargs)


def test_three_roles_correct_then_independently_recheck_the_exact_candidate(monkeypatch):
    calls, snapshots = install_agents(monkeypatch)
    events = []
    result = run(progress_callback=events.append)
    assert calls == ["mapper", "researcher", "corrector"] * 2
    assert len(snapshots) == 2
    assert result.source_approved
    assert RIGHT in json.loads(result.approved_content)["text"]
    assert WRONG not in result.approved_content
    assert json.loads(result.approved_content)["worksheet"] == json.loads(CONTENT)["worksheet"]
    assert result.rounds[0].corrected_count == 1
    assert result.release_manifest.document_hash == content_digest(result.approved_content)
    assert result.release_manifest.evidence_snapshot_ids == ["synthetic-snapshot"]
    for agent in (1, 2, 3):
        assert any(f"Agent {agent} av 3" in event["message"] for event in events)
    args = dict(export_id="norsk.pdf", content=result.approved_content,
                verification_status=result.passport.status,
                verified_revision=result.passport.content_revision,
                verification_version=result.passport.version,
                approved_revision=content_digest(result.approved_content),
                release_manifest=result.release_manifest.model_dump())
    with pytest.raises(PermissionError):
        require_export_ready(teacher_approved=False, **args)
    require_export_ready(teacher_approved=True, **args)


@pytest.mark.parametrize("failure", ["omission", "disagreement", "incomplete"])
def test_an_independent_obligation_cannot_be_dropped_or_reclassified(monkeypatch, failure):
    calls, _ = install_agents(monkeypatch, **{failure: True})
    result = run()
    assert calls == ["mapper", "researcher", "corrector"] * 2
    assert not result.source_approved
    assert result.stop_reason == "incomplete_claim_register"
    assert json.loads(result.approved_content) == json.loads(CONTENT)
    assert not result.quarantine
    assert result.passport.limitations


def test_three_agreeing_agents_without_fetched_evidence_cannot_approve(monkeypatch):
    calls, _ = install_agents(monkeypatch, missing_snapshot=True)
    result = run()
    assert calls == ["mapper", "researcher", "corrector"] * 2
    assert not result.source_approved
    assert result.stop_reason == "automatic_source_recovery_exhausted"
    assert json.loads(result.approved_content) == json.loads(CONTENT)
    with pytest.raises(PermissionError):
        require_export_ready(
            export_id="norsk.pdf", content=result.approved_content,
            verification_status=result.passport.status,
            verified_revision=result.passport.content_revision,
            verification_version=result.passport.version,
            teacher_approved=True, approved_revision=content_digest(result.approved_content),
            release_manifest=result.release_manifest.model_dump(),
        )


def test_mapper_failure_terminates_without_running_later_agents(monkeypatch):
    calls, _ = install_agents(monkeypatch, mapper_error=True)
    result = run()
    assert calls == ["mapper"] * 4  # Two bounded SDK attempts per pipeline attempt.
    assert not result.source_approved
    assert result.stop_reason == "incomplete_claim_register"


def test_cancellation_after_mapper_does_not_start_research_or_publish(monkeypatch):
    stopped = threading.Event()
    calls, _ = install_agents(monkeypatch, cancelled=stopped)
    with pytest.raises(QualityLayerCancelled):
        run(cancel_check=stopped.is_set)
    assert calls == ["mapper"]


def test_a_repaired_candidate_needs_another_complete_round(monkeypatch):
    calls, _ = install_agents(monkeypatch)
    result = run(max_rounds=1)
    assert calls == ["mapper", "researcher", "corrector"]
    assert not result.source_approved
    assert result.stop_reason == "repair_requires_delta_verification"


def test_other_modules_keep_the_existing_audit_flow(monkeypatch):
    from Skoleverksted.backend.platform import fact_crew
    def unexpected_mapper(**kwargs):
        raise AssertionError("Language agents must not replace another module's contract")
    monkeypatch.setattr(fact_crew, "map_claims", unexpected_mapper)
    calls = []
    def assessor(prompt, **kwargs):
        calls.append(kwargs)
        return {"coverage": {"complete": True, "covered_node_paths": ["$"]},
                "claims": [], "summary": "Syntetisk oppgave uten eksterne fakta."}, []
    monkeypatch.setattr(compendium, "_call_google_json", assessor)
    result = run_quality_pipeline(
        generator_id="fag.learning_sheet", content=CONTENT,
        topic="Syntetisk", subject="Historie", level="VG2",
    )
    assert len(calls) == 1
    assert "claim_inventory" not in calls[0]["research_prompt"]
