"""The FOV language standard as it reaches the model, and the readability pass
that runs before the truth gate.

CrewAI and the truth gate are replaced with doubles, so these tests pin the
prompt contract and the order of operations without an API key.
"""

import json
from types import SimpleNamespace

import pytest

from ScriptoriumFOV.backend import agents
from ScriptoriumFOV.backend.level_readability import SENTENCE_LIMITS
from Skoleverksted.backend.platform import quality_gate
from Skoleverksted.backend.platform.models import TruthPassport
from Skoleverksted.backend.platform.quality_gate import QualityGateResult, content_digest

LONG_TEXT = (
    "Jorda er 4,5 milliarder år gammel og de første cellene kom for 3,8 milliarder år siden, "
    "og de var veldig enkle og små.\n\nDyrene kom mye senere."
)
SIMPLIFIED = (
    "Jorda er 4,5 milliarder år gammel. De første cellene kom for 3,8 milliarder år siden. "
    "De var veldig enkle og små.\n\nDyrene kom mye senere."
)
WORKSHEET = "a) VIKTIGE BEGREPER\nFossil: En gammel rest av et dyr."


# ---------------------------------------------------------------------------
# Level rules in the prompt
# ---------------------------------------------------------------------------


def test_prompt_targets_never_exceed_what_the_checker_accepts():
    for level, limit in SENTENCE_LIMITS.items():
        assert agents.LEVEL_CONSTRAINTS[level]["max_sentence_words"] <= limit


def test_a2_prompt_names_the_forbidden_constructions_and_shows_a_model_sentence():
    block = agents.format_level_constraints("A2.1", False)
    for expected in ("relativsetninger med «som»", "nominalisering", "tankestrek", "Riktig A2", "Feil A2"):
        assert expected in block
    assert "Maks 6 nye fagord per side" in block


def test_a1_prompt_requires_subject_verb_object_and_caps_new_terms():
    block = agents.format_level_constraints("A1.1", False)
    assert "subjekt–verb–objekt" in block
    assert "Maks 4 nye fagord per side" in block


def test_b1_prompt_allows_relative_clauses_and_has_no_new_term_cap():
    block = agents.format_level_constraints("B1.1", False)
    assert "relativsetninger" in block
    assert "nye fagord per side" not in block
    assert "Riktig B1" not in block


def test_english_requirements_are_unchanged():
    block = agents.format_level_constraints("A2.1", True)
    assert "LANGUAGE REQUIREMENTS" in block
    assert "nye fagord" not in block


# ---------------------------------------------------------------------------
# generate_lesson_content with CrewAI and the truth gate replaced
# ---------------------------------------------------------------------------


class _FakeLLM:
    def __init__(self, reply: str = SIMPLIFIED):
        self.reply = reply
        self.prompts: list[str] = []

    def call(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.reply


@pytest.fixture
def harness(monkeypatch):
    """Run generate_lesson_content with doubles; returns a dict of captured state."""
    state = {"tasks": [], "gate_inputs": [], "text": LONG_TEXT, "llm": _FakeLLM()}

    class FakeTask:
        def __init__(self, **kwargs):
            self.description = kwargs.get("description", "")
            self.output = None
            state["tasks"].append(self)

    class FakeCrew:
        def __init__(self, agents, tasks, **_kwargs):
            self.tasks = tasks

        def kickoff(self):
            for task in self.tasks:
                description = task.description
                if "Skriv en pedagogisk tekst" in description or "Write an educational text" in description:
                    raw = state["text"]
                elif "lag et arbeidsark" in description or "create a worksheet" in description:
                    raw = WORKSHEET
                else:
                    raw = json.dumps({"grammar_tasks": [], "vocabulary_tasks": [], "syntax_tasks": []})
                task.output = SimpleNamespace(raw=raw)

    def fake_gate(**kwargs):
        content = kwargs["content"]
        state["gate_inputs"].append(content)
        passport = TruthPassport(
            version="3.0",
            status="verified",
            content_revision=content_digest(content),
            claims=[],
            sources=[],
            register_complete=True,
        )
        return QualityGateResult(
            approved_content=content,
            passport=passport,
            rounds=[],
            quarantine=[],
            stop_reason="source_approved",
            deterministic_failures=[],
            release_manifest=None,
        )

    monkeypatch.setattr(agents, "_initialized", True)
    monkeypatch.setattr(agents, "_llm", state["llm"])
    # Another test initialises the agents with dict doubles and leaves them
    # behind; pin plain, hashable stand-ins so this harness never depends on it.
    for name in ("content_creator", "pedagogical_developer", "language_exercise_creator"):
        monkeypatch.setattr(agents, name, object())
    monkeypatch.setattr(agents, "_lesson_cache", {})
    monkeypatch.setattr(agents, "Task", FakeTask)
    monkeypatch.setattr(agents, "Crew", FakeCrew)
    monkeypatch.setattr(quality_gate, "run_quality_pipeline", fake_gate)
    monkeypatch.delenv("FOV_READABILITY_REPAIR", raising=False)
    return state


def _description(state, marker: str) -> str:
    return next(task.description for task in state["tasks"] if marker in task.description)


def test_a2_text_task_carries_the_framework_rules_and_the_cultural_checklist(harness):
    agents.generate_lesson_content(topic="Livets historie", subject="Naturfag", level="A2.1")

    text_task = _description(harness, "Skriv en pedagogisk tekst")
    assert "Riktig A2" in text_task
    assert "Kulturell representasjon" in text_task
    assert "aldersadekvate" in text_task


def test_a1_worksheet_asks_for_few_terms_short_definitions_starters_and_imperatives(harness):
    agents.generate_lesson_content(topic="Livets historie", subject="Naturfag", level="A1.1")

    worksheet = _description(harness, "lag et arbeidsark")
    assert "Velg 3–4 nøkkelord" in worksheet
    assert "maks 8 ord" in worksheet
    assert 'Format: "Begrep: definisjon"' in worksheet
    assert "Start slik:" in worksheet
    assert "korte imperativ" in worksheet


def test_b1_worksheet_has_no_discussion_starters_and_allows_more_terms(harness):
    agents.generate_lesson_content(topic="Livets historie", subject="Naturfag", level="B1.1")

    worksheet = _description(harness, "lag et arbeidsark")
    assert "Velg 5–7 nøkkelord" in worksheet
    assert "Start slik:" not in worksheet


def test_writing_frame_is_pitched_at_the_level(harness):
    options = {"writing_frame": True}
    agents.generate_lesson_content(topic="Livets historie", subject="Naturfag", level="A2.2", options=options)

    assert "Hovedårsaken til ___ er ___ fordi ___." in _description(harness, "lag et arbeidsark")


def test_overlong_sentences_are_split_before_the_truth_gate_sees_the_text(harness):
    result = agents.generate_lesson_content(topic="Livets historie", subject="Naturfag", level="A2.1")

    assert len(harness["llm"].prompts) == 1
    assert json.loads(harness["gate_inputs"][0])["text"] == SIMPLIFIED
    assert result["text"] == SIMPLIFIED
    assert result["readability"]["status"] == "ok"
    assert result["readability"]["auto_simplified"] is True
    assert result["prompt_version"] == "norsk-v3-fov"


def test_the_rewrite_can_be_switched_off(harness, monkeypatch):
    monkeypatch.setenv("FOV_READABILITY_REPAIR", "0")

    result = agents.generate_lesson_content(topic="Livets historie", subject="Naturfag", level="A2.1")

    assert harness["llm"].prompts == []
    assert result["text"] == LONG_TEXT
    assert result["readability"]["status"] == "needs_attention"
    assert result["readability"]["auto_simplified"] is False


def test_a_failing_model_call_keeps_the_text_and_still_reports(harness):
    class Broken:
        def call(self, _prompt):
            raise RuntimeError("quota exhausted")

    agents._llm = Broken()

    result = agents.generate_lesson_content(topic="Livets historie", subject="Naturfag", level="A2.1")

    assert result["text"] == LONG_TEXT
    assert result["readability"]["status"] == "needs_attention"
    assert result["readability"]["auto_simplified"] is False


def test_english_subjects_are_not_rewritten(harness):
    harness["text"] = "Cells were simple and small and they lived in the sea long before any animals appeared."

    result = agents.generate_lesson_content(topic="Life", subject="Engelsk", level="A2.1")

    assert harness["llm"].prompts == []
    assert result["readability"]["auto_simplified"] is False


def test_a_level_without_a_sentence_limit_is_reported_as_not_applicable(harness):
    result = agents.generate_lesson_content(topic="Livets historie", subject="Naturfag", level="B2.1")

    assert harness["llm"].prompts == []
    assert result["readability"]["status"] == "not_applicable"
