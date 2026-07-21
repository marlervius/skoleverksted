import os
import unittest
from unittest.mock import patch

from Skoleverksted.backend.platform.cors import (
    DEFAULT_PRODUCTION_FRONTEND_ORIGINS,
    allowed_origins,
)


class CorsTests(unittest.TestCase):
    def test_keeps_localhost_as_development_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(allowed_origins(), ["http://localhost:3000"])

    def test_adds_fixed_vercel_origins_in_production(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "ALLOWED_ORIGINS": "https://example.invalid/",
            },
            clear=True,
        ):
            self.assertEqual(
                allowed_origins(),
                ["https://example.invalid", *DEFAULT_PRODUCTION_FRONTEND_ORIGINS],
            )

    def test_allows_production_origin_override_without_duplicates(self):
        origin = "https://skole.example.no"
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "ALLOWED_ORIGINS": origin,
                "SKOLEVERKSTED_PUBLIC_FRONTEND_URL": f"{origin}/",
            },
            clear=True,
        ):
            self.assertEqual(
                allowed_origins(),
                [origin, *DEFAULT_PRODUCTION_FRONTEND_ORIGINS],
            )


if __name__ == "__main__":
    unittest.main()
