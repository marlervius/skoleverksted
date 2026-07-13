import unittest

from Skoleverksted.backend.platform.telemetry import _has_quality_content, _job_id_from_path, _module_for_path, _project_id_from_scope


class TelemetryContractTests(unittest.TestCase):
    def test_domain_and_job_ids_are_derived_from_mounted_paths(self):
        job_id = "12345678-1234-1234-1234-123456789abc"
        self.assertEqual(_module_for_path(f"/api/norsk/generation-status/{job_id}"), "norsk")
        self.assertEqual(_job_id_from_path(f"/api/norsk/generation-status/{job_id}"), job_id)
        self.assertEqual(_job_id_from_path(f"/api/matematikk/generate/{job_id}/result"), job_id)

    def test_project_header_is_validated(self):
        project_id = "a" * 32
        self.assertEqual(_project_id_from_scope({"headers": [(b"x-skoleverksted-project", project_id.encode())]}), project_id)
        self.assertIsNone(_project_id_from_scope({"headers": [(b"x-skoleverksted-project", b"../bad")]}))

    def test_progress_metadata_is_not_misrepresented_as_content_quality(self):
        self.assertFalse(_has_quality_content({"step": 4, "total_steps": 4, "message": "Ferdig"}))
        self.assertTrue(_has_quality_content({"basis_text": "Et ferdig læringsark"}))


if __name__ == "__main__":
    unittest.main()
