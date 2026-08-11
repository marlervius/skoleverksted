from contextlib import contextmanager
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from Skoleverksted.backend.platform import router as router_module
from Skoleverksted.backend.platform.models import Job, YearPlanGenerateRequest
from Skoleverksted.backend.platform.router import generate_year_plan
from Skoleverksted.backend.platform.store import PlatformStore
from Skoleverksted.backend.platform.year_plan_jobs import run_year_plan_job


class FakeQueue:
    def __init__(self, store: PlatformStore) -> None:
        self.store = store

    def enqueue(self, job_id: str, *, module: str, kind: str, payload=None, project_id=None) -> Job:
        current = self.store.get_job(job_id)
        job = Job(
            id=job_id,
            module=module,
            kind=kind,
            status="queued",
            request_summary={"subject": payload.subject, "level": payload.level},
            attempt=(current.attempt + 1) if current else 1,
            retryable=True,
        )
        return self.store.upsert_job(job)

    @contextmanager
    def claim(self, job_id: str, *, auto_complete: bool = False):
        self.store.update_job_state(job_id, status="generating", progress=5, retryable=True)
        yield

    def finish(self, job_id: str, *, message: str = "Ferdig"):
        return self.store.update_job_state(
            job_id, status="completed", message=message, progress=100, retryable=False,
        )

    def fail(self, job_id: str, message: str):
        return self.store.update_job_state(
            job_id, status="failed", message=message, progress=100, retryable=True,
        )


def year_plan_request() -> YearPlanGenerateRequest:
    return YearPlanGenerateRequest(
        subject="Historie",
        level="VG2",
        school_year="2026-2027",
        lessons_per_week=2,
        lesson_minutes=45,
        teaching_weeks=38,
        number_of_periods=8,
        competency_goals=["utforske fortiden gjennom kilder"],
        constraints="",
        use_ai=False,
    )


def http_request(operation_id: str = "operation-1") -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/platform/year-plans/generate",
        "headers": [(b"x-operation-id", operation_id.encode("ascii"))],
    })


def test_generation_endpoint_registers_before_starting_model_work():
    with tempfile.TemporaryDirectory() as temp_dir:
        store = PlatformStore(Path(temp_dir) / "platform.sqlite3")
        queue = FakeQueue(store)
        with (
            patch("Skoleverksted.backend.platform.router.get_platform_store", return_value=store),
            patch("Skoleverksted.backend.platform.router.get_durable_job_queue", return_value=queue),
            patch("Skoleverksted.backend.platform.router.start_year_plan_worker") as start_worker,
        ):
            accepted = generate_year_plan(year_plan_request(), http_request())
            replay = generate_year_plan(year_plan_request(), http_request())

        assert accepted.status == "queued"
        assert accepted.plan_id is None
        assert accepted.status_url.endswith(accepted.job_id.replace(":", "%3A"))
        assert replay.job_id == accepted.job_id
        assert start_worker.call_count == 1
        assert store.list_year_plans() == []


def test_worker_completes_after_the_registering_request_has_returned():
    with tempfile.TemporaryDirectory() as temp_dir:
        store = PlatformStore(Path(temp_dir) / "platform.sqlite3")
        queue = FakeQueue(store)
        job = queue.enqueue(
            "year-plan:job-1",
            module="platform",
            kind="year_plan_generation",
            payload=year_plan_request(),
        )
        with (
            patch("Skoleverksted.backend.platform.year_plan_jobs.get_platform_store", return_value=store),
            patch("Skoleverksted.backend.platform.year_plan_jobs.get_durable_job_queue", return_value=queue),
        ):
            run_year_plan_job(job.id, year_plan_request())

        finished = store.get_job(job.id)
        assert finished is not None
        assert finished.status == "completed"
        plan_id = str(finished.result_summary["plan_id"])
        plan = store.get_year_plan(plan_id)
        assert plan is not None
        assert len(plan.periods) == 8
        assert plan.truth_passport is not None
        assert plan.truth_passport.status == "verified"


def test_worker_never_saves_a_plan_that_quality_control_blocks():
    with tempfile.TemporaryDirectory() as temp_dir:
        store = PlatformStore(Path(temp_dir) / "platform.sqlite3")
        queue = FakeQueue(store)
        job = queue.enqueue(
            "year-plan:blocked",
            module="platform",
            kind="year_plan_generation",
            payload=year_plan_request(),
        )
        with (
            patch("Skoleverksted.backend.platform.year_plan_jobs.get_platform_store", return_value=store),
            patch("Skoleverksted.backend.platform.year_plan_jobs.get_durable_job_queue", return_value=queue),
            patch(
                "Skoleverksted.backend.platform.year_plan_jobs.run_quality_pipeline",
                return_value=SimpleNamespace(source_approved=False),
            ),
        ):
            run_year_plan_job(job.id, year_plan_request())

        failed = store.get_job(job.id)
        assert failed is not None
        assert failed.status == "failed"
        assert "kildegodkjennes" in failed.message
        assert store.list_year_plans() == []


def test_http_flow_returns_202_then_exposes_the_completed_plan():
    with tempfile.TemporaryDirectory() as temp_dir:
        store = PlatformStore(Path(temp_dir) / "platform.sqlite3")
        queue = FakeQueue(store)
        app = FastAPI()
        app.include_router(router_module.router, prefix="/api/platform")
        with (
            patch("Skoleverksted.backend.platform.router.get_platform_store", return_value=store),
            patch("Skoleverksted.backend.platform.router.get_durable_job_queue", return_value=queue),
            patch("Skoleverksted.backend.platform.router.start_year_plan_worker") as start_worker,
            patch("Skoleverksted.backend.platform.year_plan_jobs.get_platform_store", return_value=store),
            patch("Skoleverksted.backend.platform.year_plan_jobs.get_durable_job_queue", return_value=queue),
        ):
            client = TestClient(app)
            response = client.post(
                "/api/platform/year-plans/generate",
                json=year_plan_request().model_dump(),
                headers={"x-operation-id": "http-operation"},
            )
            assert response.status_code == 202
            accepted = response.json()
            assert accepted["status"] == "queued"
            assert client.get(accepted["status_url"]).json()["status"] == "queued"
            assert store.list_year_plans() == []

            worker_job_id, worker_request = start_worker.call_args.args
            run_year_plan_job(worker_job_id, worker_request)

            finished = client.get(accepted["status_url"])
            assert finished.status_code == 200
            status = finished.json()
            assert status["status"] == "completed"
            plan_id = status["result_summary"]["plan_id"]
            plan_response = client.get(f"/api/platform/year-plans/{plan_id}")
            assert plan_response.status_code == 200
            assert plan_response.json()["truth_passport"]["status"] == "verified"
