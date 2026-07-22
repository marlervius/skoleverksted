from __future__ import annotations

import json
from pathlib import Path

from Skoleverksted.backend.platform.models import QualityPassportRequest
from Skoleverksted.backend.platform.quality import build_quality_passport


CASES = json.loads((Path(__file__).parents[1] / "evals" / "quality_cases.json").read_text(encoding="utf-8"))


def test_quality_eval_suite_has_cross_module_coverage():
    modules = {case["request"]["module"] for case in CASES}
    assert modules == {"fag", "norsk", "matematikk"}
    assert len(CASES) >= 5


def test_quality_eval_cases_match_expected_outcomes():
    failures = []
    for case in CASES:
        passport = build_quality_passport(QualityPassportRequest(**case["request"]))
        if passport.overall_status != case["expected"]:
            failures.append(f"{case['name']}: {passport.overall_status} != {case['expected']}")
    assert not failures, "\n".join(failures)
