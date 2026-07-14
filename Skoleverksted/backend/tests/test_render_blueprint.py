import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]


class RenderBlueprintTests(unittest.TestCase):
    def test_backend_blueprint_has_required_production_contract(self):
        blueprint = yaml.safe_load((REPO_ROOT / "render.yaml").read_text(encoding="utf-8"))
        service = blueprint["services"][0]

        self.assertEqual(service["runtime"], "docker")
        self.assertEqual(service["region"], "frankfurt")
        self.assertEqual(service["plan"], "starter")
        self.assertEqual(service["healthCheckPath"], "/health/ready")
        self.assertEqual(service["autoDeployTrigger"], "checksPass")
        self.assertEqual(service["disk"]["mountPath"], "/var/data")
        # Render rejects custom shutdown delays on services with a disk.
        self.assertNotIn("maxShutdownDelaySeconds", service)

        env_vars = {item["key"]: item for item in service["envVars"]}
        self.assertEqual(env_vars["OUTPUT_DIR"]["value"], "/var/data/output")
        self.assertEqual(
            env_vars["SKOLEVERKSTED_DB_PATH"]["value"],
            "/var/data/platform/skoleverksted.sqlite3",
        )
        self.assertFalse(env_vars["GOOGLE_API_KEY"]["sync"])
        self.assertNotIn("value", env_vars["GOOGLE_API_KEY"])
        self.assertTrue(env_vars["MATE_API_KEY"]["generateValue"])


if __name__ == "__main__":
    unittest.main()
