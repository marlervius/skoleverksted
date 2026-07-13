"""Tests for M1 reference scorer (M1-testprotokoll)."""

import pytest

from m1.scorer import MISMATCH, UNCERTAIN, VERIFIED, aggregate, answer_check


class TestAnswerCheck:
    def test_identical_expr(self):
        assert answer_check("2*x + 3", "3 + 2*x") == VERIFIED

    def test_wrong_expr(self):
        assert answer_check("x**2", "x**3") == MISMATCH

    def test_equivalent_form(self):
        assert answer_check("(x+1)**2", "x**2 + 2*x + 1") == VERIFIED

    def test_integral_up_to_constant(self):
        assert answer_check("x**2", "x**2 + 5", mode="integral") == VERIFIED

    def test_set_mode(self):
        assert answer_check("1, -2", "-2, 1", mode="set") == VERIFIED

    def test_prose_not_mismatch(self):
        assert answer_check("vis at linjen er parallell", "vis at linjen er parallell") == UNCERTAIN

    def test_unparseable(self):
        assert answer_check("not valid sympy {{{", "also bad") == UNCERTAIN


class TestAggregate:
    def test_example_csv_totals(self):
        from pathlib import Path

        csv_path = Path(__file__).resolve().parents[2] / "m1_skjema_eksempel.csv"
        by_level, _ = aggregate(str(csv_path))
        assert "1T" in by_level
        assert "R1" in by_level
        assert by_level["1T"]["poeng"] == 35
        assert by_level["R1"]["poeng"] == 34
        assert pytest.approx(by_level["1T"]["groenn"], rel=0.01) == 24
