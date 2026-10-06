"""The concept trainer: extraction from verified content, the generated HTML's
safety, and the fail-closed artefact validator.
"""

import json
import re
import shutil
import subprocess

import pytest

from ScriptoriumFOV.backend.artifact import (
    ArtifactValidationError,
    MAX_TRAINER_BYTES,
    validate_trainer_artifact,
    validate_trainer_html,
)
from ScriptoriumFOV.backend.concept_trainer import (
    MAX_TERMS,
    TrainerUnavailable,
    build_trainer,
    extract_terms,
    render_trainer_html,
)

TEXT = (
    "Norge er et demokrati. I et demokrati kan alle stemme. Folket velger politikere. "
    "En politiker jobber på Stortinget. Stortinget lager lover. Lover gjelder for alle."
)
WORKSHEET = (
    "a) VIKTIGE BEGREPER\n"
    "Demokrati: Folket bestemmer sammen.\n"
    "Politiker: En person som jobber med politikk.\n"
    "Stortinget: Norges viktigste politiske forsamling.\n"
    "Lover: Regler som gjelder for alle.\n"
    "Stemme: Å velge noe ved valg.\n\n"
    "b) LESEFORSTÅELSE\n1. Hva er et demokrati?\na) Folkestyre *\nb) Kongestyre"
)


def _content(text: str = TEXT, worksheet: str = WORKSHEET) -> str:
    return json.dumps({"text": text, "worksheet": worksheet, "language_exercises": None}, ensure_ascii=False)


def _model(**overrides):
    args = {"content": _content(), "topic": "Demokrati i Norge", "subject": "Samfunnsfag", "level": "A2.1"}
    args.update(overrides)
    return build_trainer(**args)


def _embedded_data(html: str) -> dict:
    match = re.search(r'<script type="application/json" id="trainer-data">(.*?)</script>', html, re.DOTALL)
    return json.loads(match.group(1))


# ---------------------------------------------------------------------------
# Extracting terms from the sheet
# ---------------------------------------------------------------------------


def test_terms_are_read_from_the_key_terms_section_only():
    pairs = extract_terms(WORKSHEET)
    assert pairs[0] == ("Demokrati", "Folket bestemmer sammen.")
    assert len(pairs) == 5
    assert all("Hva er et demokrati" not in definition for _, definition in pairs)


def test_bullets_numbering_and_bold_markers_are_stripped():
    worksheet = "VIKTIGE BEGREPER\n- **Klimasone**: Et område med likt klima.\n2) Temperert: Ikke for varmt.\n• Arktisk: Veldig kaldt klima."
    assert extract_terms(worksheet) == [
        ("Klimasone", "Et område med likt klima."),
        ("Temperert", "Ikke for varmt."),
        ("Arktisk", "Veldig kaldt klima."),
    ]


def test_lines_that_do_not_fit_are_skipped_instead_of_guessed():
    worksheet = (
        "VIKTIGE BEGREPER\n"
        "Bare et ord uten kolon\n"
        "Ord: x\n"  # one-word definition
        "Et veldig langt begrep som ikke er et begrep: Definisjon her.\n"  # six-word term
        "Gyldig: En gyldig forklaring her.\n"
        "gyldig: Duplikat med liten forbokstav her."
    )
    assert extract_terms(worksheet) == [("Gyldig", "En gyldig forklaring her.")]


def test_terms_are_capped():
    lines = "\n".join(f"Ord{i}: Forklaring nummer {i} her." for i in range(30))
    assert len(extract_terms("VIKTIGE BEGREPER\n" + lines)) == MAX_TERMS


def test_english_key_vocabulary_is_read_too():
    pairs = extract_terms("a) KEY VOCABULARY\nClimate: The weather in a place.\nZone: An area of land.")
    assert [term for term, _ in pairs] == ["Climate", "Zone"]


# ---------------------------------------------------------------------------
# The model: everything comes from the verified content
# ---------------------------------------------------------------------------


def test_every_term_definition_and_example_is_copied_from_the_verified_content():
    model = _model()
    sheet_sentences = {
        "Norge er et demokrati.", "I et demokrati kan alle stemme.", "Folket velger politikere.",
        "En politiker jobber på Stortinget.", "Stortinget lager lover.", "Lover gjelder for alle.",
    }
    for term in model.terms:
        assert f"{term.term}: {term.definition}" in WORKSHEET
        if term.example:
            assert term.example in sheet_sentences


def test_terms_prefer_an_example_no_other_term_already_uses():
    model = _model()
    by_term = {term.term: term.example for term in model.terms}
    assert by_term["Demokrati"] == "Norge er et demokrati."
    assert by_term["Stemme"] == "I et demokrati kan alle stemme."
    assert by_term["Politiker"] == "En politiker jobber på Stortinget."


def test_a_sentence_is_never_blanked_for_two_terms():
    model = _model()
    sentences = [(fill.before, fill.after) for fill in model.fill]
    assert len(sentences) == len(set(sentences))
    for fill in model.fill:
        term = next(t for t in model.terms if t.id == fill.term_id)
        assert fill.before + term.term + fill.after == term.example or (
            (fill.before + term.term + fill.after).lower() == term.example.lower()
        )


def test_only_exact_unbent_matches_are_blanked():
    # "demokratiet" and "politikere" are bent forms and must not become blanks.
    text = "Demokratiet er viktig for Norge. Politikere stemmer ofte. Folk bor i landet."
    worksheet = "VIKTIGE BEGREPER\nDemokrati: Folket bestemmer sammen.\nPolitiker: En person i politikk."
    model = _model(content=_content(text, worksheet))
    assert model.fill == []
    assert all(term.example is None for term in model.terms)


def test_the_fill_in_exercise_is_dropped_below_two_sentences():
    text = "Norge er et demokrati. Landet er stort og vakkert."
    model = _model(content=_content(text, WORKSHEET))
    assert model.fill == []


def test_quiz_alternates_meaning_and_term_questions_with_the_answer_among_distinct_options():
    model = _model()
    assert [q.kind for q in model.quiz] == ["definition", "term", "definition", "term", "definition"]
    for question in model.quiz:
        texts = [option["text"] for option in question.options]
        assert len(texts) == len(set(texts)) == 4
        assert question.answer in [option["id"] for option in question.options]


def test_a_two_term_quiz_has_two_options_per_question():
    worksheet = "VIKTIGE BEGREPER\nSol: Stjernen vår.\nMåne: Det lyser på natten."
    model = _model(content=_content("Solen lyser.", worksheet))
    assert all(len(question.options) == 2 for question in model.quiz)


def test_the_model_is_deterministic():
    assert _model() == _model()


def test_the_level_frame_is_passed_through_and_english_uses_english_labels():
    assert _model(frame="Hovedårsaken til ___ er ___ fordi ___.").frame.startswith("Hovedårsaken")
    english = _model(subject="Engelsk")
    assert english.language == "en"
    assert english.labels["tab_learn"] == "Learn the words"
    assert all(question.prompt.startswith(("What does", "Which word")) for question in english.quiz)


def test_too_little_verified_material_is_reported_not_faked():
    with pytest.raises(TrainerUnavailable, match="minst to begreper"):
        _model(content=_content(worksheet="VIKTIGE BEGREPER\nBare: Ett begrep her."))
    with pytest.raises(TrainerUnavailable, match="minst to begreper"):
        _model(content=_content(worksheet="a) LESEFORSTÅELSE\n1. Hva?"))


@pytest.mark.parametrize("bad", ["ikke json", "[]", "{}", json.dumps({"text": "x", "worksheet": 3})])
def test_unreadable_content_is_reported(bad):
    with pytest.raises(TrainerUnavailable):
        _model(content=bad)


# ---------------------------------------------------------------------------
# The generated document
# ---------------------------------------------------------------------------


def test_the_document_is_one_offline_self_contained_file():
    html = render_trainer_html(_model())
    assert html.startswith("<!doctype html>")
    assert 'lang="nb"' in html
    assert "default-src 'none'" in html
    assert "noindex" in html
    validate_trainer_html(html)  # raises on any external reference


def test_the_embedded_data_round_trips_the_model():
    model = _model()
    data = _embedded_data(render_trainer_html(model))
    assert [t["term"] for t in data["terms"]] == [t.term for t in model.terms]
    assert data["quiz"][0]["answer"] == model.quiz[0].answer
    assert data["draft"] is False


def test_untrusted_text_cannot_break_out_of_the_page():
    hostile = '</script><script>alert(1)</script><img src=x onerror=alert(1)> & "quotes"'
    worksheet = f"VIKTIGE BEGREPER\nAngrep: {hostile} og mer tekst.\nTrygt: Et vanlig begrep her."
    model = _model(content=_content(f"Angrep {hostile} er et ord her.", worksheet), topic=hostile)
    html = render_trainer_html(model)
    assert "<script>alert" not in html
    assert "<img" not in html
    assert html.count("<script") == 2  # the JSON data block and the app script, nothing injected
    assert _embedded_data(html)["terms"][0]["definition"].startswith(hostile)
    assert "&lt;/script&gt;" in html.split("<title>")[1].split("</title>")[0]


def test_a_topic_containing_a_placeholder_is_not_substituted_twice():
    html = render_trainer_html(_model(topic="__DATA__ __SCRIPT__ __STYLE__"))
    title = html.split("<title>")[1].split("</title>")[0]
    assert "__DATA__ __SCRIPT__ __STYLE__" in title
    assert "use strict" not in title and "trainer-data" not in title


def test_a_draft_is_clearly_marked_and_a_final_trainer_is_not():
    draft = render_trainer_html(_model(), draft=True)
    final = render_trainer_html(_model())
    assert 'role="alert"' in draft and "UTKAST – IKKE KILDEGODKJENT" in draft
    assert "<title>UTKAST – " in draft
    assert "UTKAST" not in final
    assert _embedded_data(draft)["draft"] is True


node = shutil.which("node")


@pytest.mark.skipif(node is None, reason="node is not installed")
def test_the_embedded_script_is_valid_javascript(tmp_path):
    html = render_trainer_html(_model())
    script = re.search(r"<script>(.*?)</script>", html, re.DOTALL).group(1)
    path = tmp_path / "trainer.js"
    path.write_text(script, encoding="utf-8")
    result = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# The fail-closed validator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutation, reason",
    [
        (lambda h: "", "trainer_empty"),
        (lambda h: "<html></html>", "trainer_not_html"),
        (lambda h: h.replace('id="trainer-data"', 'id="x"'), "trainer_data_missing"),
        (lambda h: h.replace("default-src 'none'", "default-src *"), "trainer_csp_missing"),
        (lambda h: h.replace("<body>", '<body><script src="https://evil.example/x.js"></script>'), "trainer_external_reference"),
        (lambda h: h.replace("<body>", '<body><a href="//evil.example">x</a>'), "trainer_external_reference"),
        (lambda h: h.replace("</style>", "@import url(x);</style>"), "trainer_external_reference"),
        (lambda h: h.replace("</style>", "body{background:url(https://evil.example/a.png)}</style>"), "trainer_external_reference"),
        (lambda h: h.replace("<body>", "<body><iframe></iframe>"), "trainer_external_reference"),
        (lambda h: h.replace("<body>", '<body><form action="/x"></form>'), "trainer_external_reference"),
        (lambda h: h + "x" * (MAX_TRAINER_BYTES + 1), "trainer_too_large"),
    ],
)
def test_the_validator_refuses_anything_that_is_not_one_offline_document(mutation, reason):
    html = render_trainer_html(_model())
    with pytest.raises(ArtifactValidationError, match=reason):
        validate_trainer_html(mutation(html))


def test_a_valid_trainer_becomes_a_typed_artifact():
    artifact = validate_trainer_artifact(render_trainer_html(_model()), "demokrati")
    assert artifact.filename == "demokrati.html"
    assert artifact.kind == "concept_trainer"
    assert artifact.content_type == "text/html; charset=utf-8"
    assert artifact.content.startswith(b"<!doctype html>")
    assert artifact.size_bytes == len(artifact.content)
