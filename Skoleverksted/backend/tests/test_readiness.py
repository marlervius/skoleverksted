import unittest

from Skoleverksted.backend.platform.readiness import build_readiness


class ReadinessTests(unittest.TestCase):
    def test_complete_runtime_is_ready_without_exposing_secrets(self):
        commands = {
            "/usr/local/bin/typst": "/usr/local/bin/typst",
            "/usr/bin/pdflatex": "/usr/bin/pdflatex",
        }
        ready, report = build_readiness(
            {"status": "healthy", "backend": "sqlite"},
            environ={
                "GOOGLE_API_KEY": "super-secret",
                "TYPST_PATH": "/usr/local/bin/typst",
                "PDFLATEX_PATH": "/usr/bin/pdflatex",
                "REDIS_URL": "redis://private",
            },
            which=commands.get,
        )

        self.assertTrue(ready)
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["missing"], [])
        self.assertTrue(report["redis_configured"])
        self.assertNotIn("super-secret", str(report))
        self.assertNotIn("redis://private", str(report))

    def test_missing_required_dependencies_returns_degraded_report(self):
        ready, report = build_readiness(
            {"status": "unhealthy"},
            environ={},
            which=lambda _: None,
        )

        self.assertFalse(ready)
        self.assertEqual(report["status"], "degraded")
        self.assertEqual(
            set(report["missing"]),
            {"storage", "google_ai", "typst", "pdflatex"},
        )


if __name__ == "__main__":
    unittest.main()
