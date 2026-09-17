"""Finished mathematics needs machine proof, never a synthetic teacher approval."""

import base64
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.job_store import load_job_from_disk, persist_terminal_job
from app.models.state import GenerationRequest, LatexCompilationResult, PipelineState, PipelineStatus
from app.pipeline.agents import release_repair
from app.pipeline.graph import finalize
from app.verification.math_checker import MathChecker
from Skoleverksted.backend.platform.quality_gate import content_digest, require_export_ready


def exercise(equation, answer, number=1):
    return (rf"\begin{{taskbox}}{{Oppgave {number}}}Løs ${equation}$.\end{{taskbox}}"
            + rf"\section*{{Løsningsforslag}}\textbf{{Oppgave {number}}}${answer}$")


@pytest.mark.parametrize("equation,answer", [
    ("3^x=7", r"x=\frac{\lg(7)}{\lg(3)}"),
    ("3^x=7", r"x=\frac{\ln(7)}{\ln(3)}"),
    ("2x+3=7", "2x=4 \\Rightarrow x=2"),
    ("x^2=4", "x=2$ og $x=-2"),
])
def test_solves_equations_against_complete_fasit(equation, answer):
    result = MathChecker().verify(exercise(equation, answer))
    assert result.claims_correct >= 2
    assert result.claims_unparseable == result.claims_incorrect == 0


@pytest.mark.parametrize("equation,answer", [
    ("3^x=7", r"x=\frac{\lg(3)}{\lg(7)}"),
    ("x^2=4", "x=2"),  # Missing negative root, with no reason given.
    (r"\sqrt{x}=2", "x=-4"),
    ("3x=12", "x=5"),
])
def test_wrong_or_incomplete_fasit_is_blocked(equation, answer):
    assert MathChecker().verify(exercise(equation, answer)).claims_incorrect > 0


def test_a_further_value_after_the_roots_is_not_proof_of_an_error():
    """A drøfting states the symmetry line x = 2 right after the zeros."""
    body = (r"\begin{taskbox}{Oppgave 1}Løs $-x^2+4x+5=0$.\end{taskbox}\section*{Løsningsforslag}"
            r"\textbf{Oppgave 1}Nullpunktene er $x_1=-1$ og $x_2=5$. Symmetrilinjen er $x=2$.")
    result = MathChecker().verify(body)
    assert result.claims_incorrect == result.claims_unparseable == 0
    assert result.claims_correct > 0


def test_a_root_rejected_for_a_reason_is_not_an_error():
    body = (r"\begin{eksempel}{Vekstfaktor}Vi har $4b^2 = 36$, så $b^2 = \frac{36}{4} = 9$. "
            r"Da er $b = \sqrt{9} = 3$. Løsningen $b = -3$ forkaster vi, fordi vekstfaktoren må være positiv."
            r"\end{eksempel}")
    result = MathChecker().verify(body)
    assert result.claims_incorrect == result.claims_unparseable == 0


def test_formulas_rules_and_notation_are_not_unverified_claims():
    """Production regression: 50 of these blocked a correct chapter."""
    body = r"""\begin{regel}{Ettpunktsformelen}
$y - y_1 = a(x - x_1)$ og sirkelen $x^2 + y^2 = r^2$. Toppunkt: $x_T = -\frac{b}{2a}$.
Andregradslikningen $ax^2 + bx + c = 0$.
$\lg(u \cdot v) = \lg u + \lg v$ og $\lg(u^k) = k \cdot \lg u$.
\end{regel}
\begin{eksempel}{Linje}
Punktene $(x_1, y_1) = (1, 3)$ og $(x_2, y_2) = (4, 9)$ gir $D_f = [-1, 3]$ og
$y - 3 = 2(x - 1)$, altså $y - 3 = 2x - 2$.
Videre er $3\lg(x) + 5\lg(x) - 2\lg(x) = (3 + 5 - 2)\lg(x)$ og $x(x^2 - 3) = 0$.
\end{eksempel}"""
    result = MathChecker().verify(body)
    assert result.claims_incorrect == 0, [(c.latex_expression, c.error_message) for c in result.errors]
    assert result.claims_unparseable == 0, [(c.latex_expression, c.error_message) for c in result.unparseable_claims]
    assert result.claims_correct >= 3  # The logarithm rules and the rewrite are proven.


def test_a_false_rule_is_never_accepted():
    result = MathChecker().verify(r"Regelen $\lg(u + v) = \lg u + \lg v$ gjelder.")
    assert result.claims_correct == 0
    assert result.claims_incorrect + result.claims_unparseable > 0


def test_worked_examples_from_a_real_chapter_are_verified():
    """Production regression: correct answers written as chains, subscripts,
    rounded decimals and evaluations of a reused function name."""
    body = r"""\begin{eksempel}{Håndverker}
Modellen er \[ K(x) = 820x + 650 \] og vi setter inn $x = 4{,}5$:
\begin{align*}
K(4{,}5) &= 820 \cdot 4{,}5 + 650 \\ &= 3\,690 + 650 = 4\,340
\end{align*}
\begin{align*}
820x + 650 &= 5\,160 \\ 820x &= 4\,510 \\ x &= \frac{4\,510}{820} = 5{,}5
\end{align*}
\end{eksempel}
\begin{eksempel}{Nullpunkter}
$-x^2 + 4x + 5 = 0$ gir $(x - 5)(x + 1) = 0$, så $x_1 = -1$ og $x_2 = 5$.
\end{eksempel}
\begin{eksempel}{Bil}
\[ V(t) = 450\,000 \cdot 0{,}88^t \]
\begin{align*}
V(5) &= 450\,000 \cdot 0{,}88^5 \\ &= 450\,000 \cdot 0{,}52773
\end{align*}
\end{eksempel}
\begin{eksempel}{Tank}
\[ V(t) = 400 - 50t \quad \text{for } 0 \le t \le 8 \]
Da er $V(0) = 400 - 50 \cdot 0 = 400$.
\end{eksempel}
\begin{eksempel}{Logaritme}
$7^x = 25$ gir $x \lg 7 = \lg 25$, så $x = \frac{\lg 25}{\lg 7} \approx 1{,}65$.
\end{eksempel}"""
    result = MathChecker().verify(body)
    assert result.claims_incorrect == 0, [(c.latex_expression, c.error_message) for c in result.errors]
    assert result.claims_unparseable == 0, [(c.latex_expression, c.error_message) for c in result.unparseable_claims]
    assert result.claims_correct >= 8
    wrong = MathChecker().verify(body.replace("= 4\\,340", "= 4\\,350").replace("0{,}52773", "0{,}53773"))
    assert wrong.claims_incorrect >= 2


_SEVERAL_EQUATIONS = {
    "example": r"""\begin{eksempel}{Løs likningene}
a) $-2x + 4 = 0$ gir $-2x = -4$, altså $x = 2$.
b) $25x + 80 = 500$ gir $25x = 420$, altså $x = 16{,}8$.
\end{eksempel}""",
    "section": r"""\section{Lineære likninger}
Vi løser $-2x + 4 = 0$. Da får vi $-2x = -4$ og $x = 2$.
Et abonnement koster 80 kr pluss 25 kr per time: $25x + 80 = 500$, så $x = 16{,}8$.""",
    "exercise": r"""\begin{taskbox}{Oppgave 3}
Løs likningene.
\begin{enumerate}
\item $-2x + 4 = 0$
\item $25x + 80 = 500$
\end{enumerate}
\end{taskbox}
\section*{Løsningsforslag}
\textbf{Oppgave 3}
$-2x = -4$, så $x = 2$. Deretter $25x = 420$, så $x = 16{,}8$.""",
    "align": r"""\begin{eksempel}{To likninger}
\begin{align*}
-2x + 4 &= 0 \\ -2x &= -4 \\ x &= 2
\end{align*}
\begin{align*}
25x + 80 &= 500 \\ 25x &= 420 \\ x &= 16{,}8
\end{align*}
\end{eksempel}""",
}


@pytest.mark.parametrize("name", _SEVERAL_EQUATIONS)
def test_answers_to_other_equations_in_the_same_scope_are_not_errors(name):
    """Production regression: -2x+4=0 was failed because x=16,8 was in scope."""
    result = MathChecker().verify(_SEVERAL_EQUATIONS[name])
    assert result.claims_incorrect == 0, [(c.latex_expression, c.error_message) for c in result.errors]
    assert result.claims_correct > 0


@pytest.mark.parametrize("name", _SEVERAL_EQUATIONS)
def test_a_wrong_answer_among_several_equations_is_still_never_released(name):
    wrong = _SEVERAL_EQUATIONS[name].replace("16{,}8", "17{,}8")
    result = MathChecker().verify(wrong)
    assert result.claims_incorrect + result.claims_unparseable > 0


def test_logarithms_are_actually_checked():
    result = MathChecker().verify(r"$\lg(100)=2$. $\ln(1)=0$. $\log(1000)=2$.")
    assert result.claims_correct == 2
    assert result.claims_incorrect == 1
    assert result.claims_unparseable == 0


def test_multiline_worked_solution_is_verified_and_wrong_steps_are_caught():
    body = r"\begin{align*}3^x &= 7 \\ x &= \frac{\lg(7)}{\lg(3)}\end{align*}"
    result = MathChecker().verify(body)
    assert result.claims_correct == 2
    assert result.claims_unparseable == result.claims_incorrect == 0
    wrong = MathChecker().verify(body.replace(r"\lg(7)", r"\lg(8)"))
    assert wrong.claims_incorrect > 0
    arithmetic = MathChecker().verify(r"\begin{align*}2+3 &= 5 \\ &= 6\end{align*}")
    assert arithmetic.claims_incorrect == 1
    fraction = MathChecker().verify(r"\begin{align*}\frac{1}{2}+\frac{1}{2}&=1\end{align*}")
    assert fraction.claims_correct == 1
    assert fraction.claims_unparseable == 0


def test_fifteen_exponential_equations_and_subparts_do_not_require_review():
    tasks, answers = [], []
    for number in range(1, 6):
        tasks.append(rf"\begin{{taskbox}}{{Oppgave {number}}}\begin{{enumerate}}"
                     + "".join(rf"\item Løs $3^x={number*3+i}$." for i in range(3))
                     + r"\end{enumerate}\end{taskbox}")
        answers.append(rf"\textbf{{Oppgave {number}}}\begin{{enumerate}}"
                       + "".join(rf"\item $x=\frac{{\lg({number*3+i})}}{{\lg(3)}}$." for i in range(3))
                       + r"\end{enumerate}")
    body = "\n".join(tasks) + r"\section*{Løsningsforslag}" + "\n".join(answers)
    result = MathChecker().verify(body)
    assert result.claims_correct == 30
    assert result.claims_unparseable == result.claims_incorrect == 0
    wrong = body.replace(r"\lg(16)", r"\lg(17)")
    assert MathChecker().verify(wrong).claims_incorrect > 0


@pytest.fixture
def released(monkeypatch):
    state = PipelineState(
        owner_id="teacher", request=GenerationRequest(grade="VG1 1T", topic="Algebra",
            include_exercises=False, include_theory=False),
        full_document=r"\documentclass{article}\begin{document}" + exercise("3^x=7", r"x=\frac{\lg(7)}{\lg(3)}") + r"\end{document}",
        latex_compilation=LatexCompilationResult(success=True),
    )
    monkeypatch.setattr("app.verification.latex_checker.LatexChecker.check", lambda self, document:
        LatexCompilationResult(success=True, pdf_base64=base64.b64encode(b"%PDF-verified").decode()))
    monkeypatch.setattr(release_repair, "LLMInterface", Mock(side_effect=AssertionError("No repair needed")))
    result = finalize(state)
    assert result.status == PipelineStatus.COMPLETED
    assert result.automatic_approved_revision == content_digest(result.verification_content)
    assert not result.teacher_approved_at and not result.approved_digest
    persist_terminal_job(result)
    return result


def test_finished_pdf_download_and_sharing_need_no_approval_request(monkeypatch, released):
    restored = load_job_from_disk(released.job_id)
    assert restored.automatic_approved_revision == released.automatic_approved_revision
    monkeypatch.setattr(main, "_jobs", {restored.job_id: restored})
    main.app.dependency_overrides[main.get_current_user] = lambda: "teacher"
    try:
        with TestClient(main.app) as client:
            response = client.get(f"/generate/{restored.job_id}/pdf")
            assert response.status_code == 200, response.text
            assert response.content == b"%PDF-verified"
            response = client.post("/sharing", json={"resource_type": "generation", "resource_id": restored.job_id})
            assert response.status_code == 200, response.text
            restored.verification_content += " Changed"
            assert client.get(f"/generate/{restored.job_id}/pdf").status_code == 409
    finally:
        main.app.dependency_overrides.clear()


@pytest.mark.parametrize("mutation", ["revision", "source", "manifest", "pdf", "document"])
def test_automatic_release_cannot_bypass_machine_proof(monkeypatch, released, mutation):
    if mutation == "revision":
        released.automatic_approved_revision = "old"
    elif mutation == "source":
        released.truth_passport["status"] = "needs_review"
    elif mutation == "manifest":
        released.release_manifest = {}
    elif mutation == "pdf":
        released.pdf_base64 = base64.b64encode(b"changed-pdf").decode()
    else:
        released.full_document += " Changed"
    monkeypatch.setattr(main, "_jobs", {released.job_id: released})
    main.app.dependency_overrides[main.get_current_user] = lambda: "teacher"
    try:
        with TestClient(main.app) as client:
            assert client.get(f"/generate/{released.job_id}/pdf").status_code == 409
    finally:
        main.app.dependency_overrides.clear()


def test_failed_repair_revokes_automatic_release(monkeypatch, released):
    released.full_document = r"\begin{document}$2+2=5$\end{document}"
    model = Mock(invoke=Mock(return_value='{"edits":[]}'))
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kwargs: model)
    assert not release_repair.prepare_release(released)
    assert not released.automatic_approved_revision
    assert not released.source_approved and not released.release_manifest


def test_logarithm_exercise_feedback_is_repaired_even_with_high_score(monkeypatch):
    from app.models.state import ContentQualityIssue, ContentQualityReport
    state = PipelineState(request=GenerationRequest(grade="VG1 1T", topic="Logaritmer", material_type="kapittel"),
                          full_document=r"\begin{document}Mangler logaritmeoppgave. $2+2=4$\end{document}")
    monkeypatch.setattr(release_repair, "evaluate_content_quality", lambda *args: ContentQualityReport(passed=True, score=95))
    issue = ContentQualityIssue(code="weak_exercises", severity="warning", message="Minst én oppgave må kreve tierlogaritmer direkte.")
    monkeypatch.setattr("app.verification.semantic_quality.evaluate_semantic_quality",
                        lambda body, request: (95, [issue] if "Mangler" in body else []))
    model = Mock(invoke=Mock(return_value='{"edits":[{"before":"Mangler logaritmeoppgave.","after":"' + exercise("3^x=7", r"x=\frac{\lg(7)}{\lg(3)}").replace('\\', '\\\\') + '"}]}'))
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kwargs: model)
    assert release_repair.prepare_release(state)
    assert "tierlogaritmer direkte" in model.invoke.call_args.args[1]
    assert state.math_verification.claims_unparseable == state.math_verification.claims_incorrect == 0


def test_unresolved_rubric_opinions_still_deliver_a_proven_document(monkeypatch):
    """Pedagogical taste steers repairs; it never withholds verified mathematics."""
    from app.models.state import ContentQualityIssue, ContentQualityReport
    state = PipelineState(request=GenerationRequest(grade="VG1 1T", topic="Logaritmer", material_type="kapittel"),
                          full_document=r"\begin{document}Runde 0. " + exercise("3^x=7", r"x=\frac{\lg(7)}{\lg(3)}") + r"\end{document}")
    monkeypatch.setattr(release_repair, "evaluate_content_quality", lambda *args: ContentQualityReport(passed=True, score=95))
    issue = ContentQualityIssue(code="weak_exercises", severity="warning", message="Oppgavene kunne vært mer varierte.")
    monkeypatch.setattr("app.verification.semantic_quality.evaluate_semantic_quality",
                        lambda body, request: (85, [issue]))
    rounds = iter(range(1, 20))
    model = Mock(invoke=Mock(side_effect=lambda *args: '{"edits":[{"before":"Runde %d.","after":"Runde %d."}]}'
                             % ((lambda n: (n - 1, n))(next(rounds)))))
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kwargs: model)

    assert release_repair.prepare_release(state)
    assert 0 < model.invoke.call_count <= release_repair._MAX_REPAIRS
    assert state.automatic_approved_revision == ""  # finalize issues the proof, not the repair loop.
    assert state.source_approved and state.verification_content
    assert [i.message for i in state.content_quality.issues] == [issue.message]
    assert state.math_verification.claims_correct > 0
    assert state.math_verification.claims_incorrect == state.math_verification.claims_unparseable == 0


def test_unresolved_mathematics_is_never_released_as_finished(monkeypatch):
    from app.models.state import ContentQualityReport
    state = PipelineState(request=GenerationRequest(grade="VG1 1T", topic="Algebra"),
                          full_document=r"\begin{document}" + exercise("x^2=4", "x=2") + r"\end{document}")
    monkeypatch.setattr(release_repair, "evaluate_content_quality", lambda *args: ContentQualityReport(passed=True, score=95))
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kwargs: Mock(invoke=Mock(return_value='{"edits":[]}')))
    assert not release_repair.prepare_release(state)
    assert not state.automatic_approved_revision and not state.pdf_base64


def _proven_chapter(monkeypatch, *, rubric):
    from app.models.state import ContentQualityReport
    state = PipelineState(request=GenerationRequest(grade="VG1 1P", topic="Likninger", material_type="kapittel"),
                          full_document=r"\begin{document}Innledning. " + exercise("2x+3=7", "x=2") + r"\end{document}")
    monkeypatch.setattr(release_repair, "evaluate_content_quality", lambda *args: ContentQualityReport(passed=True, score=95))
    monkeypatch.setattr("app.verification.semantic_quality.evaluate_semantic_quality", rubric)
    return state


def _rubric_timeout(body, request):
    from Skoleverksted.backend.platform.quality_runtime import QualityLayerTimeout
    raise QualityLayerTimeout("final content quality check timed out")


def test_an_unavailable_rubric_never_fails_a_proven_chapter(monkeypatch):
    """Production regression: a timed-out advisory call stopped the whole job."""
    state = _proven_chapter(monkeypatch, rubric=_rubric_timeout)
    monkeypatch.setattr(release_repair, "LLMInterface", Mock(side_effect=AssertionError("No repair needed")))
    assert release_repair.prepare_release(state)
    assert state.source_approved and state.verification_content
    assert "kunne ikke fullføres" in state.content_quality.semantic_summary


def test_a_failing_repair_model_delivers_the_verified_revision(monkeypatch):
    from app.models.state import ContentQualityIssue
    issue = ContentQualityIssue(code="didactics", severity="warning", message="Flere eksempler ville hjulpet.")
    state = _proven_chapter(monkeypatch, rubric=lambda body, request: (80, [issue]))
    model = Mock(invoke=Mock(side_effect=TimeoutError("Modellen svarte ikke")))
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kwargs: model)
    assert release_repair.prepare_release(state)
    assert 0 < model.invoke.call_count <= release_repair._MAX_STALLED_REPAIRS + 1
    assert state.content_quality.issues == [issue]


def test_a_spent_budget_releases_without_starting_a_repair(monkeypatch):
    from app.models.state import ContentQualityIssue
    issue = ContentQualityIssue(code="didactics", severity="warning", message="Flere eksempler ville hjulpet.")
    state = _proven_chapter(monkeypatch, rubric=lambda body, request: (80, [issue]))
    monkeypatch.setattr(release_repair, "_RELEASE_BUDGET_SECONDS", release_repair._MIN_REPAIR_ROUND_SECONDS - 1)
    monkeypatch.setattr(release_repair, "LLMInterface", Mock(side_effect=AssertionError("No time to repair")))
    assert release_repair.prepare_release(state)


def test_rejected_repairs_are_retried_without_reauditing_an_unchanged_document(monkeypatch):
    from app.models.state import ContentQualityIssue
    issue = ContentQualityIssue(code="didactics", severity="warning", message="Flere eksempler ville hjulpet.")
    state = _proven_chapter(monkeypatch, rubric=lambda body, request: (80, [issue]))
    audits = []
    original = release_repair.run_quality_pipeline
    monkeypatch.setattr(release_repair, "run_quality_pipeline", lambda **kw: audits.append(1) or original(**kw))
    model = Mock(invoke=Mock(return_value="ikke json"))
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kwargs: model)
    assert release_repair.prepare_release(state)
    assert model.invoke.call_count == release_repair._MAX_STALLED_REPAIRS + 1
    assert len(audits) == 1
    assert "ble avvist" in model.invoke.call_args.args[1]


def test_an_unrepairable_fasit_error_names_the_error(monkeypatch):
    state = _proven_chapter(monkeypatch, rubric=lambda body, request: (90, []))
    state.full_document = r"\begin{document}" + exercise("2x+3=7", "x=5") + r"\end{document}"
    monkeypatch.setattr(release_repair, "LLMInterface",
                        lambda **kwargs: Mock(invoke=Mock(side_effect=TimeoutError("Modellen svarte ikke"))))
    assert not release_repair.prepare_release(state)
    assert state.status == PipelineStatus.FAILED
    assert state.error_message.startswith("SymPy fant ")
    assert "2x+3=7" in state.error_message.replace(" ", "")
    assert not state.automatic_approved_revision and not state.source_approved


def test_raw_export_verifies_math_without_teacher_checkbox():
    from app.verification.automatic_export import verify_automatic_math_export
    assert verify_automatic_math_export(content=exercise("3^x=7", r"x=\frac{\lg(7)}{\lg(3)}"),
        export_id="matematikk.docx", topic="Logaritmer").source_approved
    with pytest.raises(PermissionError):
        verify_automatic_math_export(content="$2+2=5$", export_id="matematikk.docx", topic="Algebra")
