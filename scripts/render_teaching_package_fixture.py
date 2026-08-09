"""Create local Historie VG2 TeachingPackage example artifacts for visual QA."""

from __future__ import annotations

import json
from pathlib import Path

from Skoleverksted.backend.platform.models import TruthSource, YearPlan, YearPlanPeriod
from Skoleverksted.backend.platform.teaching_package import build_package_from_period, draft_content
from Skoleverksted.backend.platform.teaching_package_renderer import render_artifact


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "Skoleverksted" / "backend" / "tests" / "fixtures" / "historie_vg2_teaching_package.json"
OUTPUT = ROOT / "output" / "teaching-package-fixture"


def main() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    period = YearPlanPeriod(**data["period"])
    plan = YearPlan(periods=[period], **data["year_plan"])
    sources = [TruthSource(**source) for source in data["sources"]]
    package = build_package_from_period(
        plan,
        period,
        artifact_types=["presentation", "student_sheet", "exercise_sheet", "answer_key", "teacher_guide"],
        sources=sources,
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for artifact in package.artifacts:
        artifact.content_markdown = draft_content(package, artifact.artifact_type)
        for extension, payload in render_artifact(package, artifact).items():
            (OUTPUT / f"{artifact.artifact_type}.{extension}").write_bytes(payload)
    (OUTPUT / "manifest.json").write_text(package.model_dump_json(indent=2), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
