"""
Integration tests for the LangGraph pipeline.

Tests the pipeline graph structure and routing logic.
"""

import pytest

from app.models.state import (
    GenerationRequest,
    LatexCompilationResult,
    PipelineState,
    PipelineStatus,
    VerificationResult,
)
from app.pipeline.graph import (
    create_pipeline,
    finalize,
    route_final_math,
    run_math_blocked,
    should_retry_content,
    should_retry_latex,
    should_retry_math,
)


def test_pipeline_state_normalizes_legacy_null_pdf_fields():
    state = PipelineState.model_validate(
        {
            "request": {"grade": "8. trinn", "topic": "Algebra"},
            "pdf_path": None,
            "pdf_base64": None,
        }
    )
    assert state.pdf_path == ""
    assert state.pdf_base64 == ""


def test_math_blocked_keeps_pdf_fields_as_strings():
    state = PipelineState(
        request=GenerationRequest(grade="8. trinn", topic="Algebra"),
        math_verification=VerificationResult(claims_incorrect=1),
        pdf_path="old.pdf",
        pdf_base64="old",
    )
    result = run_math_blocked(state)
    assert result.pdf_path == ""
    assert result.pdf_base64 == ""
    PipelineState.model_validate(result.model_dump())


# ---------------------------------------------------------------------------
# Routing logic tests
# ---------------------------------------------------------------------------
class TestMathRetryRouting:
    """Test the math verification retry routing logic."""

    def test_retry_on_errors(self):
        """Should retry author when math errors exist and attempts remain."""
        state = PipelineState(
            request=GenerationRequest(grade="8. trinn", topic="Algebra"),
            math_verification=VerificationResult(
                claims_checked=5,
                claims_incorrect=2,
                all_correct=False,
            ),
            math_verification_attempts=1,
        )
        assert should_retry_math(state) == "author"

    def test_proceed_when_correct(self):
        """Kapittel receives the editor pass before final verification."""
        state = PipelineState(
            request=GenerationRequest(
                grade="8. trinn", topic="Algebra", material_type="kapittel"
            ),
            math_verification=VerificationResult(
                claims_checked=5,
                claims_correct=5,
                claims_incorrect=0,
                all_correct=True,
            ),
            math_verification_attempts=1,
        )
        assert should_retry_math(state) == "editor"

    def test_blocked_after_max_retries(self):
        """SymPy-confirmed errors block delivery after retries (grunnlov §1)."""
        state = PipelineState(
            request=GenerationRequest(
                grade="8. trinn", topic="Algebra", material_type="kapittel"
            ),
            math_verification=VerificationResult(
                claims_checked=5,
                claims_incorrect=2,
                all_correct=False,
            ),
            math_verification_attempts=3,  # At max
        )
        assert should_retry_math(state) == "math_blocked"

    def test_final_verification_blocks_editor_regression(self):
        state = PipelineState(
            request=GenerationRequest(
                grade="VG1 1T", topic="Algebra", material_type="kapittel"
            ),
            math_verification=VerificationResult(
                claims_checked=1,
                claims_incorrect=1,
                all_correct=False,
            ),
        )
        assert route_final_math(state) == "math_blocked"

    def test_skip_editor_for_arbeidsark(self):
        """Worksheets skip the slow LLM editor and go straight to validators."""
        state = PipelineState(
            request=GenerationRequest(grade="8. trinn", topic="Algebra"),
            verified_latex_body="\\begin{taskbox}{Oppgave} $2+2=4$ \\end{taskbox}",
            math_verification=VerificationResult(
                claims_checked=2,
                claims_correct=2,
                all_correct=True,
            ),
            math_verification_attempts=1,
        )
        assert should_retry_math(state) == "content_quality"
        assert state.edited_latex_body == state.verified_latex_body

    def test_first_correction_runs_when_mostly_unparseable(self):
        """Confirmed errors always get one correction pass before blocking."""
        state = PipelineState(
            request=GenerationRequest(grade="8. trinn", topic="Algebra"),
            math_verification=VerificationResult(
                claims_checked=69,
                claims_incorrect=3,
                claims_unparseable=66,
                all_correct=False,
            ),
            math_verification_attempts=1,
        )
        assert should_retry_math(state) == "author"


class TestLatexRetryRouting:
    """Test the LaTeX validation retry routing logic."""

    def test_retry_on_compilation_failure(self):
        """Should retry with fixer when compilation fails and attempts remain."""
        state = PipelineState(
            request=GenerationRequest(grade="8. trinn", topic="Algebra"),
            latex_compilation=LatexCompilationResult(
                success=False,
                errors=["! Undefined control sequence."],
            ),
            latex_fix_attempts=1,
        )
        assert should_retry_latex(state) == "latex_fixer"

    def test_proceed_when_compiled(self):
        """Should finalize when compilation succeeds."""
        state = PipelineState(
            request=GenerationRequest(grade="8. trinn", topic="Algebra"),
            latex_compilation=LatexCompilationResult(success=True),
            latex_fix_attempts=1,
        )
        assert should_retry_latex(state) == "finalize"

    def test_proceed_after_max_retries(self):
        """Should use latex_fallback after max fixer retries when still failing."""
        state = PipelineState(
            request=GenerationRequest(grade="8. trinn", topic="Algebra"),
            latex_compilation=LatexCompilationResult(
                success=False,
                errors=["! Emergency stop."],
            ),
            latex_fix_attempts=3,
        )
        assert should_retry_latex(state) == "latex_fallback"


class TestFinalizeStatus:
    """Test final status reflects math verification quality."""

    def test_failed_when_incorrect_fasit(self):
        state = PipelineState(
            request=GenerationRequest(grade="8. trinn", topic="Algebra"),
            raw_latex_body="\\title{T}\\maketitle",
            math_verification=VerificationResult(
                claims_checked=3,
                claims_incorrect=1,
                claims_unparseable=0,
                all_correct=False,
            ),
        )
        result = finalize(state)
        assert result.status == PipelineStatus.FAILED
        assert "grunnlov" in result.error_message.lower() or "§1" in result.error_message

    def test_completed_with_warnings_when_unparseable_only(self):
        state = PipelineState(
            request=GenerationRequest(grade="8. trinn", topic="Algebra"),
            raw_latex_body="\\title{T}\\maketitle",
            math_verification=VerificationResult(
                claims_checked=5,
                claims_correct=3,
                claims_unparseable=2,
                claims_incorrect=0,
                all_correct=False,
            ),
        )
        result = finalize(state)
        assert result.status == PipelineStatus.COMPLETED_WITH_WARNINGS
        assert "unparseable" in result.warning_reason

    def test_warning_reason_fallback(self):
        state = PipelineState(
            request=GenerationRequest(grade="8. trinn", topic="Algebra"),
            raw_latex_body="\\title{T}\\maketitle",
            used_latex_fallback=True,
            math_verification=VerificationResult(
                claims_checked=3, claims_correct=3, all_correct=True
            ),
        )
        result = finalize(state)
        assert result.status == PipelineStatus.COMPLETED_WITH_WARNINGS
        assert "fallback" in result.warning_reason

    def test_completed_when_math_clean(self):
        state = PipelineState(
            request=GenerationRequest(grade="8. trinn", topic="Algebra"),
            raw_latex_body="\\title{T}\\maketitle",
            math_verification=VerificationResult(
                claims_checked=3,
                claims_correct=3,
                all_correct=True,
            ),
        )
        result = finalize(state)
        assert result.status == PipelineStatus.COMPLETED
        assert result.warning_reason == ""


class TestRuleBasedLatexFix:
    """The fixer should repair trivial errors without calling an LLM."""

    def test_closes_unbalanced_braces(self):
        from app.pipeline.agents.latex_fixer import _try_rule_based_fix

        doc = "\\documentclass{article}\\begin{document}\\textbf{Hei\\end{document}"
        fixed = _try_rule_based_fix(doc)
        assert fixed is not None
        assert fixed.count("{") == fixed.count("}")

    def test_closes_unclosed_environment(self):
        from app.pipeline.agents.latex_fixer import _try_rule_based_fix

        doc = (
            "\\documentclass{article}\\begin{document}"
            "\\begin{itemize}\\item A\\end{document}"
        )
        fixed = _try_rule_based_fix(doc)
        assert fixed is not None
        assert "\\end{itemize}" in fixed

    def test_no_change_returns_none(self):
        from app.pipeline.agents.latex_fixer import _try_rule_based_fix

        doc = "\\documentclass{article}\\begin{document}Hei\\end{document}"
        assert _try_rule_based_fix(doc) is None


class TestGraphStructure:
    """Test that the graph is constructed correctly."""

    def test_graph_compiles(self):
        """The graph should compile without errors."""
        graph = create_pipeline()
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_has_all_nodes(self):
        """The graph should have all expected nodes."""
        graph = create_pipeline()
        # LangGraph stores nodes internally
        expected_nodes = {
            "pedagogue",
            "author",
            "math_verifier",
            "final_math_verifier",
            "content_quality",
            "editor",
            "tikz_validator",
            "table_validator",
            "latex_validator",
            "latex_fixer",
            "latex_fallback",
            "layout",
            "math_blocked",
            "finalize",
        }
        assert set(graph.nodes.keys()) == expected_nodes
        compiled = graph.compile()
        assert compiled is not None


class TestTikzSanitize:
    def test_fixes_quoted_math_in_pic_angle(self):
        from app.pipeline.agents.tikz_validator import sanitize_latex_body

        body = r"""
\begin{figure}[H]
\begin{tikzpicture}
\pic [angle eccentricity=1.3, "$\theta$", mainOrange] {angle=A--B--C};
\end{tikzpicture}
\end{figure}
"""
        cleaned, fixes = sanitize_latex_body(body)
        assert '"$\\theta$"' not in cleaned
        assert r"$\theta$" in cleaned
        assert any("quoted math" in f for f in fixes)
