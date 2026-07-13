"""Run M1 report on the example scoring sheet (smoke test for M1 tooling)."""

from m1.scorer import report


def test_m1_example_report_runs(capsys):
    from pathlib import Path

    csv_path = Path(__file__).resolve().parents[2] / "m1_skjema_eksempel.csv"
    report(str(csv_path))
    out = capsys.readouterr().out
    assert "M1-RESULTAT" in out
    assert "1T" in out
    assert "R1" in out
