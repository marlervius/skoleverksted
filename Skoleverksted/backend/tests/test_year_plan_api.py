import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.requests import Request

from Skoleverksted.backend.platform.models import (
    YearPlanGenerateRequest,
    YearPlanPeriodUpdate,
)
from Skoleverksted.backend.platform.router import (
    delete_year_plan,
    download_year_plan_material,
    generate_year_plan,
    save_year_plan_material,
    update_year_plan_period,
)
from Skoleverksted.backend.platform.store import PlatformStore


class YearPlanApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = PlatformStore(Path(self.temp_dir.name) / "platform.sqlite3")
        self.store_patch = patch(
            "Skoleverksted.backend.platform.router.get_platform_store",
            return_value=self.store,
        )
        self.store_patch.start()

    def tearDown(self):
        self.store_patch.stop()
        self.temp_dir.cleanup()

    def test_generate_edit_save_and_download_material(self):
        plan = generate_year_plan(
            YearPlanGenerateRequest(
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
            ),
        )
        self.assertEqual(len(plan.periods), 8)

        period_id = plan.periods[0].id
        edited = update_year_plan_period(
            plan.id,
            period_id,
            YearPlanPeriodUpdate(title="Kilder og historiebruk", status="in_progress"),
        )
        self.assertEqual(edited.periods[0].title, "Kilder og historiebruk")

        pdf = b"%PDF-1.4\nannual-plan-test\n%%EOF"
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": pdf, "more_body": False}

        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/platform/year-plans/materials",
                "headers": [(b"content-type", b"application/pdf")],
            },
            receive,
        )
        saved = asyncio.run(
            save_year_plan_material(
                plan.id,
                period_id,
                request,
                title="Læringsark: Kilder",
                kind="learning_sheet",
                status="approved",
                filename="kilder.pdf",
                notes="",
            ),
        )
        material = saved["material"]
        self.assertEqual(material.version, 1)

        downloaded = download_year_plan_material(plan.id, material.id)
        self.assertEqual(downloaded.body, pdf)
        self.assertIn("kilder.pdf", downloaded.headers["content-disposition"])

    def test_delete_year_plan(self):
        plan = generate_year_plan(
            YearPlanGenerateRequest(
                subject="Naturfag",
                level="VG1",
                school_year="2026-2027",
                lessons_per_week=2,
                lesson_minutes=45,
                teaching_weeks=38,
                number_of_periods=4,
                competency_goals=[],
                constraints="",
                use_ai=False,
            ),
        )

        result = delete_year_plan(plan.id)

        self.assertEqual(result, {"deleted": True, "id": plan.id})
        self.assertIsNone(self.store.get_year_plan(plan.id))


if __name__ == "__main__":
    unittest.main()
