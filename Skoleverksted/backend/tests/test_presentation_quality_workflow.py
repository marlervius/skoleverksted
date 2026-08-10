import tempfile
from pathlib import Path
from unittest.mock import patch

from Skoleverksted.backend.platform.models import (
    Job,
    QualityPassport,
    QualityQuarantineItem,
    TeachingArtifactFile,
    TruthClaim,
    TruthPassport,
    TruthSource,
    YearPlanCreate,
    YearPlanPeriod,
)
from Skoleverksted.backend.platform.quality_gate import run_quality_pipeline
from Skoleverksted.backend.platform.router import (
    approve_teaching_artifact,
    approve_teaching_package,
    approve_teaching_package_with_exceptions,
    download_teaching_artifact,
    remove_teaching_claim,
    update_teaching_artifact,
)
from Skoleverksted.backend.platform.store import PlatformStore
from Skoleverksted.backend.platform.teaching_package import build_package_from_period, content_digest
from Skoleverksted.backend.platform.truth import TruthAudit


SOURCE = TruthSource(
    title="Stortinget 1905",
    url="https://www.stortinget.no/no/Stortinget-og-demokratiet/Historikk/1905/",
    origin="teacher",
    fetch_status="provided",
)


def passport(status: str, *, claim: TruthClaim | None = None, source: TruthSource | None = None) -> TruthPassport:
    claims = [claim] if claim else []
    return TruthPassport(
        version="2.0",
        status=status,  # type: ignore[arg-type]
        topic="Unionsoppløsningen",
        subject="Historie",
        coverage_percent=100 if status == "verified" else 0,
        verified_claims=1 if status == "verified" else 0,
        total_claims=len(claims),
        claims=claims,
        sources=[source] if source else [],
        summary="Kontrollresultat",
    )


def make_package(store: PlatformStore, *, content: str, status: str = "needs_review"):
    period = YearPlanPeriod(
        title="Unionsoppløsningen",
        theme="Unionsoppløsningen",
        overview="Et historisk tema med kildearbeid og elevaktivitet.",
        learning_goals=["Forklare sentrale sammenhenger."],
        key_concepts=["union", "kilde"],
    )
    plan = store.create_year_plan(
        YearPlanCreate(
            title="Historie VG2",
            subject="Historie",
            level="VG2",
            school_year="2026-2027",
            periods=[period],
        )
    )
    package = build_package_from_period(plan, plan.periods[0], artifact_types=["presentation"], sources=[SOURCE])
    artifact = package.artifacts[0]
    artifact.content_markdown = content
    artifact.content_revision = content_digest(content)
    artifact.status = status  # type: ignore[assignment]
    artifact.quality_passport = QualityPassport(
        module="teaching-package", title=artifact.title, overall_status="passed", score=100, checks=[]
    )
    store.create_teaching_package(package)
    return package, artifact


def test_wrong_claim_is_repaired_and_verified_in_next_round():
    original = "## Historie\n\nUnionen ble oppløst i 1906. Dette er en lang nok tekst for kontroll."
    corrected = "## Historie\n\nUnionen ble oppløst i 1905. Dette er en lang nok tekst for kontroll."
    unsupported = TruthClaim(
        claim="Unionen ble oppløst i 1906.",
        exact_text="Unionen ble oppløst i 1906.",
        status="unsupported",
        action="qualify",
        replacement="Unionen ble oppløst i 1905.",
    )
    verified = TruthClaim(
        claim="Unionen ble oppløst i 1905.",
        exact_text="Unionen ble oppløst i 1905.",
        status="verified",
        source_urls=[SOURCE.url],
        evidence="Stortinget dokumenterer unionsoppløsningen.",
        confidence=0.99,
    )
    calls = iter([
        TruthAudit(original.replace("1906", "1905"), passport("needs_review", claim=unsupported)),
        TruthAudit(corrected, passport("verified", claim=verified, source=SOURCE)),
    ])
    result = run_quality_pipeline(
        generator_id="platform.teaching_package.presentation",
        content=original,
        topic="Unionsoppløsningen",
        subject="Historie",
        level="VG2",
        provided_sources=[SOURCE],
        audit=lambda **_: next(calls),
    )
    assert result.source_approved
    assert result.approved_content == corrected
    assert len(result.rounds) == 2


def test_unsupported_claim_can_be_replaced_by_documentable_text():
    original = "## Tema\n\nAlle historikere er enige om at dette skjedde slik. Dette er tekst nok til kontroll."
    replacement = "## Tema\n\nKilder kan gi ulike forklaringer på dette. Dette er tekst nok til kontroll."
    unsupported = TruthClaim(
        claim="Alle historikere er enige om at dette skjedde slik.",
        exact_text="Alle historikere er enige om at dette skjedde slik.",
        status="unsupported",
        action="qualify",
        replacement="Kilder kan gi ulike forklaringer på dette.",
    )
    verified = TruthClaim(
        claim="Kilder kan gi ulike forklaringer på dette.",
        exact_text="Kilder kan gi ulike forklaringer på dette.",
        status="verified",
        source_urls=[SOURCE.url],
        evidence="Kilden viser at historiske forklaringer må vurderes mot dokumentasjon.",
        confidence=0.9,
    )
    calls = iter([
        TruthAudit(replacement, passport("needs_review", claim=unsupported)),
        TruthAudit(replacement, passport("verified", claim=verified, source=SOURCE)),
    ])
    result = run_quality_pipeline(
        generator_id="platform.teaching_package.presentation",
        content=original,
        topic="Tema",
        subject="Historie",
        level="VG2",
        audit=lambda **_: next(calls),
    )
    assert result.source_approved
    assert "Alle historikere" not in result.approved_content
    assert "Kilder kan gi ulike" in result.approved_content


def test_no_progress_stops_and_leaves_teacher_reviewable_claim():
    content = "## Tema\n\nDette er en påstand som fortsatt trenger dokumentasjon. Mer tekst gjør kontroll mulig."
    claim = TruthClaim(
        claim="Dette er en påstand som fortsatt trenger dokumentasjon.",
        exact_text="påstand som fortsatt trenger dokumentasjon",
        status="unsupported",
        action="qualify",
        evidence="Ingen konkret støtte funnet.",
    )
    result = run_quality_pipeline(
        generator_id="platform.teaching_package.presentation",
        content=content,
        topic="Tema",
        subject="Historie",
        level="VG2",
        audit=lambda **_: TruthAudit(content, passport("needs_review", claim=claim)),
    )
    assert result.passport.status == "needs_review"
    assert len(result.rounds) <= 2
    assert "fremgang" in result.stop_reason.lower()


def test_edit_remove_approve_and_download_are_version_bound():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        content = "## Historie\n\nEn udokumentert påstand står her. Dette er nok tekst til kontroll."
        package, artifact = make_package(store, content=content)
        unresolved = TruthClaim(
            claim="En udokumentert påstand står her.",
            exact_text="En udokumentert påstand står her.",
            status="unsupported",
            action="remove",
            evidence="Ingen kilde.",
        )
        artifact.truth_passport = passport("needs_review", claim=unresolved)
        artifact.files = [TeachingArtifactFile(
            format="pptx",
            filename="presentasjon.pptx",
            mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            digest="a" * 64,
            storage_key=f"{package.id}/r1/{artifact.id}.pptx",
            package_revision=1,
        )]
        (store.teaching_packages_dir / artifact.files[0].storage_key).parent.mkdir(parents=True, exist_ok=True)
        (store.teaching_packages_dir / artifact.files[0].storage_key).write_bytes(b"approved-pptx-r1")
        store.save_teaching_package(package)
        with patch("Skoleverksted.backend.platform.router.get_platform_store", return_value=store):
            edited = update_teaching_artifact(package.id, artifact.id, type("Edit", (), {"model_dump": lambda self, **_: {"content_markdown": content + "\nNy presisering.", "status": None}})())
            assert edited.status == "needs_revision"
            assert edited.approved_at is None
            edited_artifact = edited.artifacts[0]
            edited_artifact.truth_passport = passport("needs_review", claim=unresolved)
            store.save_teaching_package(edited)
            removed = remove_teaching_claim(package.id, artifact.id, unresolved.id)
            assert "En udokumentert påstand" not in removed.artifacts[0].content_markdown

        # Recreate a green current artifact and approve its exact revision.
        current = store.get_teaching_package(package.id)
        assert current is not None
        current_artifact = current.artifacts[0]
        current_artifact.content_markdown = "## Historie\n\nDokumentert historisk innhold. Dette er nok tekst til kontroll."
        current_artifact.content_revision = content_digest(current_artifact.content_markdown)
        current_artifact.truth_passport = passport(
            "verified",
            claim=TruthClaim(
                claim="Dokumentert historisk innhold.",
                exact_text="Dokumentert historisk innhold.",
                status="verified",
                source_urls=[SOURCE.url],
                evidence="Kilden støtter påstanden.",
                confidence=0.9,
            ),
            source=SOURCE,
        )
        current_artifact.truth_passport.content_revision = current_artifact.content_revision
        current_artifact.quality_passport = QualityPassport(module="teaching-package", title=current_artifact.title, overall_status="passed", score=100, checks=[])
        current_artifact.status = "needs_review"
        current.package_revision += 1
        current_artifact.package_revision = current.package_revision
        current_artifact.files = [TeachingArtifactFile(
            format="pptx", filename="presentasjon-r2.pptx", mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            digest="b" * 64, storage_key=f"{current.id}/r{current.package_revision}/{current_artifact.id}.pptx", package_revision=current.package_revision,
        )]
        path = store.teaching_packages_dir / current_artifact.files[0].storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"approved-pptx-r2")
        store.save_teaching_package(current)
        with patch("Skoleverksted.backend.platform.router.get_platform_store", return_value=store):
            approved = approve_teaching_artifact(current.id, type("Approval", (), {"teacher": "Lærer"})(), current_artifact.id)
            approved = approve_teaching_package(approved.id, type("Approval", (), {"teacher": "Lærer"})())
            assert approved.status == "approved"
            response = download_teaching_artifact(approved.id, current_artifact.id, "pptx")
            assert response.body == b"approved-pptx-r2"
            assert response.headers["x-package-revision"] == str(approved.package_revision)


def test_quarantined_omission_requires_explicit_teacher_confirmation():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlatformStore(Path(tmp) / "platform.sqlite3")
        package, artifact = make_package(store, content="## Tema\n\nKontrollert innhold som er klart for bruk.")
        artifact.truth_passport = passport("verified")
        artifact.truth_passport.content_revision = artifact.content_revision
        artifact.quarantine = [QualityQuarantineItem(
            claim_id="omission-1",
            original_text="Uavklart påstand.",
            reason="Ingen kilde.",
            omission_consequence="Påstanden er ikke med i elevmaterialet.",
        )]
        artifact.status = "approved"
        artifact.approved_revision = artifact.content_revision
        artifact.approved_digest = content_digest(artifact.content_markdown)
        artifact.files = [TeachingArtifactFile(format="pptx", filename="presentasjon.pptx", mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", digest="c" * 64, storage_key=f"{package.id}/r1/{artifact.id}.pptx", package_revision=1)]
        path = store.teaching_packages_dir / artifact.files[0].storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"pptx")
        store.save_teaching_package(package)
        with patch("Skoleverksted.backend.platform.router.get_platform_store", return_value=store):
            try:
                approve_teaching_package(package.id, type("Approval", (), {"teacher": "Lærer"})())
                assert False, "normal approval must remain blocked"
            except Exception as exc:
                assert "karantenepunkter" in str(getattr(exc, "detail", exc))
            approved = approve_teaching_package_with_exceptions(
                package.id,
                type("Approval", (), {"teacher": "Lærer", "confirm": True, "reason": "Jeg har lest utelatelsen og vurdert konsekvensen."})(),
            )
            assert approved.status == "approved"
            assert approved.approval_history[-1].action == "approved_with_exceptions"
            response = download_teaching_artifact(approved.id, artifact.id, "pptx")
            assert response.body == b"pptx"


def test_truth_source_attempts_never_upgrade_unobserved_model_url(monkeypatch):
    content = "## Tema\n\nUnionen ble oppløst i 1905. Dette er ekstra tekst slik at hele påstanden kan kontrolleres trygt."

    def fake_call(*_args, **_kwargs):
        return ({"summary": "", "claims": [{
            "claim": "Unionen ble oppløst i 1905.",
            "exact_text": "Unionen ble oppløst i 1905.",
            "status": "verified",
            "action": "keep",
            "replacement": "",
            "source_urls": ["https://invented.example/source"],
            "evidence": "Oppdiktet kildestøtte.",
            "confidence": 0.99,
        }]}, [])

    monkeypatch.setattr("Skoleverksted.backend.platform.compendium._call_google_json", fake_call)
    from Skoleverksted.backend.platform.truth import audit_truth

    result = audit_truth(content=content, topic="Tema", subject="Historie", level="VG2")
    assert result.passport.claims[0].status == "unsupported"
    assert result.passport.status == "source_unavailable"
