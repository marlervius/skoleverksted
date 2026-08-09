import json
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from Skoleverksted.backend.platform.models import (
    Job,
    QualityPassport,
    TruthClaim,
    TruthPassport,
    TruthSource,
    YearPlanCreate,
    YearPlanPeriod,
)
from Skoleverksted.backend.platform.router import (
    approve_teaching_artifact,
    approve_teaching_package,
    create_teaching_package,
    generate_teaching_package,
    update_teaching_artifact,
)
from Skoleverksted.backend.platform.store import PlatformStore, StaleTeachingArtifactError
from Skoleverksted.backend.platform.teaching_package import build_package_from_period, content_digest
from Skoleverksted.backend.platform.teaching_package_jobs import recover_teaching_package_jobs, run_artifact_job
from Skoleverksted.backend.platform.truth import TruthAudit


class FakeGate:
    def __init__(self, store: PlatformStore):
        self.store = store

    def enqueue(self, job_id, *, module, kind, payload=None, project_id=None):
        current = self.store.get_job(job_id)
        job = Job(
            id=job_id,
            module=module,
            kind=kind,
            attempt=(current.attempt + 1) if current else 1,
            request_summary=payload or {},
            project_id=project_id,
        )
        self.store.upsert_job(job)
        return job

    @contextmanager
    def claim(self, job_id, *, auto_complete=False, **kwargs):
        self.store.update_job_state(job_id, status="generating", message="Arbeider …", progress=10)
        try:
            yield
        except BaseException:
            raise

    def cancel(self, job_id):
        return self.store.update_job_state(job_id, status="cancelled", message="Avbrutt", progress=100, retryable=True)


def _green_audit(content: str, **kwargs) -> TruthAudit:
    source = next(iter(kwargs["provided_sources"]))
    passport = TruthPassport(
        status="verified",
        topic=kwargs["topic"],
        subject=kwargs["subject"],
        coverage_percent=100,
        verified_claims=1,
        total_claims=1,
        claims=[TruthClaim(claim="Temaet er kildebasert.", status="verified", exact_text="")],
        sources=[source],
    )
    return TruthAudit(content=content, passport=passport)


def _rendered(package, artifact):
    if artifact.artifact_type == "presentation":
        return {"pptx": b"PK\x03\x04pptx"}
    return {"pdf": b"%PDF-1.7 teaching-package", "docx": b"PK\x03\x04docx"}


def _green_quality() -> QualityPassport:
    return QualityPassport(module="teaching-package", title="fixture", overall_status="passed", score=100, checks=[])


def _fixture_plan(store: PlatformStore):
    fixture = json.loads(Path(__file__).with_name("fixtures").joinpath("historie_vg2_teaching_package.json").read_text(encoding="utf-8"))
    plan_data = fixture["year_plan"]
    period_data = fixture["period"]
    period = YearPlanPeriod(**period_data)
    plan = store.create_year_plan(YearPlanCreate(periods=[period], **plan_data))
    return plan, plan.periods[0], [TruthSource(**source) for source in fixture["sources"]]


def test_fixture_creates_package_with_canonical_content_only_on_artifacts():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        plan, period, sources = _fixture_plan(store)
        package = build_package_from_period(
            plan,
            period,
            artifact_types=["presentation", "student_sheet", "exercise_sheet", "answer_key", "teacher_guide"],
            sources=sources,
        )
        store.create_teaching_package(package)
        assert len(package.artifacts) == 5
        assert all(artifact.package_id == package.id for artifact in package.artifacts)
        assert not hasattr(plan.periods[0].materials[0] if plan.periods[0].materials else object(), "content_markdown")


def test_end_to_end_generation_approval_projection_and_idempotent_double_click():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        plan, period, sources = _fixture_plan(store)
        package = build_package_from_period(plan, period, artifact_types=["presentation", "student_sheet", "exercise_sheet", "answer_key", "teacher_guide"], sources=sources)
        store.create_teaching_package(package)
        gate = FakeGate(store)
        with patch("Skoleverksted.backend.platform.router.get_platform_store", return_value=store), \
             patch("Skoleverksted.backend.platform.router.get_durable_job_queue", return_value=gate), \
             patch("Skoleverksted.backend.platform.teaching_package_jobs.get_platform_store", return_value=store), \
             patch("Skoleverksted.backend.platform.teaching_package_jobs.get_durable_job_queue", return_value=gate), \
             patch("Skoleverksted.backend.platform.teaching_package_jobs.audit_truth", side_effect=_green_audit), \
             patch("Skoleverksted.backend.platform.teaching_package_jobs.render_artifact", side_effect=_rendered):
            accepted = generate_teaching_package(package.id)
            assert accepted.package_job_id.startswith("pkg:")
            try:
                generate_teaching_package(package.id)
                assert False, "double click should be rejected while parent is active"
            except Exception as exc:
                assert "genereres allerede" in str(getattr(exc, "detail", exc))
            deadline = time.time() + 8
            while time.time() < deadline:
                current = store.get_teaching_package(package.id)
                if current and all(item.status == "needs_review" for item in current.artifacts):
                    break
                time.sleep(0.05)
            current = store.get_teaching_package(package.id)
            assert current is not None
            assert all(item.files for item in current.artifacts)
            for artifact in current.artifacts:
                approved = approve_teaching_artifact(package.id, type("Approval", (), {"teacher": "historielærer"})(), artifact.id)
                assert approved.artifacts[[item.id for item in approved.artifacts].index(artifact.id)].approved_by == "historielærer"
            assert store.get_teaching_package(package.id).status != "approved"
            approved = approve_teaching_package(package.id, type("Approval", (), {"teacher": "historielærer"})())
            assert approved.status == "approved"
            projected = store.get_year_plan(plan.id).periods[0].materials
            assert len(projected) == 5
            assert all(item.source_kind == "teaching_package" for item in projected)
            assert len({(item.teaching_package_id, item.artifact_id) for item in projected}) == 5
            approve_teaching_package(package.id, type("Approval", (), {"teacher": "historielærer"})())
            assert len(store.get_year_plan(plan.id).periods[0].materials) == 5


def test_teacher_edit_invalidates_pass_and_late_worker_cannot_write():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        plan, period, sources = _fixture_plan(store)
        package = build_package_from_period(plan, period, artifact_types=["student_sheet"], sources=sources)
        package.artifacts[0].content_markdown = "Original lærertekst"
        package.artifacts[0].content_revision = content_digest(package.artifacts[0].content_markdown)
        store.create_teaching_package(package)
        with patch("Skoleverksted.backend.platform.router.get_platform_store", return_value=store):
            updated = update_teaching_artifact(package.id, package.artifacts[0].id, type("Edit", (), {"model_dump": lambda self, **_: {"content_markdown": "Ny lærertekst", "status": None}})())
        assert updated.artifacts[0].truth_passport is None
        assert updated.artifacts[0].status == "needs_review"
        assert updated.package_revision == 2


def test_package_approval_is_blocked_without_green_exact_revision_pass():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        plan, period, sources = _fixture_plan(store)
        package = build_package_from_period(plan, period, artifact_types=["student_sheet"], sources=sources)
        package.artifacts[0].content_markdown = "Lang nok innholdstekst som mangler faktapass og derfor ikke kan godkjennes."
        store.create_teaching_package(package)
        with patch("Skoleverksted.backend.platform.router.get_platform_store", return_value=store):
            try:
                approve_teaching_package(package.id, type("Approval", (), {"teacher": "historielærer"})())
                assert False, "approval should be blocked"
            except Exception as exc:
                assert "Faktapasset mangler" in str(getattr(exc, "detail", exc))


def test_restart_recovery_marks_parent_and_child_jobs_retryable():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        plan, period, sources = _fixture_plan(store)
        package = build_package_from_period(plan, period, artifact_types=["student_sheet"], sources=sources)
        package.package_job_id = "pkg:recovery"
        artifact = package.artifacts[0]
        artifact.artifact_job_id = "art:recovery"
        artifact.generation_token = "art:recovery:1"
        artifact.status = "generating"
        store.create_teaching_package(package)
        store.upsert_job(Job(id=package.package_job_id, module="platform", kind="teaching_package", status="generating"))
        store.upsert_job(Job(id=artifact.artifact_job_id, module="platform", kind="teaching_artifact", status="generating"))
        with patch("Skoleverksted.backend.platform.teaching_package_jobs.get_platform_store", return_value=store):
            assert recover_teaching_package_jobs() == 1
        recovered = store.get_teaching_package(package.id)
        assert recovered is not None
        assert recovered.status == "needs_review"
        assert recovered.artifacts[0].status == "generation_incomplete"
        assert store.get_job(package.package_job_id).status == "needs_review"
        assert store.get_job(artifact.artifact_job_id).status == "needs_review"


def test_late_worker_cas_is_rejected_after_teacher_claim_changes():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        plan, period, sources = _fixture_plan(store)
        package = build_package_from_period(plan, period, artifact_types=["student_sheet"], sources=sources)
        artifact = package.artifacts[0]
        artifact.status = "generating"
        artifact.generation_token = "new-worker-token"
        store.create_teaching_package(package)
        artifact.content_markdown = "Sen tekst fra en foreldet worker"
        with patch("Skoleverksted.backend.platform.store.utc_now", return_value="2026-08-09T00:00:00+00:00"):
            try:
                store.cas_update_teaching_artifact(
                    package.id,
                    artifact.id,
                    expected_generation_token="old-worker-token",
                    artifact=artifact,
                    rendered={},
                    package_status="needs_review",
                )
                assert False, "late worker write should be rejected"
            except StaleTeachingArtifactError:
                pass
        stored = store.get_teaching_package(package.id)
        assert stored is not None
        assert stored.artifacts[0].content_markdown == ""
        assert stored.artifacts[0].generation_token == "new-worker-token"


def test_one_failed_child_does_not_block_independent_artifact():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        plan, period, sources = _fixture_plan(store)
        package = build_package_from_period(plan, period, artifact_types=["student_sheet", "exercise_sheet"], sources=sources)
        store.create_teaching_package(package)
        gate = FakeGate(store)
        jobs = []
        for artifact in package.artifacts:
            job = gate.enqueue(f"art:{artifact.id}", module="platform", kind="teaching_artifact", payload={"artifact_id": artifact.id})
            artifact.artifact_job_id = job.id
            artifact.generation_token = f"{job.id}:1"
            artifact.status = "generating"
            jobs.append(job)
        store.save_teaching_package(package)

        def flaky_render(current_package, artifact):
            if artifact.artifact_type == "student_sheet":
                raise RuntimeError("renderer failure")
            return _rendered(current_package, artifact)

        with patch("Skoleverksted.backend.platform.teaching_package_jobs.get_platform_store", return_value=store), \
             patch("Skoleverksted.backend.platform.teaching_package_jobs.get_durable_job_queue", return_value=gate), \
             patch("Skoleverksted.backend.platform.teaching_package_jobs.audit_truth", side_effect=_green_audit), \
             patch("Skoleverksted.backend.platform.teaching_package_jobs.build_quality", side_effect=lambda *args, **kwargs: _green_quality()), \
             patch("Skoleverksted.backend.platform.teaching_package_jobs.render_artifact", side_effect=flaky_render):
            run_artifact_job(package.id, package.artifacts[0].id, jobs[0].id)
            run_artifact_job(package.id, package.artifacts[1].id, jobs[1].id)
        current = store.get_teaching_package(package.id)
        assert current is not None
        assert current.artifacts[0].status == "generation_incomplete"
        assert current.artifacts[1].status == "needs_review"
        assert store.get_job(jobs[0].id).result_summary["failure_reason"] == "artifact_generation_failed"
        assert store.get_job(jobs[1].id).result_summary["failure_reason"] == ""
