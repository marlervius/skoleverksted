"""Concept trainer (begrepstrener): a self-contained HTML practice app.

The trainer is derived, deterministically and without any model call, from a
learning sheet that has already passed the quality gate.  Every term,
definition and example sentence is copied from that verified content, so the
trainer cannot introduce a fact the gate has not audited.  The gate itself is
enforced by the download route in ``main.py``; this module only transforms.

The produced file is one HTML document with inline CSS and JS, a strict
Content-Security-Policy (no network access) and no external resources, so a
teacher can hand it to students as a plain file.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

if __package__:
    from .level_readability import count_words, split_sentences
    from .pdf_service import parse_worksheet_content
else:
    from level_readability import count_words, split_sentences
    from pdf_service import parse_worksheet_content

MIN_TERMS = 2
MAX_TERMS = 12
MAX_FILL_SENTENCES = 8
MIN_FILL_SENTENCES = 2
MAX_TERM_WORDS = 5
MAX_DEFINITION_CHARS = 220
MAX_EXAMPLE_WORDS = 25
MIN_EXAMPLE_WORDS = 4
QUIZ_OPTIONS = 4


class TrainerUnavailable(ValueError):
    """The sheet does not hold enough verified material for a trainer."""


@dataclass(frozen=True)
class Term:
    id: str
    term: str
    definition: str
    example: Optional[str] = None


@dataclass(frozen=True)
class QuizQuestion:
    id: str
    kind: str  # "definition": pick the meaning of a term; "term": pick the term for a meaning
    prompt: str
    options: list[dict]
    answer: str


@dataclass(frozen=True)
class FillSentence:
    term_id: str
    before: str
    after: str


@dataclass(frozen=True)
class TrainerModel:
    topic: str
    subject: str
    level: str
    language: str
    terms: list[Term]
    fill: list[FillSentence]
    quiz: list[QuizQuestion]
    frame: str = ""
    labels: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Extracting verified material
# ---------------------------------------------------------------------------

_LEADING_MARK_RE = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s*")


def _clean(value: str) -> str:
    cleaned = re.sub(r"(\*\*|__|`)", "", value or "").replace("*", "")
    cleaned = unicodedata.normalize("NFC", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" \t\"'«»")


def extract_terms(worksheet: str) -> list[tuple[str, str]]:
    """Return ``(term, definition)`` pairs from the sheet's key-terms section.

    The section is written as ``Begrep: definisjon`` per line.  Lines that do
    not fit that shape are skipped rather than guessed at.
    """
    section = parse_worksheet_content(str(worksheet or ""))["vocabulary"]
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_line in section.splitlines():
        line = _LEADING_MARK_RE.sub("", raw_line).strip()
        if ":" not in line:
            continue
        raw_term, _, raw_definition = line.partition(":")
        term, definition = _clean(raw_term), _clean(raw_definition)
        if not term or len(term.split()) > MAX_TERM_WORDS:
            continue
        if len(definition.split()) < 2 or len(definition) > MAX_DEFINITION_CHARS:
            continue
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        pairs.append((term, definition))
        if len(pairs) == MAX_TERMS:
            break
    return pairs


def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(
        r"(?<![0-9A-Za-zÆØÅæøå])" + re.escape(term) + r"(?![0-9A-Za-zÆØÅæøå])",
        re.IGNORECASE,
    )


def _example_for(term: str, sentences: list[str], avoid: set[str]) -> Optional[str]:
    """First fitting sentence that uses ``term``, preferring one no other term uses."""
    pattern = _term_pattern(term)
    fitting = [
        sentence
        for sentence in sentences
        if pattern.search(sentence) and MIN_EXAMPLE_WORDS <= count_words(sentence) <= MAX_EXAMPLE_WORDS
    ]
    for sentence in fitting:
        if sentence not in avoid:
            return sentence
    return fitting[0] if fitting else None


def _quiz(terms: list[Term], labels: dict) -> list[QuizQuestion]:
    """Build one question per term, alternating meaning and term questions.

    Distractors are the following terms in the list, so the quiz is
    reproducible and every wrong option is another verified item of the sheet.
    """
    count = len(terms)
    option_count = min(QUIZ_OPTIONS, count)
    questions: list[QuizQuestion] = []
    for index, term in enumerate(terms):
        by_definition = index % 2 == 0
        others = [terms[(index + step) % count] for step in range(1, count)]
        picked: list[Term] = []
        seen = {(term.definition if by_definition else term.term).casefold()}
        for other in others:
            text = other.definition if by_definition else other.term
            if text.casefold() in seen:
                continue
            seen.add(text.casefold())
            picked.append(other)
            if len(picked) == option_count - 1:
                break
        if len(picked) < 1:
            continue
        options = [
            {"id": item.id, "text": item.definition if by_definition else item.term}
            for item in [term, *picked]
        ]
        prompt = (
            labels["quiz_meaning"].format(term=term.term)
            if by_definition
            else labels["quiz_term"].format(definition=term.definition)
        )
        questions.append(QuizQuestion(
            id=f"q{index}",
            kind="definition" if by_definition else "term",
            prompt=prompt,
            options=options,
            answer=term.id,
        ))
    return questions


def build_trainer(
    *,
    content: str,
    topic: str,
    subject: str,
    level: str,
    frame: str = "",
) -> TrainerModel:
    """Build the trainer model from verified lesson JSON (``text`` + ``worksheet``)."""
    try:
        document = json.loads(content)
    except (TypeError, ValueError) as exc:
        raise TrainerUnavailable("Det kontrollerte innholdet kunne ikke leses.") from exc
    if not isinstance(document, dict) or not isinstance(document.get("worksheet"), str):
        raise TrainerUnavailable("Det kontrollerte innholdet har ikke et arbeidsark.")

    language = "en" if str(subject or "").strip().lower() == "engelsk" else "nb"
    labels = LABELS[language]
    pairs = extract_terms(document["worksheet"])
    if len(pairs) < MIN_TERMS:
        raise TrainerUnavailable(labels["too_few_terms"])

    sentences = split_sentences(str(document.get("text") or ""))
    terms: list[Term] = []
    chosen: set[str] = set()
    for index, (term, definition) in enumerate(pairs):
        example = _example_for(term, sentences, chosen)
        if example:
            chosen.add(example)
        terms.append(Term(id=f"t{index}", term=term, definition=definition, example=example))

    fill: list[FillSentence] = []
    used: set[str] = set()
    for term in terms:
        if term.example is None or term.example in used or len(fill) == MAX_FILL_SENTENCES:
            continue
        match = _term_pattern(term.term).search(term.example)
        if match:
            used.add(term.example)
            fill.append(FillSentence(term.id, term.example[: match.start()], term.example[match.end():]))
    if len(fill) < MIN_FILL_SENTENCES:
        # Only exact, unbent matches are blanked, so a sheet whose text inflects
        # its terms may yield too few for a worthwhile exercise.
        fill = []

    return TrainerModel(
        topic=str(topic or "").strip(),
        subject=str(subject or "").strip(),
        level=str(level or "").strip(),
        language=language,
        terms=terms,
        fill=fill,
        quiz=_quiz(terms, labels),
        frame=str(frame or "").strip(),
        labels=labels,
    )


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

LABELS: dict[str, dict[str, str]] = {
    "nb": {
        "title": "Begrepstrener",
        "points": "Poeng",
        "progress": "Fremdrift",
        "tab_learn": "Lær begrepene",
        "tab_match": "Koble sammen",
        "tab_fill": "Fyll inn ord",
        "tab_quiz": "Quiz",
        "tab_write": "Skriv selv",
        "learn_intro": "Les begrepene. Skriv ordet på ditt språk.",
        "my_language": "Mitt språk",
        "from_text": "Fra teksten",
        "next": "Gå videre",
        "match_intro": "Trykk på et begrep. Trykk så på forklaringen som passer.",
        "terms": "Begreper",
        "meanings": "Forklaringer",
        "match_done": "Alle begrepene er koblet!",
        "fill_intro": "Velg riktig ord i hver setning.",
        "word_bank": "Ordbank",
        "choose": "Velg ord",
        "check": "Sjekk svarene",
        "fill_result": "{right} av {total} riktige.",
        "quiz_intro": "Velg riktig svar.",
        "quiz_meaning": "Hva betyr «{term}»?",
        "quiz_term": "Hvilket begrep passer? «{definition}»",
        "correct": "Riktig!",
        "try_again": "Ikke helt. Prøv igjen.",
        "wrong": "Ikke helt. Riktig svar: {answer}",
        "quiz_result": "{right} av {total} riktige.",
        "write_intro": "Skriv en setning med hvert begrep.",
        "frame": "Setningsramme",
        "write_prompt": "Skriv en setning med «{term}».",
        "done": "Ferdig!",
        "done_ok": "Ferdig",
        "badge_quiz": "Quiz-mester",
        "badge_match": "Koble-ekspert",
        "badge_score": "Høy poengsum",
        "draft": "UTKAST – IKKE KILDEGODKJENT. Kun for lærerens gjennomgang. Ikke del med elever.",
        "source_note": "Alle begreper, forklaringer og eksempler er hentet fra det kontrollerte læringsarket.",
        "privacy_note": "Det du skriver lagres ikke. Det forsvinner når du lukker siden.",
        "too_few_terms": "Begrepstrener krever minst to begreper under «Viktige begreper» i læringsarket.",
        "tabs": "Øvelser",
    },
    "en": {
        "title": "Vocabulary trainer",
        "points": "Points",
        "progress": "Progress",
        "tab_learn": "Learn the words",
        "tab_match": "Match",
        "tab_fill": "Fill in",
        "tab_quiz": "Quiz",
        "tab_write": "Write",
        "learn_intro": "Read the words. Write each word in your language.",
        "my_language": "My language",
        "from_text": "From the text",
        "next": "Continue",
        "match_intro": "Press a word. Then press the meaning that fits.",
        "terms": "Words",
        "meanings": "Meanings",
        "match_done": "All the words are matched!",
        "fill_intro": "Choose the right word in each sentence.",
        "word_bank": "Word bank",
        "choose": "Choose a word",
        "check": "Check answers",
        "fill_result": "{right} of {total} correct.",
        "quiz_intro": "Choose the right answer.",
        "quiz_meaning": "What does “{term}” mean?",
        "quiz_term": "Which word fits? “{definition}”",
        "correct": "Correct!",
        "try_again": "Not quite. Try again.",
        "wrong": "Not quite. Correct answer: {answer}",
        "quiz_result": "{right} of {total} correct.",
        "write_intro": "Write a sentence with each word.",
        "frame": "Sentence frame",
        "write_prompt": "Write a sentence with “{term}”.",
        "done": "Done!",
        "done_ok": "Done",
        "badge_quiz": "Quiz master",
        "badge_match": "Matching expert",
        "badge_score": "High score",
        "draft": "DRAFT – NOT SOURCE APPROVED. For the teacher's review only. Do not share with students.",
        "source_note": "All words, meanings and examples come from the verified learning sheet.",
        "privacy_note": "What you write is not saved. It disappears when you close the page.",
        "too_few_terms": "The trainer needs at least two words under “Key vocabulary” in the learning sheet.",
        "tabs": "Exercises",
    },
}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
    "base-uri 'none'; form-action 'none'"
)


def _model_data(model: TrainerModel, *, draft: bool) -> dict:
    return {
        "topic": model.topic,
        "subject": model.subject,
        "level": model.level,
        "language": model.language,
        "draft": draft,
        "frame": model.frame,
        # The draft warning text is only shipped in a draft, so an approved
        # trainer never carries the marker.
        "labels": {key: value for key, value in model.labels.items() if draft or key != "draft"},
        "terms": [
            {"id": t.id, "term": t.term, "definition": t.definition, "example": t.example}
            for t in model.terms
        ],
        "fill": [
            {"term_id": f.term_id, "before": f.before, "after": f.after} for f in model.fill
        ],
        "quiz": [
            {"id": q.id, "kind": q.kind, "prompt": q.prompt, "options": q.options, "answer": q.answer}
            for q in model.quiz
        ],
    }


def _json_for_script(data: dict) -> str:
    """Serialise ``data`` so it can never close or break the script element."""
    text = json.dumps(data, ensure_ascii=False)
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


def _escape_html(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_trainer_html(model: TrainerModel, *, draft: bool = False) -> str:
    """Render the trainer as one self-contained HTML document."""
    labels = model.labels
    prefix = "UTKAST – " if draft and model.language == "nb" else "DRAFT – " if draft else ""
    title = f"{prefix}{labels['title']}: {model.topic}".strip()
    banner = (
        f'<div class="draft" role="alert">{_escape_html(labels["draft"])}</div>' if draft else ""
    )
    values = {
        "LANG": "en" if model.language == "en" else "nb",
        "CSP": _CSP,
        "TITLE": _escape_html(title),
        "BANNER": banner,
        "STYLE": _STYLE,
        "SCRIPT": _SCRIPT,
        "DATA": _json_for_script(_model_data(model, draft=draft)),
    }
    # One pass over the template only: substituted values are never rescanned,
    # so a topic that happens to contain "__DATA__" cannot trigger a second
    # substitution.
    return _PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], _TEMPLATE)


_PLACEHOLDER_RE = re.compile(r"__(LANG|CSP|TITLE|BANNER|STYLE|SCRIPT|DATA)__")


_TEMPLATE = """<!doctype html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="__CSP__">
<meta name="robots" content="noindex">
<title>__TITLE__</title>
<style>__STYLE__</style>
</head>
<body>
__BANNER__
<header class="top">
  <div class="top-row">
    <h1 id="title"></h1>
    <p class="score" aria-live="polite"><span id="score-label"></span>: <strong id="score">0</strong></p>
  </div>
  <div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" id="bar"><div id="bar-fill"></div></div>
  <nav id="tabs" role="tablist"></nav>
</header>
<main id="main"></main>
<p class="status" id="status" role="status" aria-live="polite"></p>
<footer id="footer"></footer>
<script type="application/json" id="trainer-data">__DATA__</script>
<script>__SCRIPT__</script>
</body>
</html>
"""

_STYLE = """
:root{--ink:#1c1917;--muted:#57534e;--line:#d6d3d1;--bg:#fff;--panel:#fafaf9;--accent:#1e40af;--accent-bg:#eff6ff;
--ok:#166534;--ok-bg:#dcfce7;--bad:#991b1b;--bad-bg:#fee2e2}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans",sans-serif;text-align:left}
.draft{background:#fef3c7;color:#78350f;border-bottom:2px solid #b45309;padding:.75rem 1rem;font-weight:700}
.top,main,footer,.status{max-width:44rem;margin:0 auto;padding:0 1rem}
.top{padding-top:1rem}
.top-row{display:flex;gap:1rem;align-items:baseline;justify-content:space-between;flex-wrap:wrap}
h1{font-size:1.4rem;line-height:1.3;margin:0}
h2{font-size:1.15rem;margin:1.25rem 0 .5rem}
.score{margin:0;color:var(--muted)}
.bar{height:.5rem;background:#e7e5e4;border-radius:.25rem;margin:.75rem 0;overflow:hidden}
#bar-fill{height:100%;width:0;background:var(--accent);transition:width .4s ease}
[role=tablist]{display:flex;flex-wrap:wrap;gap:.5rem;margin:.5rem 0 1rem}
[role=tab]{min-height:44px;padding:.4rem .9rem;border:1px solid var(--line);border-radius:.5rem;background:var(--bg);color:var(--ink);font:inherit;cursor:pointer}
[role=tab][aria-selected=true]{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
button,input,select,textarea{font:inherit;color:inherit}
button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,[role=tab]:focus-visible{outline:3px solid #f59e0b;outline-offset:2px}
.intro{color:var(--muted);margin:.25rem 0 1rem}
.card{border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:.5rem;padding:.9rem 1rem;margin:0 0 1rem;background:var(--panel)}
.card h3{margin:0 0 .25rem;font-size:1.1rem}
.card p{margin:.25rem 0}
.example{background:#fffbeb;border:1px dashed #d97706;border-radius:.4rem;padding:.4rem .6rem;margin:.5rem 0}
.field{display:flex;gap:.5rem;align-items:center;margin-top:.5rem;flex-wrap:wrap}
.field label{color:var(--muted);font-size:.95rem}
input[type=text],select,textarea{border:1px solid #78716c;border-radius:.4rem;padding:.4rem .6rem;background:#fff;min-height:44px}
input[type=text]{flex:1 1 12rem}
textarea{width:100%;min-height:4.5rem}
.btn{min-height:44px;padding:.5rem 1.1rem;border:1px solid var(--accent);border-radius:.5rem;background:var(--accent);color:#fff;font-weight:600;cursor:pointer}
.btn:disabled{background:#a8a29e;border-color:#a8a29e;cursor:default}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}
@media (max-width:34rem){.cols{grid-template-columns:1fr}}
.pick{display:block;width:100%;min-height:44px;margin:0 0 .5rem;padding:.5rem .7rem;border:2px solid var(--line);border-radius:.5rem;background:var(--bg);text-align:left;cursor:pointer}
.pick[aria-pressed=true]{border-color:var(--accent);background:var(--accent-bg)}
.pick.ok{border-color:var(--ok);background:var(--ok-bg);color:var(--ok);cursor:default}
.pick.bad,select.bad{border-color:var(--bad);background:var(--bad-bg)}
select.ok{border-color:var(--ok);background:var(--ok-bg)}
.shake{animation:shake .4s}
@keyframes shake{25%{transform:translateX(-6px)}75%{transform:translateX(6px)}}
@media (prefers-reduced-motion:reduce){.shake{animation:none}#bar-fill{transition:none}}
.sentence{margin:0 0 1rem}
.bank{display:flex;flex-wrap:wrap;gap:.4rem;margin:.25rem 0 1rem;padding:0;list-style:none}
.bank li{padding:.15rem .6rem;border:1px solid var(--line);border-radius:1rem;background:var(--panel)}
.result{font-weight:700;margin:.75rem 0}
.q{margin:0 0 1.25rem}
.q .prompt{font-weight:600;margin:0 0 .5rem}
.fb{margin:.25rem 0 0;font-weight:600}
.fb.ok{color:var(--ok)}.fb.bad{color:var(--bad)}
.badges{display:flex;gap:.5rem;flex-wrap:wrap;margin:.5rem 0}
.badge{border:2px solid var(--ok);color:var(--ok);background:var(--ok-bg);border-radius:1rem;padding:.1rem .7rem;font-weight:700}
.status{min-height:1.5rem;color:var(--muted)}
footer{color:var(--muted);font-size:.9rem;padding-bottom:2rem}
footer p{margin:.25rem 0}
"""

_SCRIPT = r"""
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("trainer-data").textContent);
  var L = data.labels;
  var state = { score: 0, matched: {}, filled: {}, quiz: {}, written: {}, matchAll: false, quizRight: -1 };
  var main = document.getElementById("main");
  var status = document.getElementById("status");

  function el(tag, attrs, kids) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      if (key === "text") node.textContent = attrs[key];
      else if (key === "class") node.className = attrs[key];
      else node.setAttribute(key, attrs[key]);
    });
    (kids || []).forEach(function (kid) { node.appendChild(kid); });
    return node;
  }
  function shuffled(list) {
    var copy = list.slice();
    for (var i = copy.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = copy[i]; copy[i] = copy[j]; copy[j] = tmp;
    }
    return copy;
  }
  function fmt(template, values) {
    return template.replace(/\{(\w+)\}/g, function (_, key) { return String(values[key]); });
  }
  function say(message) { status.textContent = message; }
  function wrong(node) {
    node.classList.remove("shake"); void node.offsetWidth; node.classList.add("shake");
  }
  function count(map) { return Object.keys(map).length; }

  var termById = {};
  data.terms.forEach(function (t) { termById[t.id] = t; });
  var totalActivities = data.terms.length + data.fill.length + data.quiz.length + data.terms.length;

  function update() {
    document.getElementById("score").textContent = String(state.score);
    var doneCount = count(state.matched) + count(state.filled) + count(state.quiz) + count(state.written);
    var percent = totalActivities ? Math.round(100 * doneCount / totalActivities) : 0;
    var bar = document.getElementById("bar");
    bar.setAttribute("aria-valuenow", String(percent));
    document.getElementById("bar-fill").style.width = percent + "%";
  }
  function award(points) { state.score += points; update(); }

  // ---- Learn --------------------------------------------------------------
  function viewLearn() {
    var box = el("div");
    box.appendChild(el("p", { class: "intro", text: L.learn_intro }));
    data.terms.forEach(function (t) {
      var inputId = "my-" + t.id;
      var card = el("article", { class: "card" }, [
        el("h3", { text: t.term }),
        el("p", { text: t.definition })
      ]);
      if (t.example) {
        card.appendChild(el("p", { class: "example", text: L.from_text + ": " + t.example }));
      }
      card.appendChild(el("div", { class: "field" }, [
        el("label", { for: inputId, text: L.my_language }),
        el("input", { type: "text", id: inputId, autocomplete: "off", spellcheck: "false" })
      ]));
      box.appendChild(card);
    });
    var next = el("button", { type: "button", class: "btn", text: L.next });
    next.addEventListener("click", function () { show(views[1].id); tabNodes[views[1].id].focus(); });
    box.appendChild(next);
    return box;
  }

  // ---- Match --------------------------------------------------------------
  function viewMatch() {
    var box = el("div");
    box.appendChild(el("p", { class: "intro", text: L.match_intro }));
    var selectedTerm = null, selectedMeaning = null;
    var termButtons = {}, meaningButtons = {};
    var result = el("p", { class: "result" });

    function resolve() {
      if (!selectedTerm || !selectedMeaning) return;
      var termNode = termButtons[selectedTerm], meaningNode = meaningButtons[selectedMeaning];
      if (selectedTerm === selectedMeaning) {
        [termNode, meaningNode].forEach(function (node) {
          node.className = "pick ok"; node.disabled = true; node.setAttribute("aria-pressed", "false");
        });
        state.matched[selectedTerm] = true;
        award(5);
        say(L.correct);
        if (count(state.matched) === data.terms.length) {
          result.textContent = L.match_done;
          state.matchAll = true;
          renderBadges();
        }
      } else {
        [termNode, meaningNode].forEach(function (node) {
          node.setAttribute("aria-pressed", "false"); wrong(node);
        });
        say(L.try_again);
      }
      selectedTerm = null; selectedMeaning = null;
      update();
    }
    function pick(kind, id, node) {
      if (state.matched[id]) return;
      var map = kind === "term" ? termButtons : meaningButtons;
      Object.keys(map).forEach(function (key) {
        if (!state.matched[key]) map[key].setAttribute("aria-pressed", "false");
      });
      node.setAttribute("aria-pressed", "true");
      if (kind === "term") selectedTerm = id; else selectedMeaning = id;
      resolve();
    }

    var left = el("div"), right = el("div");
    left.appendChild(el("h2", { text: L.terms }));
    right.appendChild(el("h2", { text: L.meanings }));
    data.terms.forEach(function (t) {
      var node = el("button", { type: "button", class: "pick", "aria-pressed": "false", text: t.term });
      node.addEventListener("click", function () { pick("term", t.id, node); });
      termButtons[t.id] = node; left.appendChild(node);
    });
    shuffled(data.terms).forEach(function (t) {
      var node = el("button", { type: "button", class: "pick", "aria-pressed": "false", text: t.definition });
      node.addEventListener("click", function () { pick("meaning", t.id, node); });
      meaningButtons[t.id] = node; right.appendChild(node);
    });
    box.appendChild(el("div", { class: "cols" }, [left, right]));
    box.appendChild(result);
    return box;
  }

  // ---- Fill in ------------------------------------------------------------
  function viewFill() {
    var box = el("div");
    box.appendChild(el("p", { class: "intro", text: L.fill_intro }));
    var wordIds = [];
    data.fill.forEach(function (f) { if (wordIds.indexOf(f.term_id) < 0) wordIds.push(f.term_id); });
    var bank = el("ul", { class: "bank", "aria-label": L.word_bank });
    shuffled(wordIds).forEach(function (id) { bank.appendChild(el("li", { text: termById[id].term })); });
    box.appendChild(el("h2", { text: L.word_bank }));
    box.appendChild(bank);

    var selects = [];
    data.fill.forEach(function (f, index) {
      var selectId = "fill-" + index;
      var select = el("select", { id: selectId, "aria-label": L.choose });
      select.appendChild(el("option", { value: "", text: "– " + L.choose + " –" }));
      shuffled(wordIds).forEach(function (id) {
        select.appendChild(el("option", { value: id, text: termById[id].term }));
      });
      selects.push({ node: select, fill: f, key: "f" + index });
      box.appendChild(el("p", { class: "sentence" }, [
        document.createTextNode(f.before), select, document.createTextNode(f.after)
      ]));
    });
    var result = el("p", { class: "result" });
    var check = el("button", { type: "button", class: "btn", text: L.check });
    check.addEventListener("click", function () {
      var right = 0;
      selects.forEach(function (item) {
        if (item.node.disabled) { right++; return; }
        if (item.node.value === item.fill.term_id) {
          item.node.className = "ok"; item.node.disabled = true;
          if (!state.filled[item.key]) { state.filled[item.key] = true; award(3); }
          right++;
        } else {
          item.node.className = "bad"; wrong(item.node);
        }
      });
      result.textContent = fmt(L.fill_result, { right: right, total: selects.length });
      say(result.textContent);
      update();
    });
    box.appendChild(check);
    box.appendChild(result);
    return box;
  }

  // ---- Quiz ---------------------------------------------------------------
  function viewQuiz() {
    var box = el("div");
    box.appendChild(el("p", { class: "intro", text: L.quiz_intro }));
    var result = el("p", { class: "result" });
    function summary() {
      var right = 0, answered = count(state.quiz);
      Object.keys(state.quiz).forEach(function (key) { if (state.quiz[key] === "right") right++; });
      if (answered === data.quiz.length) {
        result.textContent = fmt(L.quiz_result, { right: right, total: data.quiz.length });
        state.quizRight = right;
        renderBadges();
      }
    }
    data.quiz.forEach(function (q) {
      var wrapper = el("div", { class: "q" });
      wrapper.appendChild(el("p", { class: "prompt", text: q.prompt }));
      var feedback = el("p", { class: "fb", "aria-live": "polite" });
      var buttons = [];
      shuffled(q.options).forEach(function (option) {
        var node = el("button", { type: "button", class: "pick", text: option.text });
        buttons.push({ node: node, option: option });
        node.addEventListener("click", function () {
          if (state.quiz[q.id]) return;
          var isRight = option.id === q.answer;
          state.quiz[q.id] = isRight ? "right" : "wrong";
          buttons.forEach(function (b) {
            b.node.disabled = true;
            if (b.option.id === q.answer) b.node.className = "pick ok";
          });
          if (isRight) {
            award(5);
            feedback.className = "fb ok"; feedback.textContent = L.correct;
          } else {
            node.className = "pick bad"; wrong(node);
            var answerText = q.options.filter(function (o) { return o.id === q.answer; })[0].text;
            feedback.className = "fb bad"; feedback.textContent = L.wrong.replace("{answer}", answerText);
          }
          update(); summary();
        });
        wrapper.appendChild(node);
      });
      wrapper.appendChild(feedback);
      box.appendChild(wrapper);
    });
    box.appendChild(result);
    summary();
    return box;
  }

  // ---- Write --------------------------------------------------------------
  function viewWrite() {
    var box = el("div");
    box.appendChild(el("p", { class: "intro", text: L.write_intro }));
    if (data.frame) {
      box.appendChild(el("p", { class: "example", text: L.frame + ": " + data.frame }));
    }
    data.terms.forEach(function (t) {
      var areaId = "write-" + t.id;
      var area = el("textarea", { id: areaId, rows: "2" });
      var button = el("button", { type: "button", class: "btn", text: L.done });
      button.addEventListener("click", function () {
        if (state.written[t.id]) return;
        state.written[t.id] = true; button.disabled = true; button.textContent = L.done_ok;
        award(10); say(L.correct);
      });
      box.appendChild(el("div", { class: "card" }, [
        el("label", { for: areaId, text: L.write_prompt.replace("{term}", t.term) }),
        area,
        el("div", { class: "field" }, [button])
      ]));
    });
    return box;
  }

  // ---- Badges + shell -----------------------------------------------------
  var badgeBox = el("div", { class: "badges", "aria-live": "polite" });
  function renderBadges() {
    badgeBox.textContent = "";
    var earned = [];
    if (state.matchAll) earned.push(L.badge_match);
    if (data.quiz.length && state.quizRight === data.quiz.length) earned.push(L.badge_quiz);
    if (state.score >= 50) earned.push(L.badge_score);
    earned.forEach(function (name) { badgeBox.appendChild(el("span", { class: "badge", text: name })); });
  }

  var views = [{ id: "learn", label: L.tab_learn, render: viewLearn }];
  if (data.terms.length >= 2) views.push({ id: "match", label: L.tab_match, render: viewMatch });
  if (data.fill.length) views.push({ id: "fill", label: L.tab_fill, render: viewFill });
  if (data.quiz.length) views.push({ id: "quiz", label: L.tab_quiz, render: viewQuiz });
  views.push({ id: "write", label: L.tab_write, render: viewWrite });

  var tabs = document.getElementById("tabs");
  tabs.setAttribute("aria-label", L.tabs);
  var tabNodes = {};
  var current = null;
  // Typed answers live in the DOM, so keep each view's node and swap visibility.
  var panels = {};
  function show(id) {
    current = id;
    views.forEach(function (view) {
      var selected = view.id === id;
      tabNodes[view.id].setAttribute("aria-selected", selected ? "true" : "false");
      tabNodes[view.id].setAttribute("tabindex", selected ? "0" : "-1");
      if (!panels[view.id]) {
        panels[view.id] = el("section", { id: "panel-" + view.id, role: "tabpanel", "aria-labelledby": "tab-" + view.id });
        panels[view.id].appendChild(view.render());
        main.appendChild(panels[view.id]);
      }
      panels[view.id].hidden = !selected;
    });
    say("");
  }
  views.forEach(function (view, index) {
    var node = el("button", { type: "button", role: "tab", id: "tab-" + view.id, "aria-controls": "panel-" + view.id, text: view.label });
    node.addEventListener("click", function () { show(view.id); });
    node.addEventListener("keydown", function (event) {
      var next = null;
      if (event.key === "ArrowRight") next = views[(index + 1) % views.length];
      if (event.key === "ArrowLeft") next = views[(index + views.length - 1) % views.length];
      if (next) { event.preventDefault(); show(next.id); tabNodes[next.id].focus(); }
    });
    tabNodes[view.id] = node; tabs.appendChild(node);
  });

  document.getElementById("title").textContent = L.title + ": " + data.topic +
    (data.level ? " (" + data.level + ")" : "");
  document.getElementById("score-label").textContent = L.points;
  var footer = document.getElementById("footer");
  footer.appendChild(el("p", { text: L.source_note }));
  footer.appendChild(el("p", { text: L.privacy_note }));
  main.appendChild(badgeBox);
  show("learn");
  update();
})();
"""
