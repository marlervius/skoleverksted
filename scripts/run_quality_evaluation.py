"""Run the deterministic cross-module quality evaluation set."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from Skoleverksted.backend.platform.models import QualityPassportRequest
from Skoleverksted.backend.platform.quality import build_quality_passport


def evaluate(cases: list[dict]) -> dict:
    results = []
    for case in cases:
        passport = build_quality_passport(QualityPassportRequest(**case["request"]))
        expected = case["expected"]
        results.append(
            {
                "name": case["name"],
                "expected": expected,
                "actual": passport.overall_status,
                "passed": passport.overall_status == expected,
                "score": passport.score,
                "checks": len(passport.checks),
            }
        )
    passed = sum(1 for item in results if item["passed"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suite": "deterministic_quality_cases",
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "status": "passed" if passed == len(results) else "failed",
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("Skoleverksted/backend/evals/quality_cases.json"),
    )
    parser.add_argument("--report", type=Path, default=Path("output/test-runs/quality-evaluation.json"))
    args = parser.parse_args()
    report = evaluate(json.loads(args.cases.read_text(encoding="utf-8")))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
