"""Regressions from the complete functions chapter, plus adversarial answers."""

from app.verification.math_checker import MathChecker
from app.verification.content_quality import _subtopic_covered


def test_inline_labels_do_not_capture_prose_or_display_equations():
    body = r"Bunnpunktets $y$-koordinat: \[3^2-6\cdot3+5=-4\] Punktet er $(3,-4)$."
    result = MathChecker().verify(body)
    assert result.claims_checked == result.claims_correct == 1
    assert not result.claims_unparseable


def test_each_example_uses_its_own_function_and_catches_wrong_value():
    body = r"""\begin{eksempel}La $f(x)=2x+4$. $f(0)=4$.\end{eksempel}
    \begin{eksempel}La $f(x)=3x+1$. $f(0)=4$.\end{eksempel}"""
    result = MathChecker().verify(body)
    assert result.claims_correct == 1
    assert result.claims_incorrect == 1
    assert not result.claims_unparseable


def test_numbered_solution_uses_corresponding_task():
    body = r"""\begin{taskbox}{Oppgave 1}$f(x)=2x+4$. Finn $f(0)$.\end{taskbox}
    \begin{taskbox}{Oppgave 2}$f(x)=3x+1$. Finn $f(0)$.\end{taskbox}
    \section*{Løsningsforslag}
    \textbf{Oppgave 1} a) $f(0)=4$
    \textbf{Oppgave 2} a) $f(0)=4$"""
    result = MathChecker().verify(body)
    assert result.claims_correct == 1
    assert result.claims_incorrect == 1
    assert not result.claims_unparseable


def test_wrong_equation_after_forty_claims_is_not_dropped():
    body = " ".join(f"${i}+1={i+1}$" for i in range(45)) + " $100+2=105$"
    assert MathChecker().verify(body).claims_incorrect == 1


def test_percent_calculation_and_wrong_percent():
    checker = MathChecker()
    assert checker.verify(r"$100\,\%-15\,\%=85\,\%$").claims_correct == 1
    assert checker.verify(r"$100\,\%-15\,\%=90\,\%$").claims_incorrect == 1


def test_norwegian_inflected_logarithm_rules_are_recognized():
    assert _subtopic_covered("logaritmereglene for tierlogaritmer", "Logaritmeregler")
    assert not _subtopic_covered("lineære funksjoner", "Logaritmeregler")
