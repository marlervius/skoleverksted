"""
SymPy-based mathematical verification engine.

Extracts mathematical claims from LaTeX and verifies them programmatically.
This is NOT an LLM — it is a symbolic computation engine that catches
arithmetic errors, incorrect solutions, and invalid equations.
"""

from __future__ import annotations

import random
import threading
import re
import structlog
from sympy import E, Eq, Symbol, Lambda, Rational, S, FiniteSet, diff, log, solveset, simplify, solve, sqrt, sympify, expand, cancel
from sympy.core.function import AppliedUndef
from app.models.state import MathClaim, VerificationResult
from m1.scorer import looks_like_prose, numeric_agreement
from app.verification.math_context import math_islands, context_ranges, local_context

logger = structlog.get_logger()

# Timeout for the entire verification pass (seconds)
_TOTAL_TIMEOUT = 90
# Max time per individual claim (seconds) — avoids SymPy simplify hangs
_CLAIM_TIMEOUT = 8
# A claim still running after this is abandoned and stays unverified.
_CLAIM_HARD_TIMEOUT = 30

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


# Names that the product and quotient rules conventionally define without an
# argument: u = x^2, v = e^x.
_BARE_FUNCTIONS = frozenset({"u", "v", "w"})

# Marks a derivative that has no formula in scope: a rule such as
# (uv)' = u'v + uv', or implicit differentiation with y'. Never evaluated.
_DERIVATIVE_MARKER = re.compile(r"_dI+$")


def _matching(text: str, start: int) -> int:
    """Index of the bracket closing the one at `start`, or -1."""
    depth = 0
    for index in range(start, len(text)):
        if text[index] in "([":
            depth += 1
        elif text[index] in ")]":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _opening(text: str, end: int) -> int:
    """Index of the bracket opening the one closing at `end`, or -1."""
    depth = 0
    for index in range(end, -1, -1):
        if text[index] in ")]":
            depth += 1
        elif text[index] in "([":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _rewrite_derivatives(s: str) -> str:
    """Turn derivative notation into calls SymPy can evaluate or mark.

    d/dx[...] becomes DIFF(...), (expr)' becomes PRIME(expr), f'(x) becomes
    the function f_dI(x) and a bare u' the symbol u_dI (no digit, which the
    parser would read as a factor). The checker resolves f_dI and u_dI from
    the definitions in scope and otherwise treats the line as a rule, never
    as a false statement.
    """
    operator = re.compile(r"\(\(d\)/\(d([a-z])\)\)\s*\*?\s*(?=[(\[])")
    while (match := operator.search(s)) is not None:
        close = _matching(s, match.end())
        if close < 0:
            break
        inner = s[match.end() + 1:close]
        s = f"{s[:match.start()]}DIFF(({inner}),{match[1]}){s[close + 1:]}"
    while (index := s.find(")'")) >= 0:
        open_ = _opening(s, index)
        if open_ < 0:
            break
        s = f"{s[:open_]}PRIME({s[open_:index + 1]}){s[index + 2:]}"
    # f'(x) is a call; a bare u' is closed in parentheses so that u'v and
    # uv' read as products.
    s = re.sub(r"([A-Za-z](?:_[A-Za-z\d]+)?)('+)(?=\()",
               lambda m: f"{m[1]}_d{'I' * len(m[2])}", s)
    s = re.sub(r"([A-Za-z](?:_[A-Za-z\d]+)?)('+)",
               lambda m: f"({m[1]}_d{'I' * len(m[2])})", s)
    return s


def _derivative(expression, variable):
    others = getattr(expression, "free_symbols", set()) - {variable}
    if others:
        return Symbol("implicit_dI")
    return diff(expression, variable)


def _prime(expression):
    symbols = getattr(expression, "free_symbols", set())
    if len(symbols) != 1:
        return Symbol("rule_dI")
    return diff(expression, next(iter(symbols)))


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
        The whole pass is bounded by ``_TOTAL_TIMEOUT``. Each claim runs in its
        own worker thread with a generous hard limit, ``_CLAIM_HARD_TIMEOUT``;
        a claim that exceeds it is abandoned and stays unverified.
        """
        self._function_definitions = {}
        self._scope_problem_cache = {}
        definitions_by_context = {}
        claims = self._extract_claims(latex_content)
        result = VerificationResult()
        result.claims_checked = len(claims)

        import time

        start_time = time.monotonic()
        # A worked example often evaluates a function defined earlier in the
        # chapter. A definition that is unambiguous document-wide may be used;
        # a local definition always takes precedence.
        document_definitions = self._extract_function_definitions(latex_content)
        self._definition_candidates = self._collect_definition_candidates(latex_content)

        for claim in claims:
            scope = claim.verification_context or latex_content
            if scope not in definitions_by_context:
                definitions_by_context[scope] = {
                    **document_definitions, **self._extract_function_definitions(scope)}
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
                if not self._verify_within_hard_limit(claim):
                    claim.is_correct = None
                    claim.error_message = "Claim verification timed out"
                    logger.warning("claim_verification_abandoned",
                                   claim=claim.latex_expression[:80], seconds=_CLAIM_HARD_TIMEOUT)
                elif time.monotonic() - claim_start > _CLAIM_TIMEOUT:
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

            if not claim.assertion and claim.is_correct is None:
                result.claims_checked -= 1
            elif claim.is_correct is True:
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

    def _verify_within_hard_limit(self, claim: MathClaim) -> bool:
        """Verify a copy of the claim; give up on it after a hard deadline.

        A SymPy call cannot be interrupted, and one pathological expression
        once held a whole release check for twenty minutes. The worker is
        abandoned instead: the claim stays unverified (never approved), and
        its late result can no longer change this verification.
        """
        work = claim.model_copy()
        done = threading.Event()

        def run() -> None:
            try:
                self._verify_claim(work)
            finally:
                done.set()

        threading.Thread(target=run, name="math-claim", daemon=True).start()
        if not done.wait(_CLAIM_HARD_TIMEOUT):
            return False
        for field in type(claim).model_fields:
            setattr(claim, field, getattr(work, field))
        return True

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
        for name, symbol, expression in self._definitions_in(content):
            if expression is None:
                ambiguous.add(name)
                continue
            definition = Lambda(symbol, expression)
            if name in definitions and definitions[name] != definition:
                ambiguous.add(name)
            definitions[name] = definition
        return {name: value for name, value in definitions.items() if name not in ambiguous}

    def _definitions_in(self, content: str):
        """Yield (name, variable, expression) for explicit function definitions.

        One display may hold several definitions and a domain:
        S_A(t) = 400t + 1200 \\quad og \\quad S_B(t) = ..., or
        h(t) = -5t^2 + 20t + 2, \\quad t \\ge 0. The expression is None when
        it cannot be read. A template (ax + b) and an equation to solve
        (f(x) = 0) are not definitions of a particular function.
        """
        separator = r"\\q?quad|\\text\{[^}]*\}|;|,\s*(?=\\q?quad|[a-zA-Z](?:_\{?\w+\}?)?\()"
        for island in math_islands(content):
            for segment in re.split(separator, island.text):
                if segment.count("=") != 1:
                    continue
                lhs, rhs = segment.split("=")
                if lhs.strip() in _BARE_FUNCTIONS and rhs.strip():
                    # u = x^2 in a product-rule solution: a function of its
                    # single variable. Anything else is not a definition.
                    try:
                        expression = self._manual_parse(rhs.strip().rstrip(","))
                    except Exception:
                        expression = None
                    symbols = getattr(expression, "free_symbols", set())
                    if (len(symbols) == 1 and str(next(iter(symbols))) != lhs.strip()
                            and not expression.has(AppliedUndef)):
                        yield lhs.strip(), next(iter(symbols)), expression
                    continue
                signature = re.fullmatch(r"([a-zA-Z](?:_\{?\w+\}?)?)\(([a-zA-Z])\)", lhs.strip())
                if not signature or not rhs.strip().rstrip(","):
                    continue
                name = re.sub(r"_\{(\w+)\}", r"_\1", signature[1])
                symbol = Symbol(signature[2])
                try:
                    expression = self._manual_parse(rhs.strip().rstrip(","))
                except Exception:
                    expression = None
                if (expression is None or not hasattr(expression, "free_symbols")
                        or expression.has(AppliedUndef)):
                    yield name, symbol, None
                elif expression.free_symbols == {symbol}:
                    yield name, symbol, expression

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

                # Skip trivial definitions (x = ...) with no computation, but
                # keep the arithmetic in an answer chain: x = 4510/820 = 5,5.
                if self._is_definition(lhs_raw, rhs_raw):
                    if "=" not in rhs_raw:
                        continue
                    lhs_raw, rhs_raw = (part.strip() for part in rhs_raw.split("=", 1))
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
        islands = math_islands(content)
        for index, island in enumerate(islands):
            answer = self._ANSWER.fullmatch(island.text)
            if not answer:
                continue
            scope = local_context(content, island.start, ranges)
            # A definition such as u=2^x is not an asserted numeric solution.
            stated = self._answer_value(answer["value"], approximate=answer["relation"] != "=")
            if stated is None:
                continue
            value, tolerance = stated
            variable = Symbol(answer["name"])
            problems = self._scope_problems(scope, variable)
            if not problems:
                continue
            # An example or a section often solves several equations in the
            # same variable. Pair the answer with the equation it solves; the
            # first equation in scope is not evidence that it belongs there.
            if not tolerance:
                equation = next((text for text, lhs, rhs, _ in problems
                                 if self._satisfies(lhs, rhs, variable, value)), None)
                if equation is not None:
                    claims.append(MathClaim(
                        latex_expression=island.text, claim_type="solution",
                        context=f"equations={[equation]!r}", verification_context=scope,
                    ))
                    continue
            else:
                equation = next((text for text, _, _, roots in problems if roots and any(
                    self._same_value(root, value, tolerance) for root in roots)), None)
                if equation is not None:
                    claims.append(MathClaim(
                        latex_expression=island.text, claim_type="approximate_solution",
                        context=f"equations={[equation]!r}", verification_context=scope,
                    ))
                    continue
            # The value solves nothing here. It is only suspicious as the end
            # of a derivation of an equation left without any stated solution;
            # a substituted value, a symmetry line x = 2 or a value elsewhere in
            # a list of exercises is not an answer to it.
            if self._introduces_value(content, island.start):
                continue
            answers = self._stated_answers(scope, variable)
            unanswered = {text for text, _, _, roots in problems
                          if roots and not any(self._same_value(root, a, tol)
                                               for root in roots for a, tol in answers)}
            derived_from = self._derivation_start(content, islands, index, unanswered)
            if derived_from is not None:
                # The value concludes the derivation of this very equation,
                # which has no correct solution stated: a wrong answer.
                claims.append(MathClaim(
                    latex_expression=island.text, claim_type="solution",
                    context=f"equations={[derived_from]!r}", verification_context=scope,
                ))

        return claims

    @staticmethod
    def _derivation_start(content: str, islands, index: int, equations: set[str]) -> str | None:
        """The equation this value concludes, within one uninterrupted derivation."""
        answer = islands[index]
        for previous in reversed(islands[:index]):
            gap = content[previous.end:answer.start]
            if (answer.start - previous.end > 600
                    or re.search(r"\n\s*\n|\\item\b|\\textbf\{|\\(?:sub)*section|\\end\{(?:enumerate|itemize|oppgaver)\}", gap)):
                return None
            if previous.text in equations:
                return previous.text
        return None

    _ANSWER = re.compile(r"(?P<name>[a-z])(?:_\{?\w+\}?)?\s*(?P<relation>=|\\approx)\s*(?P<value>.+)", re.S)

    def _stated_answers(self, scope: str, variable) -> list[tuple]:
        """Constant values stated for ``variable`` (or x_1, x_2) in a scope.

        The last link of a chain is the answer: x = 4510/820 = 5,5. A value
        written with \\approx carries the tolerance of its printed decimals.
        """
        answers = []
        for island in math_islands(scope):
            match = self._ANSWER.fullmatch(island.text)
            if match and match["name"] == str(variable):
                answer = self._answer_value(match["value"], approximate=match["relation"] != "=")
                if answer is not None:
                    answers.append(answer)
        return answers

    def _answer_value(self, text: str, *, approximate: bool = False):
        """The value of a stated answer and its tolerance.

        x = 4510/820 = 5,5 and t = lg(25/6)/lg 1,25 ≈ 6,4 år: the first exact
        constant wins; a value that only appears after ≈ carries the tolerance
        of its printed decimals. Units in \\text{...} are not part of the value.
        """
        text = re.sub(r"\\text\{[^}]*\}", "", text)
        parts = re.split(r"(=|\\approx)", text)
        relation = r"\approx" if approximate else "="
        for index in range(0, len(parts), 2):
            if index:
                relation = parts[index - 1]
            candidate = parts[index].strip()
            if not candidate:
                continue
            value = self._parse_latex_expr(candidate)
            if value is None or not hasattr(value, "free_symbols") or value.free_symbols:
                continue
            decimals = re.search(r"\d(?:\{,\}|[.,])(\d+)\s*$", candidate)
            if relation == r"\approx":
                return value, 0.5 * 10 ** -len(decimals[1]) if decimals else 0.5
            return value, 0
        return None

    @staticmethod
    def _introduces_value(content: str, position: int) -> bool:
        before = content[max(0, position - 60):position].lower()
        return bool(re.search(r"sett(?:er)?(?: vi)? inn|innsatt|substituer|velger|når\s*$|for\s*$", before))

    @staticmethod
    def _domain_restricted(scope: str) -> bool:
        """The text rejects roots for a reason: a length, a time, a growth factor."""
        return bool(re.search(
            r"forkast|ikke (?:gi )?mening|ingen mening|kan ikke være negativ|må være positiv|"
            r"gyldig|definisjonsmengde|D_|\\ge(?:q)?\s*0|>\s*0|positiv|lengde|tid\b|antall|vekstfaktor",
            scope, re.I))

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
            elif claim.claim_type == "approximate_solution":
                # Extraction compared the value with the exact root to the
                # precision of its printed decimals.
                claim.is_correct = True
                claim.error_message = ""
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
            asserted = False
            for i in range(1, len(relations), 2):
                left, op, right = relations[i-1:i+2]
                if op == "=":
                    pair = MathClaim(latex_expression=f"{left} = {right}",
                                     claim_type="equation", context=claim.context,
                                     verification_context=claim.verification_context)
                    self._verify_equation(pair)
                    if not pair.assertion and pair.is_correct is None:
                        continue
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
                        elif getattr(lhs, "free_symbols", None) or getattr(rhs, "free_symbols", None):
                            continue  # A condition such as a < 0 or x > 2, not a statement.
                asserted = True
                if correct is False:
                    claim.is_correct, claim.error_message = False, error
                    return
                if correct is None:
                    unresolved = error
            if not asserted:
                self._not_an_assertion(claim, "Relation with unknowns is a condition, not a statement")
                return
            claim.is_correct = None if unresolved else True
            claim.error_message = unresolved or ""
            return

        # Check every adjacent equality in a calculation chain. Feeding the
        # entire RHS to the expression parser made ordinary worked solutions
        # such as 2*3+1=6+1=7 unparseable.
        chain = expr_str.split('=')
        if len(chain) > 2:
            unresolved = None
            asserted = False
            for left, right in zip(chain, chain[1:]):
                pair = MathClaim(
                    latex_expression=f"{left.strip()} = {right.strip()}",
                    claim_type="equation", context=claim.context,
                    verification_context=claim.verification_context,
                )
                self._verify_equation(pair)
                if not pair.assertion and pair.is_correct is None:
                    continue  # e.g. x = 4510/820 in x = 4510/820 = 5,5
                asserted = True
                if pair.is_correct is False:
                    claim.is_correct = False
                    claim.error_message = pair.error_message
                    return
                if pair.is_correct is None:
                    unresolved = pair.error_message
            if not asserted:
                self._not_an_assertion(claim, "Chain of conditions or definitions, no checkable statement")
                return
            claim.is_correct = None if unresolved else True
            claim.error_message = unresolved or ""
            return

        parts = expr_str.split('=', 1)
        lhs_latex = parts[0].strip()
        rhs_latex = parts[1].strip()
        if not lhs_latex or not rhs_latex:
            self._not_an_assertion(claim, "One side is empty; layout fragment, not a statement")
            return
        if self._is_definition(lhs_latex, rhs_latex):
            self._not_an_assertion(claim, "Definition or stated answer; checked against its equation")
            return

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

        if any(_DERIVATIVE_MARKER.search(str(symbol)) for side in (lhs, rhs)
               for symbol in getattr(side, "free_symbols", ())):
            # (uv)' = u'v + uv' or 2x + 2y y' = 0: a rule or implicit
            # differentiation with no formula to differentiate.
            self._not_an_assertion(claim, "Derivative rule without a formula in this exercise")
            return

        undefined = [call for side in (lhs, rhs) if hasattr(side, "atoms")
                     for call in side.atoms(AppliedUndef)]
        if undefined:
            if any(arg.free_symbols for call in undefined for arg in call.args):
                # f(-b/(2a)) or f(x) = ... describes, it does not evaluate.
                self._not_an_assertion(claim, "Symbolic function expression, not an evaluation")
            elif self._matches_a_chapter_definition(lhs, rhs, undefined):
                claim.is_correct = True
                claim.error_message = "Evaluation matches a definition of this function in the chapter"
            elif not any(str(call.func) in getattr(self, "_definition_candidates", {}) for call in undefined):
                # S_A(3) for a model described only in words: there is no
                # formula to evaluate. Its arithmetic is checked on its own.
                self._not_an_assertion(claim, "Function described in words; no formula to evaluate")
            else:
                claim.is_correct = None
                claim.error_message = "Function definition missing or ambiguous; provide an explicit definition"
            return

        if looks_like_prose(lhs, rhs) or isinstance(lhs, (list, tuple)) != isinstance(rhs, (list, tuple)):
            self._not_an_assertion(claim, "Notation such as an interval or a point, not a statement")
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

                    if getattr(diff, "free_symbols", None):
                        # (x_1, y_1) = (1, 3) names a point; it asserts nothing.
                        self._not_an_assertion(claim, "Named coordinates, not a statement")
                        return
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
                # A rule box also states formulas such as y - y_1 = a(x - x_1);
                # its identities are caught as rewrites with the same unknowns.
                # f'(x) = 2x e^x states a derivative for every x; f'(x) = 0,
                # with a constant side, is an equation to solve.
                states_derivative = bool(
                    re.search(r"'|\\frac\{d\}\{d[a-z]\}", expr_str)
                    and getattr(lhs, "free_symbols", None) and getattr(rhs, "free_symbols", None))
                identity = states_derivative or self._context_claims_identity(claim.context)
                if not identity and self._verify_equation_solution_set(claim, lhs, rhs):
                    return
                symbols = lhs.free_symbols | rhs.free_symbols
                num = numeric_agreement(lhs, rhs, symbols)
                if num is not True:
                    # Logarithm and root rules hold on their school domain, the
                    # positive numbers; random negative samples say nothing.
                    positive = self._positive_agreement(lhs, rhs, symbols)
                    num = True if positive is True else (positive if num is None else num)
                if num is True:
                    claim.is_correct = True
                    claim.expected_result = str(rhs)
                    claim.actual_result = str(lhs)
                    return
                if identity:
                    claim.is_correct = False if num is False else None
                    claim.error_message = (
                        f"LHS ({lhs}) ≠ RHS ({rhs}) for generic values (identity check)"
                        if num is False else "Identity could not be evaluated")
                    return
                if (getattr(lhs, "free_symbols", set()) == getattr(rhs, "free_symbols", set())
                        and not getattr(lhs, "is_Symbol", False)
                        and not self._has_finite_real_roots(lhs, rhs)):
                    # Both sides use the same unknowns and the equation is not
                    # something to solve: it presents a rewrite, e.g.
                    # (a+b)^2 = a^2 + b^2. A rewrite that fails is not proven.
                    claim.is_correct = None
                    claim.error_message = "Rewrite could not be confirmed for general values"
                    return
                # An equation to solve (2^x = 10), a formula (x^2 + y^2 = r^2)
                # or a substitution into one states nothing by itself. Its
                # stated solutions are checked as solution claims.
                self._not_an_assertion(claim, "Equation to solve or formula, not a statement")
                return

            rounding = self._rounded_value_tolerance(expr_str)
            try:
                if rounding and abs(complex(diff.evalf())) <= rounding * max(
                        abs(complex(lhs.evalf())), abs(complex(rhs.evalf()))):
                    claim.is_correct = True
                    claim.expected_result = str(rhs)
                    claim.actual_result = str(lhs)
                    claim.error_message = "Correct to the precision of the rounded decimal"
                    return
            except (TypeError, ValueError):
                pass

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
        scope = claim.verification_context
        answers = self._stated_answers(scope, variable)
        if not answers:
            return False
        roots = self._real_roots(lhs, rhs, variable)
        if not roots:
            return False
        stated = [root for root in roots if any(self._same_value(root, a, tol) for a, tol in answers)]
        exercise = self._single_task_problem(scope, self._scope_problems(scope, variable))
        if not stated and not exercise:
            # The values may answer other equations or be other quantities. A
            # value that answers nothing here is reported as an unmatched answer.
            return False
        # A root may be rejected for a reason (a length, a growth factor b > 0).
        # Only a plain exercise that omits a root without saying why is wrong.
        same = bool(stated) and not (
            exercise and len(stated) < len(roots) and not self._domain_restricted(scope))
        claim.is_correct = same
        claim.expected_result = str(roots)
        claim.actual_result = str(FiniteSet(*(a for a, _ in answers)))
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
    def _same_value(a, b, tolerance: float = 0) -> bool:
        try:
            difference = simplify(a - b)
            if difference == 0:
                return True
            # Decimal fasit values such as 16,8 are floats; 84/5 - 16.8 is ~1e-15.
            # A value printed as x ≈ 1,77 carries the tolerance of its decimals.
            return abs(complex(difference.evalf())) <= max(1e-9, tolerance * 1.0001)
        except Exception:
            return False

    def _matches_a_chapter_definition(self, lhs, rhs, calls) -> bool:
        """An evaluation such as V(0) = 400 - 50·0 when V has several models.

        A chapter may reuse V(t) for different models. The evaluation is
        proven when it holds for one of the chapter's explicit definitions.
        """
        from itertools import product

        candidates = getattr(self, "_definition_candidates", {})
        names = sorted({str(call.func) for call in calls})
        if not names or any(name not in candidates for name in names):
            return False
        for choice in list(product(*(candidates[name] for name in names)))[:16]:
            chosen = dict(zip(names, choice))
            values = {call: chosen[str(call.func)](*call.args) for call in calls if len(call.args) == 1}
            if len(values) != len(calls):
                return False
            try:
                if self._same_value(lhs.subs(values), rhs.subs(values)):
                    return True
            except Exception:
                continue
        return False

    def _collect_definition_candidates(self, content: str) -> dict:
        """Every explicit single-variable definition per function name."""
        candidates: dict[str, list] = {}
        for name, symbol, expression in self._definitions_in(content):
            if expression is None:
                continue
            definition = Lambda(symbol, expression)
            if definition not in candidates.setdefault(name, []):
                candidates[name].append(definition)
        return candidates

    @staticmethod
    def _not_an_assertion(claim: MathClaim, reason: str) -> None:
        claim.assertion = False
        claim.is_correct = None
        claim.error_message = reason

    @staticmethod
    def _positive_agreement(lhs, rhs, symbols):
        """Numeric agreement on positive values, the domain of lg and roots."""
        rng = random.Random(20260917)
        agree = disagree = 0
        for _ in range(12):
            values = {s: Rational(rng.randint(1, 60), rng.randint(1, 9)) for s in symbols}
            try:
                a = complex(lhs.subs(values).evalf())
                b = complex(rhs.subs(values).evalf())
            except Exception:
                continue
            if any(v != v or abs(v) == float("inf") or abs(v.imag) > 1e-12 for v in (a, b)):
                continue
            if abs(a - b) <= 1e-9 * (1 + abs(a)):
                agree += 1
            else:
                disagree += 1
        if agree >= 3 and not disagree:
            return True
        if disagree and not agree:
            return False
        return None

    @staticmethod
    def _has_finite_real_roots(lhs, rhs) -> bool:
        symbols = getattr(lhs, "free_symbols", set()) | getattr(rhs, "free_symbols", set())
        if len(symbols) != 1:
            return False
        return bool(MathChecker._real_roots(lhs, rhs, next(iter(symbols))))

    @staticmethod
    def _rounded_value_tolerance(latex: str) -> float:
        """Relative tolerance of the most precise rounded decimal in a claim.

        450 000 · 0,88^5 = 450 000 · 0,52773 is correct to the five decimals
        printed. The strictest literal decides, so an exact input such as 0,88
        never excuses a wrong result.
        """
        tolerances = []
        for whole, fraction in re.findall(r"(\d+)(?:\{,\}|[.,])(\d+)", latex):
            value = float(f"{whole}.{fraction}")
            if value:
                tolerances.append(0.5 * 10 ** -len(fraction) / value)
        return min(tolerances) * 1.01 if tolerances else 0.0

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
        sol_match = self._ANSWER.fullmatch(claim.latex_expression.strip())
        if not sol_match:
            claim.is_correct = None
            claim.error_message = "Could not parse solution format"
            return

        var_name = sol_match["name"]
        value_str = sol_match["value"]
        stated = self._answer_value(value_str)  # x = 4510/820 = 5,5
        if stated is None:
            claim.is_correct = None
            claim.error_message = f"Could not parse solution value: {value_str}"
            return
        value = stated[0]

        # Try to find and parse the original equation from context. The list
        # is a Python repr: decode it, or \lg arrives as \\lg and cannot parse.
        try:
            import ast
            eq_strs = [str(text) for text in ast.literal_eval(claim.context.removeprefix("equations="))]
        except (ValueError, SyntaxError):
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
            definitions = getattr(self, "_function_definitions", {})
            for call in manual.atoms(AppliedUndef):
                name, order = self._derivative_name(str(call.func))
                definition = definitions.get(name)
                if definition is not None and len(call.args) == 1 and (order or name not in _BARE_FUNCTIONS):
                    manual = manual.subs(call, self._differentiated(definition, order)(*call.args))
            # u' and u in a product-rule line refer to u = ... in the same
            # exercise. Plain u is only replaced where a derivative is taken,
            # so a substitution u = 3^x in an exponential equation is untouched.
            if "'" in latex_expr or re.search(r"\\frac\{d\}\{d[a-z]\}", latex_expr):
                for symbol in list(manual.free_symbols):
                    name, order = self._derivative_name(str(symbol))
                    definition = definitions.get(name)
                    if definition is not None and (order or name in _BARE_FUNCTIONS):
                        manual = manual.subs(symbol, self._differentiated(definition, order).expr)
        return manual

    @staticmethod
    def _derivative_name(name: str) -> tuple[str, int]:
        match = re.fullmatch(r"(.+)_d(I+)", name)
        return (match[1], len(match[2])) if match else (name, 0)

    @staticmethod
    def _differentiated(definition, order: int):
        variable = definition.variables[0]
        return Lambda(variable, diff(definition.expr, variable, order) if order else definition.expr)

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

            # 4. Convert \sqrt[n]{x} -> ((x)**(1/(n))) and \sqrt{x} -> sqrt(x)
            s_new = re.sub(
                r'\\sqrt\[([^\[\]{}]+)\]\{([^{}]+)\}',
                r'((\2)**(1/(\1)))',
                s_new,
            )
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
        # 3\lg(x), (3+5-2)\lg(x) and x \lg 5 multiply by the logarithm.
        s = re.sub(r"(?<=[\w)}.])\s*\\(lg|ln|log)\b", r"*\\\1", s)
        s = s.replace('\\', '')
        s = _rewrite_derivatives(s)
        # School notation commonly omits multiplication in 2x and 3(x+1).
        s = re.sub(r"(?<=\d)(?=[a-df-zA-DF-Z(]|[eE](?![+-]?\d))", "*", s)
        s = re.sub(r"\)(?=\()", ")*", s)
        # (x + 1)^2 e^x and 2x e^{-2x}: a space or a closing parenthesis
        # before the next factor is multiplication. A space between two
        # digits (4 340) stays ambiguous and unparsed.
        s = re.sub(r"\)(?=[A-Za-z\d])", ")*", s)
        s = re.sub(r"(?<=[\w)])\s+(?=[A-Za-z(]|\d)",
                   lambda m: m[0] if (s[m.start() - 1].isdigit() and s[m.end()].isdigit())
                   or re.search(r"(?:^|\W)(?:sqrt|lg|ln|log|exp|DIFF|PRIME)$", s[:m.start()])
                   else "*", s)
        s = re.sub(r"\b([abcd])([xyz])\b", r"\1*\2", s)
        s = re.sub(r"\b([abcd])\s*\(", r"\1*(", s)
        # x(x^2 - 3) is a product unless x is a defined function.
        definitions = getattr(self, "_function_definitions", {})
        functions = set(definitions) - _BARE_FUNCTIONS
        # u(x) and v(x) name the functions of a product-rule solution.
        s = re.sub(r"\b([uvw])\(([a-z])\)",
                   lambda m: m[1] if m[1] in definitions
                   and str(definitions[m[1]].variables[0]) == m[2] else m[0], s)
        s = re.sub(r"\b([xyztuvwkmn])\s*\(",
                   lambda m: m[0] if m[1] in functions else f"{m[1]}*(", s)

        try:
            return sympify(s, locals={"lg": lambda value: log(value, 10),
                                      "log": lambda value: log(value, 10), "ln": log,
                                      "e": E, "DIFF": _derivative, "PRIME": _prime})
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
        # Single variable = expression is usually a definition (e.g., f(x) = 2x+1).
        # A subscripted name labels a value: x_1 = -1, y_S = f(2).
        if re.match(r"^[a-zA-Z](?:_\{?\w+\}?)?(\([a-zA-Z,\s]+\))?$", lhs):
            return True
        if re.match(r"^[a-zA-Z]$", lhs) and not re.search(r"\d|[+\-*/^]", rhs):
            return True
        return False

    @staticmethod
    def _context_claims_identity(context: str) -> bool:
        """Return True only when nearby prose explicitly presents an identity.

        ``for alle`` is also ordinary exercise language (for example, "løs
        for alle ``u``"). Treating that phrase by itself as an identity made
        finite-root equations fail before their solution set could be checked.
        """
        normalized = re.sub(r"\s+", " ", context.lower())
        if (
            "identitet" in normalized
            or "uansett verdien" in normalized
            or "alltid lik" in normalized
        ):
            return True
        return bool(
            re.search(r"\bgjelder\b[^.!?]{0,100}\bfor alle\b", normalized)
            or re.search(r"\bfor alle\b[^.!?]{0,100}\bgjelder\b", normalized)
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
        lines.append(
            "Disse uttrykkene er ikke nødvendigvis feil, men kontrollen kan ikke lese dem. "
            "Et tomt svar løser ikke problemet: skriv hvert uttrykk om til enkel standardnotasjon "
            r"(for eksempel 10^{1/3} i stedet for \sqrt[3]{10}), del lange kjeder i kortere "
            "likheter og flytt tekst og enheter ut av formelen.\n"
        )
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
