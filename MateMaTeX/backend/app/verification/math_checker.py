"""
SymPy-based mathematical verification engine.

Extracts mathematical claims from LaTeX and verifies them programmatically.
This is NOT an LLM — it is a symbolic computation engine that catches
arithmetic errors, incorrect solutions, and invalid equations.
"""

from __future__ import annotations

import re
import structlog
from sympy import Eq, Symbol, simplify, solve, sqrt, sympify, expand, cancel
from app.models.state import MathClaim, VerificationResult
from m1.scorer import looks_like_prose, numeric_agreement

logger = structlog.get_logger()

# Timeout for the entire verification pass (seconds)
_TOTAL_TIMEOUT = 90
# Max time per individual claim (seconds) — avoids SymPy simplify hangs
_CLAIM_TIMEOUT = 8


class MathChecker:
    """
    Extracts and verifies mathematical claims from LaTeX content.

    Supports:
    - Equation verification (LHS = RHS)
    - Solution verification (check that x=a satisfies the original equation)
    - Arithmetic computations (2 + 3 = 5)
    - Fraction/root simplification
    """

    # Patterns to extract mathematical claims from LaTeX
    _MAX_CLAIMS = 40

    _EQUATION_PATTERNS = [
        # Standalone equation: $expr = expr$
        re.compile(r'\$([^$]+?)\s*=\s*([^$]+?)\$'),
        # Display equation: \[ expr = expr \]
        re.compile(r'\\\[([^\\]+?)\s*=\s*([^\\]+?)\\\]'),
    ]

    # Pattern for "Oppgave N ... fasit: answer" or solution blocks
    _SOLUTION_PATTERNS = [
        # a) $x = 3$  or  a) x = 3
        re.compile(r'[a-z]\)\s*\$?\\?x\s*=\s*([^$\\\n,]+)\$?'),
    ]

    # Patterns to find equations inside taskbox environments
    _TASK_EQUATION_PATTERN = re.compile(
        r'\\begin\{taskbox\}\{([^}]*)\}(.*?)\\end\{taskbox\}',
        re.DOTALL,
    )

    _SOLUTION_SECTION_PATTERN = re.compile(
        r'\\section\*\{Løsningsforslag\}(.*?)(?:\\section|\Z)',
        re.DOTALL,
    )

    def verify(self, latex_content: str) -> VerificationResult:
        """
        Run full mathematical verification on the LaTeX content.

        Returns a VerificationResult with details on every claim checked.
        The whole pass is bounded by ``_TOTAL_TIMEOUT``; claims run in-process
        (SymPy is already loaded in this interpreter — a thread pool caused
        spurious timeouts on Windows when workers first touched SymPy).
        """
        claims = self._extract_claims(latex_content)
        result = VerificationResult()
        result.claims_checked = len(claims)

        import time

        start_time = time.monotonic()

        for claim in claims:
            # Check total timeout
            if time.monotonic() - start_time > _TOTAL_TIMEOUT:
                logger.warning("math_verification_total_timeout", checked_so_far=result.claims_correct + result.claims_incorrect + result.claims_unparseable)
                break

            claim_start = time.monotonic()
            try:
                self._verify_claim(claim)
                if time.monotonic() - claim_start > _CLAIM_TIMEOUT:
                    claim.is_correct = None
                    claim.error_message = "Claim verification timed out"
                    logger.warning(
                        "claim_verification_timeout",
                        claim=claim.latex_expression[:80],
                        seconds=round(time.monotonic() - claim_start, 1),
                    )
            except Exception as e:
                claim.is_correct = None
                claim.error_message = f"Verification error: {e}"

            if claim.is_correct is True:
                result.claims_correct += 1
            elif claim.is_correct is False:
                result.claims_incorrect += 1
                result.errors.append(claim)
            else:
                result.claims_unparseable += 1
                result.unparseable_claims.append(claim)

        result.all_correct = result.claims_incorrect == 0
        result.summary = (
            f"Checked {result.claims_checked} claims: "
            f"{result.claims_correct} correct, "
            f"{result.claims_incorrect} incorrect, "
            f"{result.claims_unparseable} unparseable."
        )

        logger.info(
            "math_verification_complete",
            checked=result.claims_checked,
            correct=result.claims_correct,
            incorrect=result.claims_incorrect,
            unparseable=result.claims_unparseable,
            duration=round(time.monotonic() - start_time, 1),
        )

        return result

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    def _extract_claims(self, latex_content: str) -> list[MathClaim]:
        """Extract verifiable mathematical claims from the LaTeX."""
        claims: list[MathClaim] = []

        # 1. Extract equation claims (a = b style)
        claims.extend(self._extract_equation_claims(latex_content))

        # 2. Extract solution claims (match exercises with their solutions)
        claims.extend(self._extract_solution_claims(latex_content))

        return self._cap_claims(claims)

    def _extract_equation_claims(self, content: str) -> list[MathClaim]:
        """Extract 'LHS = RHS' equations from inline/display math."""
        claims: list[MathClaim] = []

        for pattern in self._EQUATION_PATTERNS:
            for match in pattern.finditer(content):
                lhs_raw = match.group(1).strip()
                rhs_raw = match.group(2).strip()

                if not self._is_valid_math_fragment(lhs_raw) or not self._is_valid_math_fragment(rhs_raw):
                    continue

                # Skip trivial definitions (x = ...) with no computation
                if self._is_definition(lhs_raw, rhs_raw):
                    continue
                if not self._looks_like_computation(lhs_raw, rhs_raw):
                    continue

                claim = MathClaim(
                    latex_expression=f"{lhs_raw} = {rhs_raw}",
                    claim_type="equation",
                    context=content[max(0, match.start() - 40):match.end() + 40],
                )
                claims.append(claim)

        return claims

    def _extract_solution_claims(self, content: str) -> list[MathClaim]:
        """
        Extract exercise-solution pairs and verify solutions are correct.

        Looks for exercises with equations and matches them to solutions.
        """
        claims: list[MathClaim] = []

        # Find the solution section
        sol_match = self._SOLUTION_SECTION_PATTERN.search(content)
        if not sol_match:
            return claims

        solution_text = sol_match.group(1)

        # Extract tasks and their equations
        for task_match in self._TASK_EQUATION_PATTERN.finditer(content):
            task_title = task_match.group(1)
            task_body = task_match.group(2)

            # Find equations in the task (e.g., "Løs likningen $2x + 3 = 7$")
            equations_in_task = re.findall(r'\$([^$]*?[=<>][^$]*?)\$', task_body)

            # Find the corresponding solution
            task_num = re.search(r'(\d+)', task_title)
            if task_num:
                sol_pattern = re.compile(
                    rf'\\textbf\{{Oppgave\s*{task_num.group(1)}\}}(.*?)(?=\\textbf|$)',
                    re.DOTALL,
                )
                sol_match_task = sol_pattern.search(solution_text)
                if sol_match_task:
                    sol_text = sol_match_task.group(1)

                    # For each sub-answer (a), b), etc.)
                    sub_answers = re.findall(
                        r'([a-z])\)\s*\$?([^$\n,]+?)\$?(?:\s|\\|$)',
                        sol_text,
                    )
                    for sub_letter, answer in sub_answers:
                        if '=' in answer:
                            claim = MathClaim(
                                latex_expression=answer.strip(),
                                claim_type="solution",
                                context=f"Oppgave {task_num.group(1)}{sub_letter}): equations={equations_in_task}",
                            )
                            claims.append(claim)

        return claims

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    def _verify_claim(self, claim: MathClaim) -> None:
        """Verify a single mathematical claim using SymPy."""
        try:
            if claim.claim_type == "equation":
                self._verify_equation(claim)
            elif claim.claim_type == "solution":
                self._verify_solution(claim)
            else:
                self._verify_equation(claim)
        except Exception as e:
            claim.is_correct = None
            claim.error_message = f"Verification failed: {e}"
            logger.debug(
                "claim_verification_error",
                claim=claim.latex_expression,
                error=str(e),
            )

    def _verify_equation(self, claim: MathClaim) -> None:
        """Verify that LHS = RHS symbolically."""
        expr_str = claim.latex_expression

        if '=' not in expr_str:
            claim.is_correct = None
            claim.error_message = "No equality found"
            return

        parts = expr_str.split('=', 1)
        lhs_latex = parts[0].strip()
        rhs_latex = parts[1].strip()

        try:
            lhs = self._parse_latex_expr(lhs_latex)
            rhs = self._parse_latex_expr(rhs_latex)
        except Exception as e:
            claim.is_correct = None
            claim.error_message = f"Parse error: {e}"
            return

        if lhs is None or rhs is None:
            claim.is_correct = None
            claim.error_message = "Could not parse one or both sides"
            return

        if looks_like_prose(lhs, rhs):
            claim.is_correct = None
            claim.error_message = "Looks like prose, not a verifiable expression (M1)"
            return

        # Support vector/coordinate list/tuple comparison
        if isinstance(lhs, (list, tuple)) and isinstance(rhs, (list, tuple)):
            if len(lhs) != len(rhs):
                claim.is_correct = False
                claim.error_message = f"Vector length mismatch: {len(lhs)} ≠ {len(rhs)}"
                return
            for i, (l, r) in enumerate(zip(lhs, rhs)):
                try:
                    diff_raw = l - r
                    if diff_raw == 0 or getattr(diff_raw, "is_zero", False) is True:
                        continue
                    
                    # Try cheap checks before heavy simplify
                    resolved = False
                    for simplifier in (expand, cancel):
                        try:
                            diff_simple = simplifier(diff_raw)
                            if diff_simple == 0 or getattr(diff_simple, "is_zero", False) is True:
                                resolved = True
                                break
                        except Exception:
                            pass
                    if resolved:
                        continue

                    diff = simplify(diff_raw)
                    if diff == 0 or getattr(diff, "is_zero", False) is True:
                        continue
                    
                    try:
                        d = complex(diff.evalf())
                        if abs(d) < 1e-9:
                            continue
                    except (TypeError, ValueError):
                        pass

                    claim.is_correct = False
                    claim.error_message = f"Mismatch at element {i+1}: {l} ≠ {r}"
                    return
                except Exception as e:
                    claim.is_correct = None
                    claim.error_message = f"Could not verify element {i+1}: {e}"
                    return
            claim.is_correct = True
            claim.expected_result = str(rhs)
            claim.actual_result = str(lhs)
            return

        # Check symbolic equality (avoid `complex(sympy)` — unreliable for Rationals)
        try:
            # First check direct physical equality of parsed objects
            if lhs == rhs:
                claim.is_correct = True
                claim.expected_result = str(rhs)
                claim.actual_result = str(lhs)
                return

            lhs_diff = lhs - rhs
            if lhs_diff == 0 or getattr(lhs_diff, "is_zero", False) is True:
                claim.is_correct = True
                claim.expected_result = str(rhs)
                claim.actual_result = str(lhs)
                return

            # Try cheap checks before heavy simplify
            for simplifier in (expand, cancel):
                try:
                    diff_simple = simplifier(lhs_diff)
                    if diff_simple == 0 or getattr(diff_simple, "is_zero", False) is True:
                        claim.is_correct = True
                        claim.expected_result = str(rhs)
                        claim.actual_result = str(lhs)
                        return
                except Exception:
                    pass

            diff = simplify(lhs_diff)
            if diff == 0 or getattr(diff, "is_zero", False) is True:
                claim.is_correct = True
                claim.expected_result = str(rhs)
                claim.actual_result = str(lhs)
                return

            try:
                d = complex(diff.evalf())
                if abs(d) < 1e-9:
                    claim.is_correct = True
                    claim.expected_result = str(rhs)
                    claim.actual_result = str(lhs)
                    return
            except (TypeError, ValueError):
                pass

            if getattr(diff, "free_symbols", None):
                # A symbolic equation can be an equation to solve/define, not an
                # identity. Numeric disagreement therefore does NOT prove a
                # fasit error unless the surrounding text explicitly claims an
                # identity (e.g. "for alle x"). This prevents task equations
                # such as 2^x = 10 from being blocked as false statements.
                num = numeric_agreement(lhs, rhs, lhs.free_symbols | rhs.free_symbols)
                if num is True:
                    claim.is_correct = True
                    claim.expected_result = str(rhs)
                    claim.actual_result = str(lhs)
                    return
                if num is False:
                    if self._context_claims_identity(claim.context):
                        claim.is_correct = False
                        claim.error_message = (
                            f"LHS ({lhs}) ≠ RHS ({rhs}) for generic values "
                            "(identity check)"
                        )
                    else:
                        claim.is_correct = None
                        claim.error_message = (
                            "Symbolic equation may be a condition to solve; "
                            "not treated as an identity"
                        )
                    return
                claim.is_correct = None
                claim.error_message = "Contains unknown symbols; cannot verify numerically"
                return

            # Only call simplify on LHS/RHS if it fails (for the error message only!)
            simplified_lhs = simplify(lhs)
            simplified_rhs = simplify(rhs)
            claim.expected_result = str(simplified_rhs)
            claim.actual_result = str(simplified_lhs)
            claim.is_correct = False
            claim.error_message = (
                f"LHS ({simplified_lhs}) ≠ RHS ({simplified_rhs}), "
                f"difference = {diff}"
            )
        except (TypeError, ValueError):
            try:
                ev = Eq(lhs, rhs)
                claim.is_correct = bool(ev) if ev in (True, False) else False
                if not claim.is_correct:
                    claim.error_message = f"Could not prove equality: {ev}"
            except Exception:
                claim.is_correct = None
                claim.error_message = "Could not determine equality"

    def _verify_solution(self, claim: MathClaim) -> None:
        """
        Verify a solution claim like 'x = 3' against its equation context.
        """
        # Extract variable and value from the solution
        sol_match = re.match(r'\\?([a-z])\s*=\s*(.+)', claim.latex_expression.strip())
        if not sol_match:
            claim.is_correct = None
            claim.error_message = "Could not parse solution format"
            return

        var_name = sol_match.group(1)
        value_str = sol_match.group(2).strip()

        try:
            value = self._parse_latex_expr(value_str)
        except Exception:
            claim.is_correct = None
            claim.error_message = f"Could not parse solution value: {value_str}"
            return

        # Try to find and parse the original equation from context
        eq_strs = re.findall(r"equations=\['([^']+)'\]", claim.context)
        if not eq_strs:
            eq_strs = re.findall(r'equations=\["([^"]+)"\]', claim.context)

        if not eq_strs:
            claim.is_correct = None
            claim.error_message = "No equation found in context to verify against"
            return

        var = Symbol(var_name)

        for eq_str in eq_strs:
            if '=' not in eq_str:
                continue

            parts = eq_str.split('=', 1)
            try:
                lhs = self._parse_latex_expr(parts[0].strip())
                rhs = self._parse_latex_expr(parts[1].strip())
            except Exception:
                continue

            if lhs is None or rhs is None:
                continue

            # Substitute the claimed solution
            try:
                # Support element-by-element substitution for lists
                if isinstance(lhs, (list, tuple)) or isinstance(rhs, (list, tuple)):
                    if isinstance(lhs, (list, tuple)) and isinstance(rhs, (list, tuple)) and len(lhs) == len(rhs):
                        all_match = True
                        for l, r in zip(lhs, rhs):
                            diff_raw = (l - r).subs(var, value)
                            if diff_raw == 0 or getattr(diff_raw, "is_zero", False) is True:
                                continue
                            resolved = False
                            for simplifier in (expand, cancel):
                                try:
                                    diff_simple = simplifier(diff_raw)
                                    if diff_simple == 0 or getattr(diff_simple, "is_zero", False) is True:
                                        resolved = True
                                        break
                                except Exception:
                                    pass
                            if resolved:
                                continue
                            diff = simplify(diff_raw)
                            if diff == 0 or getattr(diff, "is_zero", False) is True:
                                continue
                            try:
                                if abs(complex(diff)) < 1e-10:
                                    continue
                            except (TypeError, ValueError):
                                pass
                            all_match = False
                            break
                        if all_match:
                            claim.is_correct = True
                            claim.expected_result = str(value)
                            claim.actual_result = str(value)
                            return
                    continue

                diff_raw = (lhs - rhs).subs(var, value)
                if diff_raw == 0 or getattr(diff_raw, "is_zero", False) is True:
                    claim.is_correct = True
                    claim.expected_result = str(value)
                    claim.actual_result = str(value)
                    return

                # Try cheap simplifications
                resolved = False
                for simplifier in (expand, cancel):
                    try:
                        diff_simple = simplifier(diff_raw)
                        if diff_simple == 0 or getattr(diff_simple, "is_zero", False) is True:
                            resolved = True
                            break
                    except Exception:
                        pass
                if resolved:
                    claim.is_correct = True
                    claim.expected_result = str(value)
                    claim.actual_result = str(value)
                    return

                diff = simplify(diff_raw)
                if diff == 0 or getattr(diff, "is_zero", False) is True:
                    claim.is_correct = True
                    claim.expected_result = str(value)
                    claim.actual_result = str(value)
                    return
                
                try:
                    val_complex = complex(diff)
                    if abs(val_complex) < 1e-10:
                        claim.is_correct = True
                        claim.expected_result = str(value)
                        claim.actual_result = str(value)
                        return
                except (TypeError, ValueError):
                    pass

                # If we get here, it is genuinely incorrect.
                # Avoid calling `solve` since it can hang, just report the difference.
                claim.is_correct = False
                claim.expected_result = "Value satisfying the equation"
                claim.actual_result = str(value)
                claim.error_message = (
                    f"Substituting {var_name}={value} gives non-zero difference: {diff}"
                )
                return
            except Exception as e:
                logger.debug("solution_substitution_error", error=str(e))
                continue

        claim.is_correct = None
        claim.error_message = "Could not verify against any equation"

    # ------------------------------------------------------------------
    # LaTeX → SymPy parsing
    # ------------------------------------------------------------------
    def _parse_latex_expr(self, latex_expr: str):
        """
        Parse a LaTeX math expression into a SymPy expression (manual rules only).
        """
        # Clean the expression
        expr = latex_expr.strip()
        expr = expr.replace('\\,', '')
        expr = expr.replace('\\;', '')
        expr = expr.replace('\\!', '')

        # Manual parse only for reliability: parse_latex can hang without full antlr.
        manual = self._manual_parse(expr)
        return manual

    def _manual_parse(self, expr: str):
        """Manual fallback parser for common LaTeX math patterns."""
        s = expr

        # Convert caret superscript to ** early to simplify other replacements
        s = s.replace('^', '**')

        # Robust loop to handle nested structures, \frac, \sqrt, formatting macros, etc.
        while True:
            s_new = s

            # 1. Strip styling/formatting wrappers: \text{...}, \mathrm{...}, \mathbf{...}, etc.
            s_new = re.sub(
                r'\\(text|mathrm|mathbf|mathit|mathsf|mathtt|operatorname)\{([^{}]+)\}',
                r'\2',
                s_new,
            )

            # 2. Convert \frac{a}{b} -> ((a)/(b))
            s_new = re.sub(
                r'\\frac\{([^{}]+)\}\{([^{}]+)\}',
                r'((\1)/(\2))',
                s_new,
            )

            # 3. Convert \binom{n}{k} -> binomial(n, k)
            s_new = re.sub(
                r'\\binom\{([^{}]+)\}\{([^{}]+)\}',
                r'binomial(\1,\2)',
                s_new,
            )

            # 4. Convert \sqrt{x} -> sqrt(x)
            s_new = re.sub(
                r'\\sqrt\{([^{}]+)\}',
                r'sqrt(\1)',
                s_new,
            )

            # 5. Handle curly braces in exponents: **{x} -> **(x)
            s_new = re.sub(
                r'\*\*\{([^{}]+)\}',
                r'**(\1)',
                s_new,
            )

            # 6. Handle alphanumeric curly braces in subscripts: _{1} -> _1, _{ij} -> _ij
            s_new = re.sub(
                r'_\{([a-zA-Z0-9]+)\}',
                r'_\1',
                s_new,
            )

            # 7. Handle remaining complex curly braces in subscripts: _{expr} -> _(expr)
            s_new = re.sub(
                r'_\{([^{}]+)\}',
                r'_(\1)',
                s_new,
            )

            # If no replacements were made in this iteration, we break to avoid any infinite loop
            if s_new == s:
                break
            s = s_new

        # \cdot → *
        s = s.replace('\\cdot', '*')
        s = s.replace('\\times', '*')
        s = s.replace('\\div', '/')

        # Clean remaining LaTeX controls and symbols
        s = s.replace('\\left', '').replace('\\right', '')
        s = s.replace('\\', '')

        try:
            return sympify(s)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _cap_claims(self, claims: list[MathClaim]) -> list[MathClaim]:
        """Deduplicate and limit work — large documents produced 60+ false claims."""
        seen: set[str] = set()
        out: list[MathClaim] = []
        for claim in claims:
            key = claim.latex_expression.strip()
            if key in seen:
                continue
            seen.add(key)
            out.append(claim)
            if len(out) >= self._MAX_CLAIMS:
                break
        return out

    @staticmethod
    def _looks_like_computation(lhs: str, rhs: str) -> bool:
        """Skip labels, prose, and layout lines that are not arithmetic checks."""
        for side in (lhs, rhs):
            if re.search(r"\\(text|textbf|section|begin|end)\b", side):
                return False
            if "{" in side or "}" in side:
                return False
        combined = f"{lhs} {rhs}"
        if re.search(r"[+\-*/^]|\\frac|\\sqrt|\\cdot", combined):
            return True
        if re.search(r"\d", combined) and "=" in combined:
            return True
        return False

    @staticmethod
    def _is_valid_math_fragment(expr: str) -> bool:
        """Reject malformed LaTeX fragments (unbalanced braces, incomplete macros)."""
        depth = 0
        for ch in expr:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth < 0:
                    return False
        if depth != 0:
            return False
        if re.search(r"\\frac(?!\{)", expr):
            return False
        if re.search(r"\\(sqrt|binom|text|mathrm)\{[^}]*$", expr):
            return False
        return True

    @staticmethod
    def _is_definition(lhs: str, rhs: str) -> bool:
        """Check if this is a variable definition rather than a verifiable claim."""
        lhs = lhs.strip()
        rhs = rhs.strip()
        # Single variable = expression is usually a definition (e.g., f(x) = 2x+1)
        if re.match(r"^[a-zA-Z](\([a-zA-Z,\s]+\))?$", lhs):
            return True
        if re.match(r"^[a-zA-Z]$", lhs) and not re.search(r"\d|[+\-*/^]", rhs):
            return True
        return False

    @staticmethod
    def _context_claims_identity(context: str) -> bool:
        """Return True only when prose explicitly presents a symbolic identity."""
        normalized = context.lower()
        return any(
            marker in normalized
            for marker in (
                "identitet",
                "for alle",
                "uansett verdien",
                "alltid lik",
            )
        )


def format_errors_for_agent(result: VerificationResult) -> str:
    """Format verification errors into instructions for the author agent to fix."""
    if result.all_correct:
        return ""

    lines = [
        "=== MATEMATISKE FEIL FUNNET ===",
        f"SymPy fant {result.claims_incorrect} feil av {result.claims_checked} sjekket.\n",
    ]

    for i, err in enumerate(result.errors, 1):
        lines.append(f"FEIL {i}:")
        lines.append(f"  Uttrykk: {err.latex_expression}")
        lines.append(f"  Type: {err.claim_type}")
        if err.expected_result:
            lines.append(f"  Forventet: {err.expected_result}")
        if err.actual_result:
            lines.append(f"  Faktisk: {err.actual_result}")
        lines.append(f"  Detalj: {err.error_message}")
        lines.append(f"  Kontekst: ...{err.context}...")
        lines.append("")

    if result.unparseable_claims:
        lines.append(f"=== KUNNE IKKE VERIFISERE ({len(result.unparseable_claims)}) ===\n")
        for i, c in enumerate(result.unparseable_claims, 1):
            lines.append(f"UVISS {i}: {c.latex_expression}")
            if c.error_message:
                lines.append(f"  Merknad: {c.error_message}")
            lines.append("")

    lines.append("RETT ALLE FEILENE OVER og returner hele dokumentet med korreksjoner.")
    return "\n".join(lines)
