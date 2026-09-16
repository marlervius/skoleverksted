"""
SymPy-based mathematical verification engine.

Extracts mathematical claims from LaTeX and verifies them programmatically.
This is NOT an LLM — it is a symbolic computation engine that catches
arithmetic errors, incorrect solutions, and invalid equations.
"""

from __future__ import annotations

import re
import structlog
from sympy import Eq, Symbol, Lambda, S, FiniteSet, log, solveset, simplify, solve, sqrt, sympify, expand, cancel
from sympy.core.function import AppliedUndef
from app.models.state import MathClaim, VerificationResult
from m1.scorer import looks_like_prose, numeric_agreement
from app.verification.math_context import math_islands, context_ranges, local_context

logger = structlog.get_logger()

# Timeout for the entire verification pass (seconds)
_TOTAL_TIMEOUT = 90
# Max time per individual claim (seconds) — avoids SymPy simplify hangs
_CLAIM_TIMEOUT = 8

# Macros ``_manual_parse`` knows how to rewrite into SymPy input. A claim that
# only uses these is worth handing to the parser even when it contains braces;
# anything else stays out of the extraction so we do not manufacture claims the
# parser cannot represent.
_VERIFIABLE_MACROS = frozenset({
    "frac", "sqrt", "binom", "cdot", "times", "div", "left", "right",
    "mathrm", "mathbf", "mathit", "mathsf", "mathtt", "operatorname", "pi",
    "le", "leq", "ge", "geq",
    "lg", "log", "ln", "dfrac", "tfrac",
})


class MathChecker:
    """
    Extracts and verifies mathematical claims from LaTeX content.

    Supports:
    - Equation verification (LHS = RHS)
    - Solution verification (check that x=a satisfies the original equation)
    - Arithmetic computations (2 + 3 = 5)
    - Fraction/root simplification
    """

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
        self._function_definitions = {}
        self._scope_problem_cache = {}
        definitions_by_context = {}
        claims = self._extract_claims(latex_content)
        result = VerificationResult()
        result.claims_checked = len(claims)

        import time

        start_time = time.monotonic()

        for claim in claims:
            scope = claim.verification_context or latex_content
            if scope not in definitions_by_context:
                definitions_by_context[scope] = self._extract_function_definitions(scope)
            self._function_definitions = definitions_by_context[scope]
            # Check total timeout
            if time.monotonic() - start_time > _TOTAL_TIMEOUT:
                logger.warning("math_verification_total_timeout", checked_so_far=result.claims_correct + result.claims_incorrect + result.claims_unparseable)
                claim.error_message = "Verification time budget exhausted"
                result.claims_unparseable += 1
                result.unparseable_claims.append(claim)
                continue

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
    def _extract_function_definitions(self, content: str) -> dict:
        """Resolve only unambiguous, explicit single-variable definitions.

        Conflicting definitions remain unresolved rather than borrowing a
        function from another exercise. Reset on every document verification.
        """
        definitions = {}
        ambiguous = set()
        for island in math_islands(content):
            if "=" in island.text:
                lhs, rhs = island.text.split("=", 1)
                signature = re.fullmatch(r"([a-zA-Z](?:_\{?\w+\}?)?)\(([a-zA-Z])\)", lhs.strip())
                if not signature:
                    continue
                name, variable = signature.groups()
                try:
                    expression = self._manual_parse(rhs.strip())
                    symbol = Symbol(variable)
                    if (expression is None or not hasattr(expression, "free_symbols")
                            or expression.has(AppliedUndef)):
                        ambiguous.add(name)
                        continue
                    if expression.free_symbols - {symbol}:
                        # A template such as ax+b is not a competing numeric
                        # definition for a worked example's explicit 2x+1.
                        continue
                    definition = Lambda(symbol, expression)
                    if name in definitions and definitions[name] != definition:
                        ambiguous.add(name)
                    definitions[name] = definition
                except Exception:
                    ambiguous.add(name)
        return {name: value for name, value in definitions.items() if name not in ambiguous}

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

        ranges = context_ranges(content)
        for island in math_islands(content):
            if "=" in island.text:
                lhs_raw, rhs_raw = (part.strip() for part in island.text.split("=", 1))

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
                    context=content[max(0, island.start - 80):island.end + 80],
                    verification_context=local_context(content, island.start, ranges),
                )
                claims.append(claim)

        return claims

    def _extract_solution_claims(self, content: str) -> list[MathClaim]:
        """
        Extract exercise-solution pairs and verify solutions are correct.

        Looks for exercises with equations and matches them to solutions.
        """
        claims: list[MathClaim] = []

        ranges = context_ranges(content)
        for island in math_islands(content):
            answer = re.fullmatch(r"([a-z])\s*=\s*([^=]+)", island.text)
            if not answer:
                continue
            scope = local_context(content, island.start, ranges)
            # A definition such as u=2^x is not an asserted numeric solution.
            value = self._manual_parse(answer[2])
            if value is None or not hasattr(value, "free_symbols") or value.free_symbols:
                continue
            problems = self._scope_problems(scope, Symbol(answer[1]))
            if not problems:
                continue
            # An example or a section often solves several equations in the
            # same variable. Pair the answer with the equation it solves; the
            # first equation in scope is not evidence that it belongs there.
            equation = next((text for text, lhs, rhs, _ in problems
                             if self._satisfies(lhs, rhs, Symbol(answer[1]), value)), None)
            if equation is None and self._single_task_problem(scope, problems):
                equation = problems[0][0]  # Nothing else it could answer: a real error.
            if equation is None:
                continue  # Ambiguous; the equation claims still require a stated root.
            claims.append(MathClaim(
                latex_expression=island.text, claim_type="solution",
                context=f"equations={[equation]!r}", verification_context=scope,
            ))

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

        # Relations in a chain are separate claims, never arithmetic operands.
        normalized = re.sub(r"\\(?:leq|le)\b", "<=", expr_str)
        normalized = re.sub(r"\\(?:geq|ge)\b", ">=", normalized)
        relations = re.split(r"(<=|>=|=|<|>)", normalized)
        if any(op != "=" for op in relations[1::2]):
            unresolved = None
            for i in range(1, len(relations), 2):
                left, op, right = relations[i-1:i+2]
                if op == "=":
                    pair = MathClaim(latex_expression=f"{left} = {right}",
                                     claim_type="equation", context=claim.context,
                                     verification_context=claim.verification_context)
                    self._verify_equation(pair)
                    correct, error = pair.is_correct, pair.error_message
                else:
                    lhs, rhs = self._parse_latex_expr(left), self._parse_latex_expr(right)
                    correct, error = None, f"Unresolved relation: {left} {op} {right}"
                    if lhs is not None and rhs is not None:
                        relation = {"<": lambda: lhs < rhs, ">": lambda: lhs > rhs,
                                    "<=": lambda: lhs <= rhs, ">=": lambda: lhs >= rhs}[op]()
                        if relation == True:
                            correct, error = True, ""
                        elif relation == False:
                            correct, error = False, f"False relation: {left} {op} {right}"
                if correct is False:
                    claim.is_correct, claim.error_message = False, error
                    return
                if correct is None:
                    unresolved = error
            claim.is_correct = None if unresolved else True
            claim.error_message = unresolved or ""
            return

        # Check every adjacent equality in a calculation chain. Feeding the
        # entire RHS to the expression parser made ordinary worked solutions
        # such as 2*3+1=6+1=7 unparseable.
        chain = expr_str.split('=')
        if len(chain) > 2:
            unresolved = None
            for left, right in zip(chain, chain[1:]):
                pair = MathClaim(
                    latex_expression=f"{left.strip()} = {right.strip()}",
                    claim_type="equation", context=claim.context,
                    verification_context=claim.verification_context,
                )
                self._verify_equation(pair)
                if pair.is_correct is False:
                    claim.is_correct = False
                    claim.error_message = pair.error_message
                    return
                if pair.is_correct is None:
                    unresolved = pair.error_message
            claim.is_correct = None if unresolved else True
            claim.error_message = unresolved or ""
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

        if any(getattr(side, "has", lambda *_: False)(AppliedUndef) for side in (lhs, rhs)):
            claim.is_correct = None
            claim.error_message = "Function definition missing or ambiguous; provide an explicit definition"
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
                if (not self._context_claims_identity(claim.context)
                        and self._verify_equation_solution_set(claim, lhs, rhs)):
                    return
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

    def _verify_equation_solution_set(self, claim: MathClaim, lhs, rhs) -> bool:
        """Prove a condition against ALL stated real roots in its local scope.

        Substitution alone misses lost roots (x^2=4, x=2). Comparing finite
        solution sets also catches that error. A scope that solves several
        different equations in the same variable is ambiguous: an answer to one
        of them is never evidence that another was solved wrongly.
        """
        symbols = lhs.free_symbols | rhs.free_symbols
        if len(symbols) != 1:
            return False
        variable = next(iter(symbols))
        answers = []
        for island in math_islands(claim.verification_context):
            match = re.fullmatch(rf"{re.escape(str(variable))}\s*=\s*([^=]+)", island.text)
            if match:
                answer = self._parse_latex_expr(match[1])
                if answer is None or not hasattr(answer, "free_symbols") or answer.free_symbols:
                    return False
                answers.append(answer)
        if not answers:
            return False
        roots = self._real_roots(lhs, rhs, variable)
        if roots is None:
            return False
        problems = self._scope_problems(claim.verification_context, variable)
        single_problem = all(self._same_roots(found, roots) for _, _, _, found in problems)
        missing = [root for root in roots if not any(self._same_value(root, a) for a in answers)]
        extra = [a for a in answers if not any(self._same_value(a, root) for root in roots)]
        if missing and not single_problem:
            return False  # The stated answers may all belong to other equations.
        # Every stated answer in an exercise answers that exercise; elsewhere an
        # extra value may be a different quantity (a price, a time, a count).
        same = not missing and not (extra and self._single_task_problem(claim.verification_context, problems))
        claim.is_correct = same
        claim.expected_result = str(roots)
        claim.actual_result = str(FiniteSet(*answers))
        claim.error_message = "" if same else "Stated solutions do not match the complete real solution set"
        return True

    def _scope_problems(self, scope: str, variable) -> list[tuple]:
        """Equations in ``variable`` within a scope, with their real roots.

        Roots are None when they cannot be determined exactly.
        """
        cache = getattr(self, "_scope_problem_cache", None)
        if cache is None:
            cache = self._scope_problem_cache = {}
        key = (scope, str(variable))
        if key not in cache:
            problems = []
            for equation in math_islands(scope):
                if equation.text.count("=") != 1:
                    continue
                left, right = equation.text.split("=")
                if self._is_definition(left, right):
                    continue
                lhs, rhs = self._manual_parse(left), self._manual_parse(right)
                if lhs is None or rhs is None:
                    continue
                symbols = getattr(lhs, "free_symbols", set()) | getattr(rhs, "free_symbols", set())
                if variable not in symbols:
                    continue
                roots = self._real_roots(lhs, rhs, variable) if symbols == {variable} else None
                problems.append((equation.text, lhs, rhs, roots))
            cache[key] = problems
        return cache[key]

    @staticmethod
    def _single_task_problem(scope: str, problems: list[tuple]) -> bool:
        """An exercise scope whose equations all have the same solutions."""
        if not problems or not scope.lstrip().startswith(r"\begin{taskbox}"):
            return False
        first = problems[0][3]
        return all(MathChecker._same_roots(found, first) for _, _, _, found in problems)

    @staticmethod
    def _real_roots(lhs, rhs, variable):
        try:
            roots = solveset(lhs - rhs, variable, domain=S.Reals)
        except Exception:
            return None
        return roots if isinstance(roots, FiniteSet) else None

    @staticmethod
    def _same_value(a, b) -> bool:
        try:
            difference = simplify(a - b)
            if difference == 0:
                return True
            # Decimal fasit values such as 16,8 are floats; 84/5 - 16.8 is ~1e-15.
            return abs(complex(difference.evalf())) < 1e-9
        except Exception:
            return False

    @staticmethod
    def _same_roots(a, b) -> bool:
        return (a is not None and b is not None and len(a) == len(b)
                and all(any(MathChecker._same_value(x, y) for y in b) for x in a))

    @staticmethod
    def _satisfies(lhs, rhs, variable, value) -> bool:
        try:
            return MathChecker._same_value((lhs - rhs).subs(variable, value), 0)
        except Exception:
            return False

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

            sides = list(lhs) if isinstance(lhs, (list, tuple)) else [lhs]
            sides += list(rhs) if isinstance(rhs, (list, tuple)) else [rhs]
            if not any(var in getattr(side, "free_symbols", set()) for side in sides):
                # An auxiliary substitution (u=2^x) is not a solution for an
                # equation in x. It cannot establish a mathematical error.
                claim.is_correct = None
                claim.error_message = "Solution variable is absent from the original equation; auxiliary substitution requires review"
                return

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
        if manual is not None and hasattr(manual, "atoms"):
            for call in manual.atoms(AppliedUndef):
                definition = getattr(self, "_function_definitions", {}).get(str(call.func))
                if definition is not None and len(call.args) == 1:
                    manual = manual.subs(call, definition(*call.args))
        return manual

    def _manual_parse(self, expr: str):
        """Manual fallback parser for common LaTeX math patterns."""
        s = re.sub(r"(?<=\d)\{,\}(?=\d)", ".", expr)
        s = s.replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac")
        s = re.sub(r"\\(lg|log|ln)\s+(\d+(?:\.\d+)?|[a-z])\b", r"\\\1(\2)", s)
        s = s.replace(r"\,", "").replace(r"\;", "").replace(r"\!", "")
        s = re.sub(r"(\d+(?:\.\d+)?)\\%", r"(\1/100)", s)

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
        # School notation commonly omits multiplication in 2x and 3(x+1).
        s = re.sub(r"(?<=\d)(?=[a-df-zA-DF-Z(]|[eE](?![+-]?\d))", "*", s)
        s = re.sub(r"\)(?=\()", ")*", s)
        s = re.sub(r"\b([abcd])([xyz])\b", r"\1*\2", s)
        s = re.sub(r"\b([abcd])\s*\(", r"\1*(", s)

        try:
            return sympify(s, locals={"lg": lambda value: log(value, 10),
                                      "log": lambda value: log(value, 10), "ln": log})
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _cap_claims(self, claims: list[MathClaim]) -> list[MathClaim]:
        """Deduplicate within a scope; the time budget bounds verification.

        Never silently discard the latter part of a chapter or an identical
        answer belonging to a different exercise.
        """
        seen: set[tuple[str, str]] = set()
        out: list[MathClaim] = []
        for claim in claims:
            key = (claim.latex_expression.strip(), claim.verification_context)
            if key in seen:
                continue
            seen.add(key)
            out.append(claim)
        return out

    @staticmethod
    def _looks_like_computation(lhs: str, rhs: str) -> bool:
        """Skip labels, prose, and layout lines that are not arithmetic checks."""
        for side in (lhs, rhs):
            if re.search(r"\\(text|textbf|section|begin|end)\b", side):
                return False
            # Braces are normal in real mathematics (\frac{1}{2}, x^{2}, a_{i}).
            # Only skip the side when it uses a macro we have no reason to
            # believe SymPy can read — an unverified claim must never be
            # silently dropped when it is verifiable (grunnlov §1).
            unknown_macros = [
                macro for macro in re.findall(r"\\([a-zA-Z]+)", side)
                if macro not in _VERIFIABLE_MACROS
            ]
            if unknown_macros:
                return False
        combined = f"{lhs} {rhs}"
        if re.search(r"[+\-*/^]|\\frac|\\sqrt|\\cdot", combined):
            return True
        if re.search(r"\d", combined):
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


def format_errors_for_agent(result: VerificationResult, *, max_claims: int | None = None) -> str:
    """Format verification errors into instructions for the author agent to fix."""
    if result.all_correct and not result.claims_unparseable:
        return ""

    lines = [
        "=== MATEMATISKE FEIL FUNNET ===",
        f"SymPy fant {result.claims_incorrect} feil av {result.claims_checked} sjekket.\n",
    ]

    errors = result.errors if max_claims is None else result.errors[:max_claims]
    remaining = None if max_claims is None else max(0, max_claims - len(errors))
    uncertain = (result.unparseable_claims if remaining is None
                 else result.unparseable_claims[:remaining])
    for i, err in enumerate(errors, 1):
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
        for i, c in enumerate(uncertain, 1):
            lines.append(f"UVISS {i}: {c.latex_expression}")
            if c.error_message:
                lines.append(f"  Merknad: {c.error_message}")
            lines.append(f"  Kontekst: ...{c.context}...")
            if c.verification_context and len(c.verification_context) <= 4000:
                lines.append(f"  Oppgave/eksempel: {c.verification_context}")
            lines.append("")

    omitted = len(result.errors) + len(result.unparseable_claims) - len(errors) - len(uncertain)
    if omitted:
        lines.append(f"{omitted} øvrige uttrykk kontrolleres i senere reparasjonsrunder. "
                     "Prioriter uttrykkene ovenfor i dette svaret.")
    lines.append("RETT FEILENE OVER. Følg svarformatet i reparasjonsinstruksjonen.")
    return "\n".join(lines)
