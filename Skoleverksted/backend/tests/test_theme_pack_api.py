import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Skoleverksted.backend.platform.models import ThemePackRequest
from Skoleverksted.backend.platform.router import create_theme_pack
from Skoleverksted.backend.platform.store import PlatformStore


class ThemePackApiTests(unittest.TestCase):
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

    def _request(self, **overrides) -> ThemePackRequest:
        payload = {
            "title": "Klima og bærekraft",
            "theme": "Klimaendringer i Norge",
            "subject": "Naturfag",
            "level": "VG1",
            "competency_goals": ["gjøre rede for drivhuseffekten"],
        }
        payload.update(overrides)
        return ThemePackRequest(**payload)

    def test_minimal_pack_is_not_reported_as_failed(self):
        """The passport judges the plan, not the three short briefs."""
        pack = create_theme_pack(self._request())

        self.assertEqual(len(pack.tasks), 3)
        self.assertNotEqual(pack.quality_passport.overall_status, "failed")
        content_check = next(
            check for check in pack.quality_passport.checks if check.code == "content_present"
        )
        self.assertEqual(content_check.status, "passed")

    def test_registered_source_is_carried_into_the_passport(self):
        pack = create_theme_pack(self._request(
            source_name="NDLA: Drivhuseffekten",
            source_text="Drivhuseffekten gjør jorda beboelig.",
        ))

        self.assertEqual(pack.quality_passport.sources, ["NDLA: Drivhuseffekten"])
        source_check = next(
            check for check in pack.quality_passport.checks if check.code == "sources"
        )
        self.assertEqual(source_check.status, "passed")

    def test_missing_source_is_still_reported_as_a_limitation(self):
        pack = create_theme_pack(self._request())

        self.assertEqual(pack.quality_passport.sources, [])
        self.assertTrue(
            any("kilder" in text.lower() for text in pack.quality_passport.limitations)
        )


if __name__ == "__main__":
    unittest.main()
