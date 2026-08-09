from __future__ import annotations

import json
from pathlib import Path

from Skoleverksted.backend.platform import compendium as compendium_module
from Skoleverksted.backend.platform.compendium import (
    apply_repair_plan,
    content_revision,
    repair_compendium_chapter,
)
from Skoleverksted.backend.platform.models import (
    CompendiumCreate,
    CompendiumChapter,
    RepairPlan,
    TruthPassport,
)
from Skoleverksted.backend.platform.store import PlatformStore
from Skoleverksted.backend.platform.truth import TruthAudit


SOURCE = "https://snl.no/den_franske_revolusjonen"


def _plan(content: str, actions: list[dict]) -> RepairPlan:
    issue_rows = []
    for action in actions:
        issue_rows.append({
            "issue_id": action["issue_id"],
            "claim_id": action["issue_id"],
            "category": "factual",
            "severity": "medium",
            "original_text": action.get("target_text", ""),
            "evidence": action.get("justification", ""),
            "source_refs": action.get("source_refs", []),
            "recommended_action": action["action"],
        })
    return RepairPlan.model_validate({
        "chapter_id": "chapter-1",
        "source_revision": content_revision(content),
        "issues": issue_rows,
        "proposed_actions": actions,
        "expected_result": "Kirurgiske, dokumenterte endringer.",
    })


def test_plan_changes_text_and_preserves_heading_structure() -> None:
    before = (
        "## Aktører\n\n"
        "Robespierre innførte terroren for å kontrollere Frankrike. "
        "De politiske allierte forsvarte unntakstiltak.\n\n"
        "- En påstand uten nødvendig dokumentasjon.\n"
    )
    plan = _plan(before, [
        {
            "issue_id": "qualify",
            "action": "qualify",
            "target_text": "Robespierre innførte terroren for å kontrollere Frankrike.",
            "replacement_text": "Robespierre og hans politiske allierte forsvarte unntakstiltak som nødvendige for å beskytte revolusjonen.",
            "justification": "Kilden støtter den avgrensede formuleringen.",
            "source_refs": [SOURCE],
        },
        {
            "issue_id": "remove",
            "action": "remove",
            "target_text": "En påstand uten nødvendig dokumentasjon.",
            "replacement_text": "",
            "justification": "Påstanden er ikke nødvendig og mangler evidens.",
            "source_refs": [],
        },
    ])

    after, changes = apply_repair_plan(before, plan, trusted_source_urls={SOURCE})

    assert "Robespierre innførte terroren" not in after
    assert "forsvarte unntakstiltak som nødvendige" in after
    assert "En påstand uten nødvendig dokumentasjon." not in after
    assert after.splitlines()[0] == "## Aktører"
    assert [change.result for change in changes] == ["applied", "applied"]


def test_partial_and_ambiguous_targets_are_fail_closed() -> None:
    content = "## Kapittel\n\nRobespierre innførte terroren. Robespierre innførte terroren.\n"
    partial = _plan(content, [{
        "issue_id": "partial",
        "action": "replace",
        "target_text": "innførte terroren",
        "replacement_text": "endret formulering.",
        "justification": "Faglig presisering.",
        "source_refs": [SOURCE],
    }])
    ambiguous = _plan(content, [{
        "issue_id": "ambiguous",
        "action": "remove",
        "target_text": "Robespierre innførte terroren.",
        "replacement_text": "",
        "justification": "Påstanden kan ikke dokumenteres.",
        "source_refs": [],
    }])

    partial_after, partial_changes = apply_repair_plan(
        content, partial, trusted_source_urls={SOURCE}
    )
    ambiguous_after, ambiguous_changes = apply_repair_plan(
        content, ambiguous, trusted_source_urls={SOURCE}
    )

    assert partial_after == content
    assert partial_changes[0].result == "manual_review"
    assert "del av en setning" in partial_changes[0].reason
    assert ambiguous_after == content
    assert ambiguous_changes[0].result == "manual_review"
    assert "flere tekstenheter" in ambiguous_changes[0].reason


def test_unknown_source_cannot_make_a_replace_green() -> None:
    content = "## Kapittel\n\nEn udokumentert historisk påstand.\n"
    plan = _plan(content, [{
        "issue_id": "source",
        "action": "replace",
        "target_text": "En udokumentert historisk påstand.",
        "replacement_text": "En mer avgrenset historisk påstand.",
        "justification": "Dette høres mer presist ut.",
        "source_refs": ["https://example.invalid/oppfunnet"],
    }])

    after, changes = apply_repair_plan(content, plan, trusted_source_urls=set())

    assert after == content
    assert changes[0].action == "source_required"
    assert changes[0].result == "unresolved"


def test_passport_is_invalid_after_content_revision_changes(tmp_path: Path) -> None:
    store = PlatformStore(tmp_path / "platform.sqlite3")
    chapter = CompendiumChapter(
        title="Kapittel",
        content_markdown="## Kapittel\n\n" + ("Dokumentert tekst. " * 20),
        truth_passport=TruthPassport(
            status="verified",
            content_revision=content_revision("## Kapittel\n\n" + ("Dokumentert tekst. " * 20)),
        ),
    )

    # The store computes the authoritative content revision and invalidates a
    # passport whose revision no longer matches the text being persisted.
    compendium = store.create_compendium(CompendiumCreate(
        title="Test",
        topic="Historie",
        chapters=[chapter],
    ))
    updated = chapter.model_copy(update={
        "content_markdown": chapter.content_markdown.replace("Dokumentert", "Ny"),
    })
    saved = store.replace_compendium_chapter(compendium.id, updated)

    assert saved is not None
    assert saved.chapters[0].truth_passport is None


def test_repair_pipeline_applies_plan_and_reaudits_the_new_text(tmp_path: Path, monkeypatch) -> None:
    fixture = json.loads(
        (Path(__file__).parents[3] / "evaluations" / "history_vg2" / "french_revolution_1789_1799" / "input.json").read_text(encoding="utf-8")
    )
    fixture_source = fixture["source_brief"].splitlines()[0]
    before = "## Kapittel\n\nRobespierre innførte terroren for å kontrollere Frankrike. " + (
        "Denne historiske framstillingen gir nødvendig kontekst for elevene. "
    ) * 30
    store = PlatformStore(tmp_path / "platform.sqlite3")
    compendium = store.create_compendium(CompendiumCreate(
        title=fixture["topic"],
        topic=fixture["topic"],
        subject=fixture["subject"],
        level=fixture["level"],
        source_brief=fixture["source_brief"],
        chapters=[CompendiumChapter(
            title="Aktører",
            content_markdown=before,
            status="needs_revision",
            verification_notes=["Påstanden må kvalifiseres."],
        )],
    ))
    chapter = compendium.chapters[0]
    observed: list[str] = []

    def fake_google(_prompt, **kwargs):
        schema = kwargs.get("response_schema", {})
        if "approved" in schema.get("properties", {}):
            return {"approved": True, "notes": [], "unsafe_claims": []}, []
        return {
            "repair_plan": {
                "chapter_id": chapter.id,
                "source_revision": content_revision(before),
                "issues": [{
                    "issue_id": "issue-1",
                    "claim_id": "claim-1",
                    "category": "factual",
                    "severity": "high",
                    "original_text": "Robespierre innførte terroren for å kontrollere Frankrike.",
                    "evidence": "Kilden støtter en mer avgrenset formulering.",
                    "source_refs": [fixture_source],
                    "recommended_action": "qualify",
                }],
                "proposed_actions": [{
                    "issue_id": "issue-1",
                    "action": "qualify",
                    "target_text": "Robespierre innførte terroren for å kontrollere Frankrike.",
                    "replacement_text": "Robespierre og hans politiske allierte forsvarte unntakstiltak som nødvendige for å beskytte revolusjonen.",
                    "justification": "Kilden støtter en mer avgrenset formulering.",
                    "source_refs": [fixture_source],
                }],
                "expected_result": "Fjern en bastant årsaksformulering.",
            },
            "key_facts": [],
            "glossary": [],
            "sources": [],
        }, []

    monkeypatch.setattr(compendium_module, "_call_google_json", fake_google)
    monkeypatch.setattr(
        compendium_module,
        "audit_truth",
        lambda **kwargs: TruthAudit(
            content=kwargs["content"],
            passport=TruthPassport(
                status="verified",
                coverage_percent=100,
                verified_claims=2,
                total_claims=2,
            ),
        ),
    )

    repaired = repair_compendium_chapter(
        compendium,
        chapter.id,
        observer=lambda stage, _data: observed.append(stage),
    )

    assert repaired.content_markdown != before.strip()
    assert "Robespierre innførte terroren" not in repaired.content_markdown
    assert repaired.repair_summary is not None
    assert repaired.repair_summary.qualified_count == 1
    assert repaired.repair_summary.before.coverage == 0
    assert repaired.repair_summary.after.coverage == 100
    assert repaired.truth_passport is not None
    assert repaired.truth_passport.content_revision == content_revision(repaired.content_markdown)
    assert "repair_plan_applied" in observed
    assert "truth_audit" in observed
