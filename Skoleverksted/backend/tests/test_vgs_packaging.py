import ast
import logging
import unittest
from pathlib import Path

from VGS_KI.backend.logging_utils import RequestLogger


REPO_ROOT = Path(__file__).resolve().parents[3]


class VgsPackagingTests(unittest.TestCase):
    def test_request_logger_is_package_safe(self):
        adapter = RequestLogger(logging.getLogger("test"), {"request_id": "abc123"})
        _, kwargs = adapter.process("message", {})
        self.assertEqual(kwargs["extra"]["request_id"], "abc123")

    def test_job_manager_does_not_import_top_level_main(self):
        path = REPO_ROOT / "VGS_KI" / "backend" / "job_manager.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        top_level_main_imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "main"
        ]
        self.assertEqual(top_level_main_imports, [])


if __name__ == "__main__":
    unittest.main()
