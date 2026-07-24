import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from Skoleverksted.backend.platform.router import router
from Skoleverksted.backend.platform.store import PlatformStore


class YearPlanApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = PlatformStore(Path(self.temp_dir.name) / "platform.sqlite3")
        app = FastAPI()
        app.include_router(router, prefix="/api/platform")
        self.store_patch = patch(
            "Skoleverksted.backend.platform.router.get_platform_store",
            return_value=self.store,
        )
        self.store_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.store_patch.stop()
        self.temp_dir.cleanup()

    def test_generate_edit_save_and_download_material(self):
        generated = self.client.post(
            "/api/platform/year-plans/generate",
            json={
                "subject": "Historie",
                "level": "VG2",
                "school_year": "2026-2027",
                "lessons_per_week": 2,
                "lesson_minutes": 45,
                "teaching_weeks": 38,
                "number_of_periods": 8,
                "competency_goals": ["utforske fortiden gjennom kilder"],
                "constraints": "",
                "use_ai": False,
            },
        )
        self.assertEqual(generated.status_code, 201)
        plan = generated.json()
        self.assertEqual(len(plan["periods"]), 8)

        period_id = plan["periods"][0]["id"]
        edited = self.client.patch(
            f"/api/platform/year-plans/{plan['id']}/periods/{period_id}",
            json={"title": "Kilder og historiebruk", "status": "in_progress"},
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["periods"][0]["title"], "Kilder og historiebruk")

        pdf = b"%PDF-1.4\nannual-plan-test\n%%EOF"
        saved = self.client.post(
            f"/api/platform/year-plans/{plan['id']}/periods/{period_id}/materials",
            params={
                "title": "Læringsark: Kilder",
                "kind": "learning_sheet",
                "status": "approved",
                "filename": "kilder.pdf",
            },
            content=pdf,
            headers={"Content-Type": "application/pdf"},
        )
        self.assertEqual(saved.status_code, 201)
        material = saved.json()["material"]
        self.assertEqual(material["version"], 1)

        downloaded = self.client.get(
            f"/api/platform/year-plans/{plan['id']}/materials/{material['id']}/download",
        )
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, pdf)
        self.assertIn("kilder.pdf", downloaded.headers["content-disposition"])


if __name__ == "__main__":
    unittest.main()
