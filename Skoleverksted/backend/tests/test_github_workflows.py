from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOW_DIR = Path(__file__).resolve().parents[3] / ".github" / "workflows"


def test_job_level_environment_does_not_use_runner_context() -> None:
    """The runner context is unavailable while GitHub expands job-level env."""

    for workflow_path in WORKFLOW_DIR.glob("*.yml"):
        workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        for job_name, job in (workflow.get("jobs") or {}).items():
            environment = job.get("env") or {}
            invalid = {
                name: value
                for name, value in environment.items()
                if "${{ runner." in str(value)
            }
            assert not invalid, f"{workflow_path.name}:{job_name} uses runner context in job env: {invalid}"
