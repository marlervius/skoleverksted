import tempfile
import unittest
from pathlib import Path

from Skoleverksted.backend.platform.models import (
    FeedbackCreate,
    Job,
    ProjectCreate,
    ProjectUpdate,
    YearPlanCreate,
    YearPlanMaterialCreate,
    YearPlanPeriod,
    YearPlanPeriodUpdate,
)
from Skoleverksted.backend.platform.store import PlatformStore
from Skoleverksted.backend.platform.teaching_package import build_package_from_period


class PlatformStoreTests(unittest.TestCase):
    def test_project_roundtrip_is_durable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "platform.sqlite3"
            first = PlatformStore(db)
            created = first.create_project(ProjectCreate(title="Klima", theme="Bærekraft", level="VG1"))
            updated = first.update_project(created.id, ProjectUpdate(status="ready", description="Fire timer"))

            self.assertIsNotNone(updated)
            self.assertEqual(updated.status, "ready")  # type: ignore[union-attr]
            self.assertEqual(updated.description, "Fire timer")  # type: ignore[union-attr]

            reopened = PlatformStore(db)
            loaded = reopened.get_project(created.id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.title, "Klima")  # type: ignore[union-attr]
            self.assertEqual(reopened.health()["status"], "healthy")

    def test_jobs_are_shared_across_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PlatformStore(Path(tmp) / "platform.sqlite3")
            store.upsert_job(Job(id="fag-1", module="fag", status="generating", progress=40))
            store.upsert_job(Job(id="norsk-1", module="norsk", status="completed", progress=100))
            store.upsert_job(Job(id="matte-1", module="matematikk", status="needs_review", progress=100))

            jobs = store.list_jobs()
            self.assertEqual({job.module for job in jobs}, {"fag", "norsk", "matematikk"})
            self.assertEqual(store.get_job("matte-1").status, "needs_review")  # type: ignore[union-attr]

    def test_queue_positions_and_restart_recovery_are_durable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PlatformStore(Path(tmp) / "platform.sqlite3")
            store.upsert_job(Job(id="first", module="fag", status="queued"))
            store.upsert_job(Job(id="second", module="norsk", status="queued"))

            self.assertEqual(store.get_job("first").queue_position, 1)  # type: ignore[union-attr]
            self.assertEqual(store.get_job("second").queue_position, 2)  # type: ignore[union-attr]
            self.assertEqual(store.recover_incomplete_jobs(), 2)

            recovered = store.get_job("second")
            self.assertEqual(recovered.status, "needs_review")  # type: ignore[union-attr]
            self.assertTrue(recovered.retryable)  # type: ignore[union-attr]
            self.assertIn("startet på nytt", recovered.message)  # type: ignore[union-attr]

    def test_feedback_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PlatformStore(Path(tmp) / "platform.sqlite3")
            saved = store.create_feedback(FeedbackCreate(
                module="fag", artifact_id="job-1", rating="down", reason="Fasit mangler"
            ))

            self.assertTrue(saved.id)
            self.assertEqual(store.list_feedback(), [saved])

    def test_year_plan_periods_and_materials_are_durable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PlatformStore(root / "platform.sqlite3")
            created = store.create_year_plan(YearPlanCreate(
                title="Historie VG2",
                subject="Historie",
                level="VG2",
                school_year="2026-2027",
                periods=[YearPlanPeriod(title="Middelalderen", lesson_count=8)],
            ))
            period = created.periods[0]
            updated = store.update_year_plan_period(
                created.id,
                period.id,
                YearPlanPeriodUpdate(status="ready", teacher_notes="Fungerer godt."),
            )
            self.assertIsNotNone(updated)
            self.assertEqual(updated.periods[0].status, "ready")  # type: ignore[union-attr]

            result = store.add_year_plan_material(
                created.id,
                period.id,
                YearPlanMaterialCreate(
                    title="Læringsark om middelalderen",
                    filename="middelalderen.pdf",
                ),
                b"%PDF-test",
            )
            self.assertIsNotNone(result)
            saved_plan, material = result  # type: ignore[misc]
            self.assertEqual(saved_plan.periods[0].materials[0].version, 1)
            loaded = PlatformStore(root / "platform.sqlite3").get_year_plan(created.id)
            self.assertEqual(loaded.periods[0].materials[0].title, material.title)  # type: ignore[union-attr]
            stored = store.get_year_plan_material(created.id, material.id)
            self.assertEqual(stored[1].read_bytes(), b"%PDF-test")  # type: ignore[index]

    def test_delete_year_plan_removes_owned_files_and_teaching_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PlatformStore(root / "platform.sqlite3")
            plan = store.create_year_plan(YearPlanCreate(
                title="Påbegynt matematikkplan",
                subject="Matematikk",
                level="VG1 1T",
                school_year="2026-2027",
                periods=[YearPlanPeriod(title="Algebra", lesson_count=8)],
            ))
            period = plan.periods[0]
            material_result = store.add_year_plan_material(
                plan.id,
                period.id,
                YearPlanMaterialCreate(title="Oppgaveark", filename="algebra.pdf"),
                b"%PDF-test",
            )
            self.assertIsNotNone(material_result)
            material = material_result[1]  # type: ignore[index]
            material_path = store.files_dir / plan.id / f"{material.id}.bin"

            package = build_package_from_period(
                plan,
                period,
                artifact_types=["presentation"],
            )
            store.create_teaching_package(package)
            package_dir = store.teaching_packages_dir / package.id
            package_dir.mkdir(parents=True)
            (package_dir / "preview.pptx").write_bytes(b"pptx-test")

            self.assertTrue(store.delete_year_plan(plan.id))
            self.assertIsNone(store.get_year_plan(plan.id))
            self.assertEqual(store.list_teaching_packages(year_plan_id=plan.id), [])
            self.assertFalse(material_path.exists())
            self.assertFalse(package_dir.exists())
            self.assertFalse(store.delete_year_plan(plan.id))


if __name__ == "__main__":
    unittest.main()
