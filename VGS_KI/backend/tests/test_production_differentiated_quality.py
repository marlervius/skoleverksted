"""Regression tests for the Norsklæring differentiated production path."""

import asyncio
import time

from Skoleverksted.backend.platform.models import TruthClaim, TruthPassport
from Skoleverksted.backend.platform.quality_gate import (
    claim_is_resolved,
    claim_requires_evidence,
    run_quality_pipeline,
)
from Skoleverksted.backend.platform.truth import TruthAudit
from VGS_KI.backend.job_manager import get_job, register_job, run_job_in_thread


def _passport(claims):
    return TruthPassport(
        status="not_evaluated",
        topic="Norsk",
        subject="Norsklæring",
        claims=claims,
        total_claims=len(claims),
        verified_claims=sum(item.status == "verified" for item in claims),
    )


def test_language_examples_and_instructions_do_not_require_external_sources():
    examples = [
        TruthClaim(
            claim="Ali kjøper to epler på butikken.",
            exact_text="Ali kjøper to epler på butikken.",
            status="not_evaluated",
            content_type="fictional_language_example",
        ),
        TruthClaim(
            claim="Sett verbet i preteritum.",
            exact_text="Sett verbet i preteritum.",
            status="not_evaluated",
            content_type="instruction",
        ),
        TruthClaim(
            claim="Hva synes du om dialogen?",
            exact_text="Hva synes du om dialogen?",
            status="not_evaluated",
            content_type="reflection_question",
        ),
    ]

    assert all(not claim_requires_evidence(item) for item in examples)
    assert all(claim_is_resolved(item) for item in examples)


def test_external_claims_still_require_a_concrete_source():
    claim = TruthClaim(
        claim="Norge fikk sin grunnlov i 1814.",
        exact_text="Norge fikk sin grunnlov i 1814.",
        status="unsupported",
        content_type="external_factual_claim",
    )

    assert claim_requires_evidence(claim)
    assert not claim_is_resolved(claim)


def test_source_free_language_material_can_be_source_approved():
    content = "Instruksjon og et fiktivt språkeksempel som er langt nok til kontroll."

    def deterministic_audit(**kwargs):
        return TruthAudit(content=kwargs["content"], passport=_passport([]))

    result = run_quality_pipeline(
        generator_id="norsk.multi_level",
        content=content,
        topic="Hverdagsdialog",
        subject="Norsklæring",
        level="A2",
        audit=deterministic_audit,
    )

    assert result.source_approved
    assert result.passport.status == "verified"


def test_unknown_quality_status_fails_closed_and_never_exposes_pdf():
    async def scenario():
        job_id, _queue = register_job()

        def worker(ctx):
            ctx.set_meta("quality_status", "unexpected_status")
            return b"must-not-be-served", "blocked.pdf"

        run_job_in_thread(job_id, _queue, object(), worker)
        deadline = time.time() + 5
        while time.time() < deadline:
            job = get_job(job_id)
            if job and job.done:
                return job
            await asyncio.sleep(0.01)
        raise AssertionError("job did not reach a terminal state")

    job = asyncio.run(scenario())
    assert job.status == "needs_teacher_review"
    assert job.pdf is None
