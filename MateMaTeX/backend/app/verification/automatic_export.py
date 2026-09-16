"""Automatic export approval issued only by server-side checks of exact content."""

from app.verification.math_checker import MathChecker
from Skoleverksted.backend.platform.quality_gate import (
    content_digest, require_export_ready, run_quality_pipeline,
)


def verify_automatic_math_export(*, content: str, export_id: str, topic: str):
    math = MathChecker().verify(content)
    if not math.all_correct or math.claims_incorrect or math.claims_unparseable:
        raise PermissionError("Automatisk matematikkontroll er ikke bestått. Dokumentet må repareres før eksport.")
    quality = run_quality_pipeline(
        generator_id="matematikk.material", content=content,
        topic=topic or "Matematikk", subject="Matematikk", level="VGS",
    )
    if quality.approved_content != content or quality.quarantine:
        raise PermissionError("Sluttkontrollen krever reparasjon og ny kontroll av dokumentet før eksport.")
    require_export_ready(
        export_id=export_id, content=content,
        verification_status=quality.passport.status,
        verified_revision=quality.passport.content_revision,
        verification_version=quality.passport.version,
        teacher_approved=False, approved_revision="",
        automatic_approved_revision=content_digest(content),
        release_manifest=quality.release_manifest.model_dump(mode="json") if quality.release_manifest else None,
    )
    return quality
