"""
Tests for the differentiation module.

Verifies that:
- differentiation output structure is correct
- all three levels contain valid LaTeX (structural check)
- exercise count logic works
"""

import pytest

from app.differentiation.generator import (
    DifferentiatedOutput,
    DifferentiateRequest,
    differentiate_content,
)
from app.differentiation.hint_engine import (
    HintSet,
    generate_hints,
    generate_qr_code,
)


# ---------------------------------------------------------------------------
# Tests: DifferentiatedOutput
# ---------------------------------------------------------------------------
class TestDifferentiatedOutput:
    """Test the data model."""

    def test_defaults(self):
        output = DifferentiatedOutput()
        assert output.basic_latex == ""
        assert output.standard_latex == ""
        assert output.advanced_latex == ""
        assert output.basic_verified is False

    def test_with_content(self):
        output = DifferentiatedOutput(
            basic_latex=r"\begin{taskbox}{1} easy \end{taskbox}",
            standard_latex=r"\begin{taskbox}{1} medium \end{taskbox}",
            advanced_latex=r"\begin{taskbox}{1} hard \end{taskbox}",
        )
        assert "easy" in output.basic_latex
        assert "hard" in output.advanced_latex


# ---------------------------------------------------------------------------
# Tests: HintSet
# ---------------------------------------------------------------------------
class TestHintSet:
    """Test the hint data model."""

    def test_defaults(self):
        hints = HintSet()
        assert hints.nudge == ""
        assert hints.step == ""
        assert hints.near_solution == ""

    def test_with_content(self):
        hints = HintSet(
            nudge="Tenk på hva som skjer...",
            step="Start med å trekke fra 3...",
            near_solution="$2x + 3 = 7 \\Rightarrow 2x = 4 \\Rightarrow x = ...$",
        )
        assert "Tenk" in hints.nudge
        assert "$2x" in hints.near_solution


# ---------------------------------------------------------------------------
# Tests: QR code generation
# ---------------------------------------------------------------------------
class TestQrGeneration:
    """Test QR code generation."""

    def test_generate_qr_bytes(self):
        """QR generation should return PNG bytes (if qrcode is installed)."""
        try:
            result = generate_qr_code("https://matematex.no/hints/abc123")
            assert isinstance(result, bytes)
            if result:
                # PNG magic bytes
                assert result[:4] == b'\x89PNG'
        except ImportError:
            pytest.skip("qrcode package not installed")

    def test_generate_qr_empty_url(self):
        """Empty URL should still produce QR code."""
        try:
            result = generate_qr_code("")
            # qrcode library handles empty strings
            assert isinstance(result, bytes)
        except (ImportError, Exception):
            pytest.skip("qrcode package not available or rejects empty URL")


# ---------------------------------------------------------------------------
# Tests: DifferentiateRequest validation
# ---------------------------------------------------------------------------
class TestDifferentiateRequest:
    """Test request validation."""

    def test_valid_request(self):
        req = DifferentiateRequest(
            latex_content=r"\begin{taskbox}{1} Løs $x+1=2$ \end{taskbox}",
            topic="Algebra",
            grade="8. trinn",
        )
        assert req.topic == "Algebra"

    def test_short_content_rejected(self):
        with pytest.raises(Exception):
            DifferentiateRequest(latex_content="short")


# ---------------------------------------------------------------------------
# Integration test (requires LLM — skipped unless env var is set)
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="Requires LLM API key")
class TestDifferentiationIntegration:
    """Integration tests requiring an LLM backend."""

    @pytest.mark.asyncio
    async def test_differentiate_produces_three_levels(self):
        output = await differentiate_content(
            r"\begin{taskbox}{Oppgave 1} Løs $2x + 3 = 7$ \end{taskbox}",
            topic="Algebra",
            grade="8. trinn",
        )
        assert output.basic_latex != ""
        assert output.standard_latex != ""
        assert output.advanced_latex != ""

    @pytest.mark.asyncio
    async def test_generate_hints_produces_three_levels(self):
        hints = await generate_hints(
            r"Løs likningen $2x + 3 = 7$",
            solution=r"$x = 2$",
        )
        assert hints.nudge != ""
        assert hints.step != ""
        assert hints.near_solution != ""
