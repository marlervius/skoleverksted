import tempfile
import unittest
from pathlib import Path

from Skoleverksted.backend.platform.models import FeedbackCreate, Job, ProjectCreate, ProjectUpdate
from Skoleverksted.backend.platform.store import PlatformStore


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


if __name__ == "__main__":
    unittest.main()
