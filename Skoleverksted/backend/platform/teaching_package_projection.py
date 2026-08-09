"""The only write path from TeachingPackage to YearPlanPeriod.materials."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import TeachingPackage, YearPlan
from .store import PlatformStore


def project_package_materials(
    store: PlatformStore,
    package: TeachingPackage,
) -> tuple[TeachingPackage, YearPlan]:
    """Atomically project approved artifact references to the source period.

    Content, passports, prompts and revision history stay canonical on the
    package. The year plan receives only a file reference and display metadata.
    """
    plan = store.get_year_plan(package.year_plan_id)
    if plan is None:
        raise ValueError("Årsplanen finnes ikke lenger.")
    return store.apply_teaching_package_projection(package, plan)


def retract_package_materials(store: PlatformStore, package: TeachingPackage) -> YearPlan:
    """Mark old projections for a changed package without deleting the row."""
    plan = store.get_year_plan(package.year_plan_id)
    if plan is None:
        raise ValueError("Årsplanen finnes ikke lenger.")
    with store._exclusive() as conn:  # one deliberate derived-state write path
        row = conn.execute("SELECT payload FROM year_plans WHERE id=?", (plan.id,)).fetchone()
        if row is None:
            raise ValueError("Årsplanen finnes ikke lenger.")
        current = type(plan).model_validate_json(row["payload"])
        period = next((item for item in current.periods if item.id == package.period_id), None)
        if period is None:
            raise ValueError("Årsplanperioden finnes ikke lenger.")
        for material in period.materials:
            if material.source_kind == "teaching_package" and material.teaching_package_id == package.id:
                material.status = "needs_revision"
                material.artifact_status = "needs_revision"
                material.updated_at = material.projected_at = datetime.now(timezone.utc).isoformat()
        current.updated_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE year_plans SET payload=?,updated_at=? WHERE id=?",
            (store._json(current.model_dump(mode="json")), current.updated_at, current.id),
        )
    return current
