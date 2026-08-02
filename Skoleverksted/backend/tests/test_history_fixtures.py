import json
from pathlib import Path

import pytest

from Skoleverksted.backend.platform.compendium import _teacher_sources
from Skoleverksted.backend.platform.text_quality import inspect_markdown


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = ROOT / "evaluations" / "history_vg2"


def _fixture_names() -> list[str]:
    matrix = json.loads((FIXTURE_ROOT / "regression_matrix.json").read_text(encoding="utf-8"))
    return list(matrix["fixtures"])


@pytest.mark.parametrize("fixture_name", _fixture_names())
def test_history_fixture_contract_and_teacher_source_provenance(fixture_name: str):
    payload = json.loads((FIXTURE_ROOT / fixture_name / "input.json").read_text(encoding="utf-8"))
    assert payload["subject"] == "Historie"
    assert payload["level"] == "VG2"
    assert payload["chapter_count"] == 3
    assert payload["target_pages"] == 6
    assert payload["competency_goals"]
    assert payload["differentiation"]["support"]
    assert payload["differentiation"]["extension"]
    sources = _teacher_sources(payload["source_brief"])
    assert len(sources) >= 2
    assert all(source.origin == "teacher" for source in sources)
    assert all(source.fetch_status == "provided" for source in sources)


def test_fixture_regression_text_gate_is_not_a_model_snapshot():
    sample = "## Historisk framstilling\n\n" + ("Dette er en komplett faglig setning. " * 40)
    assert inspect_markdown(sample) == []
    broken = "## Tom overskrift\n\nSærlig ble en finansiell katastrofe.\n\n## Neste"
    assert {issue.code for issue in inspect_markdown(broken, min_words=1)} >= {
        "sentence_fragment",
        "empty_heading",
    }
