"""Durable compendium repair: registration, execution, recovery and evidence.

Every test here asks the same question in a different way: can a teacher's
repair be lost, silently succeed, overwrite newer work, or leave the chapter
locked? The answer has to stay "no" for all of them.
"""

from __future__ import annotations

import threading
import time

import pytest
from fastapi import HTTPException

from Skoleverksted.backend.platform import queue as queue_module
from Skoleverksted.backend.platform import repair as repair_module
from Skoleverksted.backend.platform import router as router_module
from Skoleverksted.backend.platform import store as store_module
from Skoleverksted.backend.platform.compendium import plan_compendium
from Skoleverksted.backend.platform.models import (
    CompendiumChapter,
    CompendiumPlanRequest,
    CompendiumSource,
    TruthPassport,
)
from Skoleverksted.backend.platform.repair import RepairConflictError, RepairService
from Skoleverksted.backend.platform.store import PlatformStore
from Skoleverksted.backend.platform.truth import TruthAudit


REPAIRED_TEXT = "## Aktører\n\n" + ("Rettet og dokumentert setning om perioden. " * 30)
ORIGINAL_TEXT = "## Aktører\n\n" + ("Uklar påstand om perioden uten dekning. " * 30)


class _Harness:
    """Temp store, a repair service with a controllable worker, no real model."""

    def __init__(self, tmp_path) -> None:
        self.store = PlatformStore(tmp_path / "platform.sqlite3")
        self.pending: list = []
        self.service = RepairService(store=self.store, spawn=self.pending.append, gate=_PassThroughGate())
        self.compendium = self.store.create_compendium(
            plan_compendium(CompendiumPlanRequest(
                topic="Alle kongedømmer i Europa omkring 1450",
                subject="Historie",
                level="VG2",
                kind="reference",
                chapter_count=3,
                use_ai=False,
            ))
        )
        self.chapter = self._seed_chapter()

    def _seed_chapter(self) -> CompendiumChapter:
        chapter = self.compendium.chapters[0]
        payload = chapter.model_dump()
        payload.update(
            content_markdown=ORIGINAL_TEXT,
            status="needs_revision",
            verification_notes=["Årstallet mangler dekning i kildene."],
            sources=[CompendiumSource(
                title="Svak kilde",
                url="https://no.wikipedia.org/wiki/Europa",
                publisher="Wikipedia",
            )],
        )
        updated = self.store.replace_compendium_chapter(
            self.compendium.id,
            CompendiumChapter.model_validate(payload),
        )
        assert updated is not None
        self.compendium = updated
        return updated.chapters[0]

    def reload_compendium(self):
        self.compendium = self.store.get_compendium(self.compendium.id)
        return self.compendium

    def stored_chapter(self) -> CompendiumChapter:
        return self.store.compendium_chapter(self.compendium.id, self.chapter.id)

    def submit(self, operation_id: str = "op-1"):
        return self.service.submit(self.reload_compendium(), self.chapter.id, operation_id=operation_id)

    def run_pending(self) -> None:
        while self.pending:
            self.pending.pop(0)()

    def stages(self, job_id: str) -> list[str]:
        return [entry.stage for entry in self.store.list_repair_events(job_id)]


class _PassThroughGate:
    """The capacity gate is exercised in test_queue; here it must not block."""

    class _Claim:
        def __enter__(self):
            return None

        def __exit__(self, *_exc):
            return False

    def claim(self, _job_id: str, **_kwargs):
        return self._Claim()


@pytest.fixture
def harness(tmp_path):
    return _Harness(tmp_path)


def _model(*, repair=None, verification=None, fail=None):
    """Fake the two grounded model calls the repair pipeline makes."""

    def call(_prompt, *, grounded=False, response_schema=None):
        is_verification = bool((response_schema or {}).get("properties", {}).get("approved"))
        if is_verification:
            return (verification or {"approved": True, "notes": [], "unsafe_claims": []}), []
        if fail is not None:
            raise fail
        return (repair or {
            "content_markdown": REPAIRED_TEXT,
            "changes": ["Årstallet er dokumentert med en konkret kilde."],
            "key_facts": ["En dokumentert påstand"],
            "glossary": ["Begrep – forklaring"],
            "sources": [{
                "title": "Kongedømmer i Europa",
                "url": "https://snl.no/kongedomme",
                "publisher": "Store norske leksikon",
            }],
        }), []

    return call


def _verified_audit(**kwargs):
    return TruthAudit(
        content=kwargs["content"],
        passport=TruthPassport(
            status="verified",
            topic="Testtema",
            subject="Historie",
            coverage_percent=100,
            verified_claims=4,
            total_claims=4,
            summary="Kontrollen er grønn.",
        ),
    )


def _install(monkeypatch, call, audit=_verified_audit):
    monkeypatch.setattr("Skoleverksted.backend.platform.compendium._call_google_json", call)
    monkeypatch.setattr("Skoleverksted.backend.platform.compendium.audit_truth", audit)


def _use_harness_globally(monkeypatch, harness):
    """Point the module singletons at the harness so endpoints are testable."""
    monkeypatch.setattr(store_module, "_store", harness.store)
    monkeypatch.setattr(repair_module, "_service", harness.service)
    monkeypatch.setattr(queue_module, "_queue", None)


class _Request:
    def __init__(self, headers=None):
        self.headers = headers or {}


# --------------------------------------------------------------------------
# 1-3: the request registers work, it does not perform it
# --------------------------------------------------------------------------


def test_repair_is_registered_durably_before_any_work(harness, monkeypatch):
    calls: list[str] = []
    _install(monkeypatch, lambda *a, **k: calls.append("model") or ({}, []))

    job = harness.submit()

    assert job.status == "queued"
    assert harness.store.get_repair_job(job.id).status == "queued"
    assert harness.stages(job.id) == ["registered"]
    assert calls == []


def test_repair_endpoint_returns_202_with_a_durable_job_identity(harness, monkeypatch):
    _install(monkeypatch, _model())
    _use_harness_globally(monkeypatch, harness)

    accepted = router_module.repair_compendium_chapter_endpoint(
        harness.compendium.id,
        harness.chapter.id,
        _Request({"x-operation-id": "op-202"}),
    )

    assert accepted.status == "queued"
    assert accepted.operation_id == "op-202"
    assert accepted.status_url == f"/api/platform/repair-jobs/{accepted.job_id}"
    route = next(
        item for item in router_module.router.routes
        if getattr(item, "name", "") == "repair_compendium_chapter_endpoint"
    )
    assert route.status_code == 202
    # The chapter is untouched: the response was sent before any model work.
    assert harness.stored_chapter().content_markdown == ORIGINAL_TEXT


def test_model_call_never_runs_in_the_request_thread(tmp_path, monkeypatch):
    harness = _Harness(tmp_path)
    harness.service = RepairService(store=harness.store, gate=_PassThroughGate())
    seen: dict[str, int] = {}
    done = threading.Event()

    def call(prompt, **kwargs):
        seen["worker"] = threading.get_ident()
        done.set()
        return _model()(prompt, **kwargs)

    _install(monkeypatch, call)
    job = harness.service.submit(harness.compendium, harness.chapter.id, operation_id="op-thread")

    assert done.wait(10)
    for _ in range(100):
        if harness.store.get_repair_job(job.id).status != "running":
            break
        time.sleep(0.05)
    assert seen["worker"] != threading.get_ident()
    assert harness.store.get_repair_job(job.id).status == "succeeded"


# --------------------------------------------------------------------------
# 4, 8, 24: success requires a real write-back
# --------------------------------------------------------------------------


def test_successful_repair_writes_the_chapter_and_records_success(harness, monkeypatch):
    _install(monkeypatch, _model())

    job = harness.submit()
    harness.run_pending()

    finished = harness.store.get_repair_job(job.id)
    assert finished.status == "succeeded"
    assert finished.chapter_status == "generated"
    assert finished.result_token and finished.result_token != finished.chapter_token
    assert harness.stored_chapter().content_markdown == REPAIRED_TEXT.strip()
    assert harness.stored_chapter().previous_content_markdown == ORIGINAL_TEXT
    assert "write_back" in harness.stages(job.id)
    assert "succeeded" in harness.stages(job.id)


def test_truth_failure_is_a_content_result_not_an_infrastructure_failure(harness, monkeypatch):
    def unverified(**kwargs):
        return TruthAudit(
            content=kwargs["content"],
            passport=TruthPassport(
                status="source_unavailable",
                topic="Testtema",
                subject="Historie",
                coverage_percent=40,
                verified_claims=2,
                total_claims=5,
                summary="Kildene svarte ikke.",
            ),
        )

    _install(monkeypatch, _model(), audit=unverified)

    job = harness.submit()
    harness.run_pending()

    finished = harness.store.get_repair_job(job.id)
    assert finished.status == "succeeded"
    assert finished.chapter_status == "source_grounding_failed"
    audit = next(entry for entry in harness.store.list_repair_events(job.id) if entry.stage == "truth_audit")
    assert audit.payload["truth_status"] == "source_unavailable"
    assert audit.payload["coverage_percent"] == 40


# --------------------------------------------------------------------------
# 5-7, 9, 10, 21, 24: failures stay retryable and never claim success
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("modellen svarte ikke innen tidsgrensen"),
        RuntimeError("leverandøren returnerte 503"),
        ValueError("modellsvaret kunne ikke tolkes som JSON"),
    ],
    ids=["timeout", "provider", "parse"],
)
def test_model_failure_is_retryable_and_preserves_the_text(harness, monkeypatch, error):
    _install(monkeypatch, _model(fail=error))

    job = harness.submit()
    harness.run_pending()

    finished = harness.store.get_repair_job(job.id)
    assert finished.status == "failed_retryable"
    assert harness.stored_chapter().content_markdown == ORIGINAL_TEXT
    failure = next(entry for entry in harness.store.list_repair_events(job.id) if entry.stage == "model_failed")
    assert failure.payload["error_type"] == type(error).__name__
    assert failure.payload["content_written"] is False
    assert "succeeded" not in harness.stages(job.id)
    # The chapter lock is free again.
    assert harness.store.active_repair_job(harness.compendium.id, harness.chapter.id) is None


def test_database_write_failure_is_retryable_and_leaves_no_lock(harness, monkeypatch):
    _install(monkeypatch, _model())

    def broken(*_args, **_kwargs):
        raise OSError("disken er full")

    monkeypatch.setattr(harness.store, "replace_compendium_chapter_if_unchanged", broken)

    job = harness.submit()
    harness.run_pending()

    finished = harness.store.get_repair_job(job.id)
    assert finished.status == "failed_retryable"
    assert finished.chapter_status is None
    assert harness.stored_chapter().content_markdown == ORIGINAL_TEXT
    assert harness.store.active_repair_job(harness.compendium.id, harness.chapter.id) is None


def test_worker_crash_never_produces_a_false_success(harness, monkeypatch):
    def crashes(*_args, **_kwargs):
        raise MemoryError("arbeideren stoppet")

    monkeypatch.setattr(repair_module, "repair_compendium_chapter", crashes)

    job = harness.submit()
    harness.run_pending()

    finished = harness.store.get_repair_job(job.id)
    assert finished.status == "failed_retryable"
    assert "failed" in harness.stages(job.id)
    assert "write_back" not in harness.stages(job.id)
    assert harness.stored_chapter().content_markdown == ORIGINAL_TEXT


# --------------------------------------------------------------------------
# 11-13, 22: restart and lease recovery
# --------------------------------------------------------------------------


def test_restart_before_claim_releases_the_chapter(harness, monkeypatch):
    _install(monkeypatch, _model())
    job = harness.submit()
    harness.pending.clear()

    assert harness.store.recover_incomplete_repair_jobs() == 1

    recovered = harness.store.get_repair_job(job.id)
    assert recovered.status == "failed_retryable"
    assert "startet på nytt" in recovered.message
    assert harness.store.active_repair_job(harness.compendium.id, harness.chapter.id) is None
    # A restarted process can start a fresh repair immediately.
    assert harness.submit("op-after-restart").status == "queued"


def test_restart_during_the_model_call_is_retryable_not_successful(harness, monkeypatch):
    _install(monkeypatch, _model())
    job = harness.submit()
    harness.pending.clear()
    assert harness.store.claim_repair_job(job.id) is not None

    # A new process boots: RepairService.__init__ recovers what it inherited.
    RepairService(store=harness.store, spawn=harness.pending.append, gate=_PassThroughGate())

    recovered = harness.store.get_repair_job(job.id)
    assert recovered.status == "failed_retryable"
    assert recovered.lease_expires_at == ""
    assert harness.stored_chapter().content_markdown == ORIGINAL_TEXT


def test_stale_lease_is_reclaimed_so_the_chapter_never_stays_locked(harness, monkeypatch):
    _install(monkeypatch, _model())
    job = harness.submit()
    harness.pending.clear()
    harness.store.claim_repair_job(job.id, lease_seconds=30)
    stale = harness.store.get_repair_job(job.id)
    stale.lease_expires_at = "2000-01-01T00:00:00+00:00"
    with harness.store._exclusive() as conn:  # noqa: SLF001 - direct ledger surgery
        harness.store._save_repair_job(conn, stale)  # noqa: SLF001

    assert harness.store.expire_stale_repair_leases() == 1
    assert harness.store.get_repair_job(job.id).status == "failed_retryable"
    assert harness.store.active_repair_job(harness.compendium.id, harness.chapter.id) is None


def test_job_status_survives_a_backend_restart(tmp_path, monkeypatch):
    harness = _Harness(tmp_path)
    _install(monkeypatch, _model())
    job = harness.submit()
    harness.run_pending()

    reopened = PlatformStore(tmp_path / "platform.sqlite3")
    persisted = reopened.get_repair_job(job.id)
    assert persisted is not None
    assert persisted.status == "succeeded"
    assert persisted.operation_id == "op-1"
    assert [entry.stage for entry in reopened.list_repair_events(job.id)]


# --------------------------------------------------------------------------
# 14-16: identity, idempotence and conflicts
# --------------------------------------------------------------------------


def test_retrying_the_same_operation_returns_the_same_job(harness, monkeypatch):
    _install(monkeypatch, _model())

    first = harness.submit("op-same")
    second = harness.submit("op-same")

    assert second.id == first.id
    assert len(harness.pending) == 1


def test_parallel_repair_of_the_same_chapter_conflicts(harness, monkeypatch):
    _install(monkeypatch, _model())
    first = harness.submit("op-first")

    with pytest.raises(RepairConflictError) as error:
        harness.submit("op-second")

    assert error.value.job.id == first.id


def test_new_repair_after_a_terminal_failure_gets_a_new_identity(harness, monkeypatch):
    _install(monkeypatch, _model(fail=RuntimeError("leverandørfeil")))
    first = harness.submit("op-first")
    harness.run_pending()
    assert harness.store.get_repair_job(first.id).status == "failed_retryable"

    _install(monkeypatch, _model())
    second = harness.submit("op-second")
    harness.run_pending()

    assert second.id != first.id
    assert second.operation_id != first.operation_id
    assert second.attempt == first.attempt + 1
    assert harness.store.get_repair_job(second.id).status == "succeeded"


# --------------------------------------------------------------------------
# 17, 18: compare-and-swap protects newer teacher work
# --------------------------------------------------------------------------


def test_teacher_edit_during_repair_supersedes_the_result(harness, monkeypatch):
    teacher_text = "## Aktører\n\n" + ("Lærerens egen nyere formulering av perioden. " * 14)

    def call_then_teacher_edits(prompt, **kwargs):
        result = _model()(prompt, **kwargs)
        current = harness.stored_chapter()
        if current.content_markdown != teacher_text:
            payload = current.model_dump()
            payload["content_markdown"] = teacher_text
            harness.store.replace_compendium_chapter(
                harness.compendium.id,
                CompendiumChapter.model_validate(payload),
            )
        return result

    _install(monkeypatch, call_then_teacher_edits)

    job = harness.submit()
    harness.run_pending()

    finished = harness.store.get_repair_job(job.id)
    assert finished.status == "superseded"
    assert harness.stored_chapter().content_markdown == teacher_text
    superseded = next(entry for entry in harness.store.list_repair_events(job.id) if entry.stage == "superseded")
    assert superseded.payload["content_written"] is False
    assert superseded.payload["expected_token"] != superseded.payload["actual_token"]


def test_a_stale_worker_cannot_overwrite_newer_text(harness, monkeypatch):
    _install(monkeypatch, _model())
    job = harness.submit()
    harness.pending.clear()
    harness.store.claim_repair_job(job.id)

    newer = "## Aktører\n\n" + ("Nyere tekst skrevet etter at jobben startet. " * 14)
    payload = harness.stored_chapter().model_dump()
    payload["content_markdown"] = newer
    harness.store.replace_compendium_chapter(
        harness.compendium.id,
        CompendiumChapter.model_validate(payload),
    )

    late = harness.stored_chapter().model_copy(update={"content_markdown": REPAIRED_TEXT})
    with pytest.raises(store_module.StaleChapterWriteError):
        harness.store.replace_compendium_chapter_if_unchanged(
            harness.compendium.id,
            late,
            job.chapter_token,
        )
    assert harness.stored_chapter().content_markdown == newer


# --------------------------------------------------------------------------
# 19, 20: cancellation
# --------------------------------------------------------------------------


def test_cancel_before_start_stops_the_job_and_frees_the_chapter(harness, monkeypatch):
    _install(monkeypatch, _model())
    job = harness.submit()

    cancelled = harness.service.cancel(job.id)
    assert cancelled.status == "cancelled"
    assert harness.store.active_repair_job(harness.compendium.id, harness.chapter.id) is None

    harness.run_pending()
    assert harness.store.get_repair_job(job.id).status == "cancelled"
    assert harness.stored_chapter().content_markdown == ORIGINAL_TEXT
    assert "claimed" not in harness.stages(job.id)


def test_cancel_during_model_work_discards_the_late_result(harness, monkeypatch):
    holder: dict[str, str] = {}

    def call_then_cancel(prompt, **kwargs):
        harness.service.cancel(holder["job_id"])
        return _model()(prompt, **kwargs)

    _install(monkeypatch, call_then_cancel)
    job = harness.submit()
    holder["job_id"] = job.id
    harness.run_pending()

    finished = harness.store.get_repair_job(job.id)
    assert finished.status == "cancelled"
    assert finished.cancel_requested is True
    assert harness.stored_chapter().content_markdown == ORIGINAL_TEXT
    assert "write_back" not in harness.stages(job.id)


# --------------------------------------------------------------------------
# 23, 25, 26: reload, evidence and secret hygiene
# --------------------------------------------------------------------------


def test_a_reloaded_page_finds_the_job_again(harness, monkeypatch):
    _install(monkeypatch, _model())
    _use_harness_globally(monkeypatch, harness)
    job = harness.submit()

    found = router_module.latest_chapter_repair_job(harness.compendium.id, harness.chapter.id)
    assert found.id == job.id
    assert found.status == "queued"

    with pytest.raises(HTTPException) as missing:
        router_module.latest_chapter_repair_job(harness.compendium.id, harness.compendium.chapters[1].id)
    assert missing.value.status_code == 404


def test_the_ledger_reconstructs_the_repair(harness, monkeypatch):
    _install(monkeypatch, _model())
    job = harness.submit()
    harness.run_pending()

    entries = harness.store.list_repair_events(job.id)
    assert [entry.job_id for entry in entries] == [job.id] * len(entries)
    assert {entry.operation_id for entry in entries} == {job.operation_id}
    stages = [entry.stage for entry in entries]
    for stage in ("registered", "claimed", "model_request", "model_response", "truth_audit", "write_back", "succeeded"):
        assert stage in stages
    request = next(entry for entry in entries if entry.stage == "model_request")
    assert request.payload["model"]
    assert request.payload["prompt_version"] == "compendium-repair-v1"
    assert request.payload["prompt_chars"] > 0
    assert len(request.payload["prompt_hash"]) == 64
    response = next(entry for entry in entries if entry.stage == "model_response")
    assert response.payload["provider_returned"] is True
    assert response.payload["parsed"] is True
    assert response.payload["duration_ms"] >= 0
    write = next(entry for entry in entries if entry.stage == "write_back")
    assert write.payload["content_written"] is True
    assert write.payload["chapter_status"] == "generated"


def test_the_ledger_stores_no_secrets_and_no_prompt_text(harness):
    entry = harness.store.append_repair_event(
        "job-1",
        "op-1",
        "model_request",
        {
            "google_api_key": "AIzaSecretValue",
            "authorization": "Bearer hemmelig",
            "prompt": "x" * 5000,
            "prompt_hash": "a" * 64,
            "model": "gemini-3.5-flash",
        },
    )

    assert "google_api_key" not in entry.payload
    assert "authorization" not in entry.payload
    assert entry.payload["prompt_hash"] == "a" * 64
    assert len(entry.payload["prompt"]) == 400
    stored = harness.store.list_repair_events("job-1")[0]
    assert "AIzaSecretValue" not in str(stored.payload)
    assert "hemmelig" not in str(stored.payload)


def test_cancel_endpoint_routes_repair_jobs_through_the_repair_lifecycle(harness, monkeypatch):
    _install(monkeypatch, _model())
    _use_harness_globally(monkeypatch, harness)
    job = harness.submit()

    mirrored = router_module.cancel_job(job.id)

    assert mirrored.status == "cancelled"
    assert mirrored.kind == "compendium_repair"
    assert harness.store.get_repair_job(job.id).status == "cancelled"


def test_http_contract_is_asynchronous_durable_and_recoverable(harness, monkeypatch):
    """The teacher-visible contract, over real HTTP, with a real worker."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    release = threading.Event()

    def slow_call(prompt, **kwargs):
        assert release.wait(10)
        return _model()(prompt, **kwargs)

    _install(monkeypatch, slow_call)
    harness.service = RepairService(store=harness.store, gate=_PassThroughGate())
    _use_harness_globally(monkeypatch, harness)

    app = FastAPI()
    app.include_router(router_module.router, prefix="/api/platform")
    client = TestClient(app)
    path = f"/api/platform/compendia/{harness.compendium.id}/chapters/{harness.chapter.id}/repair"

    started = time.monotonic()
    response = client.post(path, headers={"x-operation-id": "op-http"})
    elapsed = time.monotonic() - started

    assert response.status_code == 202
    # The model call is still blocked, so the response cannot have waited for it.
    assert elapsed < 5
    body = response.json()
    job_id = body["job_id"]
    assert body["status"] == "queued"
    assert body["status_url"] == f"/api/platform/repair-jobs/{job_id}"

    # A retry with a new operation is refused while the chapter is reserved.
    conflict = client.post(path, headers={"x-operation-id": "op-http-2"})
    assert conflict.status_code == 409
    assert job_id in conflict.json()["detail"]

    # The same operation replayed is idempotent, not a second job.
    replay = client.post(path, headers={"x-operation-id": "op-http"})
    assert replay.status_code == 202
    assert replay.json()["job_id"] == job_id

    # A reloaded page finds the job again.
    assert client.get(path).json()["id"] == job_id
    assert client.get(f"/api/platform/repair-jobs/{job_id}").json()["status"] in {"queued", "running"}

    release.set()
    for _ in range(200):
        status = client.get(f"/api/platform/repair-jobs/{job_id}").json()["status"]
        if status not in {"queued", "running"}:
            break
        time.sleep(0.05)
    assert status == "succeeded"

    events = client.get(f"/api/platform/repair-jobs/{job_id}/events").json()
    assert [entry["stage"] for entry in events][-1] == "succeeded"
    assert client.get(f"/api/platform/jobs/{job_id}").json()["status"] == "completed"


def test_the_shared_job_ledger_mirrors_the_repair(harness, monkeypatch):
    _install(monkeypatch, _model())
    job = harness.submit()

    queued = harness.store.get_job(job.id)
    assert queued.status == "queued"
    assert queued.kind == "compendium_repair"
    assert queued.request_summary["chapter_id"] == harness.chapter.id

    harness.run_pending()
    completed = harness.store.get_job(job.id)
    assert completed.status == "completed"
    assert completed.retryable is False
    assert completed.result_summary["repair_status"] == "succeeded"
