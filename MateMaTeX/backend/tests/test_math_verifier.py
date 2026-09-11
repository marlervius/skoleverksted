"""
Tests for the SymPy-based math verification engine.

These tests ensure that the math checker correctly identifies:
- Correct equations
- Incorrect equations
- Correct solutions
- Incorrect solutions
"""

import pytest

from app.verification.math_checker import MathChecker


@pytest.fixture
def checker():
    return MathChecker()


# ---------------------------------------------------------------------------
# Equation verification
# ---------------------------------------------------------------------------
class TestEquationVerification:
    """Test verification of mathematical equations."""

    def test_correct_simple_equation(self, checker: MathChecker):
        """Simple arithmetic: 2 + 3 = 5."""
        latex = r"Summen er $2 + 3 = 5$."
        result = checker.verify(latex)
        assert result.claims_incorrect == 0

    def test_incorrect_simple_equation(self, checker: MathChecker):
        """Simple arithmetic error: 2 + 3 = 6."""
        latex = r"Summen er $2 + 3 = 6$."
        result = checker.verify(latex)
        assert result.claims_incorrect > 0

    def test_correct_fraction(self, checker: MathChecker):
        """Fraction: 6/3 = 2."""
        latex = r"Vi får $\frac{6}{3} = 2$."
        result = checker.verify(latex)
        assert result.claims_checked == 1
        assert result.claims_correct == 1
        assert result.claims_incorrect == 0

    def test_wrong_fraction_answer_is_caught(self, checker: MathChecker):
        """Braces must not hide a wrong answer from SymPy (grunnlov §1)."""
        latex = r"Regn ut: $\frac{1}{2} + \frac{1}{3} = \frac{2}{5}$."
        result = checker.verify(latex)
        assert result.claims_incorrect == 1

    def test_wrong_square_root_answer_is_caught(self, checker: MathChecker):
        latex = r"Vi får $\sqrt{16} = 5$."
        result = checker.verify(latex)
        assert result.claims_incorrect == 1

    def test_wrong_braced_exponent_is_caught(self, checker: MathChecker):
        latex = r"Da er $2^{3} = 9$."
        result = checker.verify(latex)
        assert result.claims_incorrect == 1

    def test_incorrect_fraction(self, checker: MathChecker):
        """Fraction error: 6/4 = 2."""
        latex = r"Vi forenkler: $6/4 = 2$."
        result = checker.verify(latex)
        assert result.claims_incorrect > 0

    def test_correct_multiplication(self, checker: MathChecker):
        """Multiplication: 3 * 4 = 12."""
        latex = r"Produktet er $3 \cdot 4 = 12$."
        result = checker.verify(latex)
        assert result.claims_incorrect == 0

    def test_correct_negative_numbers(self, checker: MathChecker):
        """Negative: -3 + 8 = 5."""
        latex = r"Vi regner ut $-3 + 8 = 5$."
        result = checker.verify(latex)
        assert result.claims_incorrect == 0

    def test_correct_square_root(self, checker: MathChecker):
        """Square root: sqrt(9) = 3."""
        latex = r"Vi får $\sqrt{9} = 3$."
        result = checker.verify(latex)
        assert result.claims_incorrect == 0

    def test_equations_to_solve_are_not_identity_errors(self, checker: MathChecker):
        latex = r"""
        Den generelle andregradslikningen er $ax^2 + bx + c = 0$.
        Løs eksponentiallikningene $2^x = 10$ og $10^x = 100$.
        """
        result = checker.verify(latex)
        assert result.claims_incorrect == 0
        assert result.claims_unparseable == 3

    def test_correct_symbolic_identity_is_verified(self, checker: MathChecker):
        latex = r"Identiteten $x + 1 = 1 + x$ gjelder for alle x."
        result = checker.verify(latex)
        assert result.claims_correct == 1
        assert result.claims_incorrect == 0

    def test_false_explicit_identity_is_incorrect(self, checker: MathChecker):
        latex = r"Identiteten $x^2 = x$ gjelder for alle x."
        result = checker.verify(latex)
        assert result.claims_incorrect == 1


class TestMultipleEquations:
    """Test documents with multiple equations."""

    @pytest.mark.parametrize("chain", [
        r"(-4)^2 - 9 = 7 > 0",
        r"(-4)^2 - 9 = 7 \geq 0",
        r"2+3 = 5 < 6",
        r"2+3 = 5 <= 5",
    ])
    def test_mixed_relation_chain(self, checker, chain):
        result = checker.verify(f"${chain}$")
        assert result.claims_correct == 1
        assert result.claims_unparseable == result.claims_incorrect == 0

    @pytest.mark.parametrize("chain", [
        r"(-4)^2 - 9 = 8 > 0",
        r"(-4)^2 - 9 = 7 < 0",
        r"2+3 = 5 > 6",
    ])
    def test_false_part_of_mixed_chain_blocks_delivery(self, checker, chain):
        assert checker.verify(f"${chain}$").claims_incorrect == 1

    def test_function_value_from_screenshot(self, checker):
        result = checker.verify(
            r"La $f(x) = \frac{2x+4}{x-1}$. "
            r"$f(0) = \frac{2 \cdot 0 + 4}{0 - 1} = \frac{4}{-1} = -4$"
        )
        assert result.claims_correct == 1
        assert result.claims_incorrect == result.claims_unparseable == 0

    def test_wrong_function_substitution_is_caught(self, checker):
        result = checker.verify(r"$f(x) = 2x+4$. $f(0) = 2+4 = 6$")
        assert result.claims_incorrect == 1

    def test_function_answer_without_intermediate_steps_is_checked(self, checker):
        assert checker.verify(r"$f(x)=2x+4$. $f(0)=5$").claims_incorrect == 1

    def test_scientific_notation_is_not_implicit_multiplication(self, checker):
        assert checker.verify(r"$1e-3 + 1e-3 = 0.002$").claims_correct == 1

    def test_missing_function_is_unresolved_not_incorrect(self, checker):
        result = checker.verify(r"$f(0) = 2+4 = 6$")
        assert result.claims_unparseable == 1
        assert result.claims_incorrect == 0

    def test_conflicting_functions_are_not_borrowed_from_another_exercise(self, checker):
        result = checker.verify(r"$f(x)=2x+4$. $f(x)=3x+1$. $f(0)=2+4=6$")
        assert result.claims_unparseable == 1

    def test_function_definitions_do_not_leak_between_documents(self, checker):
        checker.verify(r"$f(x)=2x+4$")
        assert checker.verify(r"$f(0)=2+2=4$").claims_unparseable == 1

    @pytest.mark.parametrize("latex", [
        r"$2 \cdot 3 + 1 = 6 + 1 = 7$",
        r"\[\frac{6}{3} = 2\]",
        r"$1 - 0{,}85 = 0{,}15$",
    ])
    def test_worked_calculation_is_fully_verified(self, checker, latex):
        result = checker.verify(latex)
        assert result.claims_correct == 1
        assert result.claims_unparseable == result.claims_incorrect == 0

    def test_wrong_last_step_of_chain_is_blocked(self, checker):
        result = checker.verify(r"$2 \cdot 3 = 6 = 7$")
        assert result.claims_incorrect == 1

    def test_unresolved_only_feedback_is_sent_to_author(self, checker):
        from app.verification.math_checker import format_errors_for_agent
        result = checker.verify(r"$f(0) = a \cdot 0 + b = b$")
        assert result.claims_unparseable == 1
        assert "f(0)" in format_errors_for_agent(result)

    def test_all_correct(self, checker: MathChecker):
        """Multiple correct equations."""
        latex = r"""
        Vi regner ut:
        $2 + 3 = 5$
        $10 - 4 = 6$
        $3 \cdot 7 = 21$
        """
        result = checker.verify(latex)
        assert result.claims_incorrect == 0

    def test_one_error_among_correct(self, checker: MathChecker):
        """One error among several correct equations."""
        latex = r"""
        Vi regner ut:
        $2 + 3 = 5$
        $10 - 4 = 7$
        $3 \cdot 7 = 21$
        """
        result = checker.verify(latex)
        assert result.claims_incorrect >= 1
        # The error should be the second equation
        errors = result.errors
        assert any("10" in e.latex_expression or "7" in e.latex_expression for e in errors)


class TestSolutionVerification:
    """Test verification of exercise solutions."""

    def test_correct_linear_solution(self, checker: MathChecker):
        """Verify that x=3 satisfies 2x+1=7."""
        latex = r"""
        \begin{taskbox}{Oppgave 1}
        Løs likningen $2x + 1 = 7$.
        \end{taskbox}

        \section*{Løsningsforslag}
        \textbf{Oppgave 1}\\
        a) $x = 3$
        """
        result = checker.verify(latex)
        # Should find and verify the solution
        assert result.claims_checked > 0


class TestEdgeCases:
    """Test edge cases and robustness."""

    def test_empty_content(self, checker: MathChecker):
        """Empty content should not crash."""
        result = checker.verify("")
        assert result.claims_checked == 0
        assert result.all_correct is True  # Vacuously true

    def test_no_math(self, checker: MathChecker):
        """Content without math should not crash."""
        latex = r"""
        \title{En tittel}
        \section{Introduksjon}
        Dette er en tekst uten matematikk.
        """
        result = checker.verify(latex)
        assert result.claims_checked == 0

    def test_unparseable_expression(self, checker: MathChecker):
        """Unparseable expressions should be counted but not block."""
        latex = r"Vi har $\mathbb{R} \setminus \{0\} = \text{noe rart}$."
        result = checker.verify(latex)
        # Should handle gracefully
        assert result.claims_incorrect == 0  # Can't verify ≠ incorrect

    def test_definition_skipped(self, checker: MathChecker):
        """Definitions like f(x) = 2x+1 should be skipped (not verifiable)."""
        latex = r"La $f(x) = 2x + 1$ være en funksjon."
        result = checker.verify(latex)
        # Definitions should be ignored
        assert result.claims_incorrect == 0

    def test_nested_frac_and_sqrt(self, checker: MathChecker):
        """Test nested \frac and \sqrt expressions do not hang and parse correctly."""
        latex = r"Vi har $\frac{\sqrt{16}}{2} = 2$."
        result = checker.verify(latex)
        assert result.claims_incorrect == 0

    def test_malformed_frac_no_hang(self, checker: MathChecker):
        """Test malformed fraction syntax does not cause an infinite loop/hang."""
        latex = r"Dette er malformert: $\frac{1 = 2$ og $\frac$."
        result = checker.verify(latex)
        # Should complete immediately and handle gracefully without hanging
        assert result.claims_checked == 0

    def test_formatting_macros(self, checker: MathChecker):
        """Test LaTeX formatting macros like \mathrm, \text, \mathbf are correctly parsed/stripped."""
        latex = r"Vi regner ut $\mathbf{a} + \mathrm{b} = c$ og $\text{f}(x) = 2$."
        # Note: \text{f}(x) = 2 is treated as definition because of "f(x) = ", which gets skipped
        result = checker.verify(latex)
        assert result.claims_incorrect == 0

    def test_exponents_and_subscripts(self, checker: MathChecker):
        """Test subscripts and exponents with curly braces."""
        latex = r"$\gamma_{1} = 2^{3}$ og $\delta_{ij} = 8$."
        # This will extract two claims: \gamma_{1} = 2^{3} and \delta_{ij} = 8
        result = checker.verify(latex)
        assert result.claims_incorrect == 0
