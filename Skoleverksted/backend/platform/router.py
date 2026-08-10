from __future__ import annotations

import logging
import io
import zipfile
from urllib.parse import quote, urlencode
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from .models import (
    Compendium,
    CompendiumChapter,
    CompendiumChapterUpdate,
    CompendiumPlanRequest,
    CompendiumUpdate,
    Job,
    Feedback,
    FeedbackCreate,
    Project,
    ProjectCreate,
    ProjectUpdate,
    QualityPassport,
    QualityPassportRequest,
    TruthPassport,
    RepairJob,
    RepairJobAccepted,
    RepairLedgerEntry,
    ThemePack,
    ThemePackRequest,
    ThemePackTask,
    YearPlan,
    YearPlanCreate,
    YearPlanGenerateRequest,
    YearPlanMaterialCreate,
    YearPlanMaterialUpdate,
    YearPlanPeriodUpdate,
    YearPlanUpdate,
    TeachingApprovalRequest,
    TeachingApprovalRecord,
    TeachingArtifactUpdate,
    TeachingPackage,
    TeachingPackageCreate,
    TeachingPackageUpdate,
    TeachingPackageJobAccepted,
    TeachingArtifactJobAccepted,
    utc_now,
)
from .compendium import (
    _source_quality_notes,
    generate_compendium_chapter,
    plan_compendium,
)
from .compendium_renderer import render_compendium
from .images import resolve_image
from .quality import build_quality_passport
from .quality_gate import content_digest as gate_content_digest, require_export_ready, run_quality_pipeline, source_approval_reasons
from .repair import RepairConflictError, get_repair_service
from .store import get_platform_store
from .queue import get_durable_job_queue
from .year_planner import build_year_plan
from .truth import TruthAudit
from .teaching_package import (
    ARTIFACT_TITLES,
    aggregate_package_status,
    build_package_from_period,
    can_approve_artifact,
    can_approve_package,
    can_approve_package_with_exceptions,
    content_digest,
    with_revision_digest,
    unresolved_claims,
)
from .teaching_package_jobs import (
    cancel_teaching_job,
    start_artifact_worker,
    start_package_worker,
)
from .teaching_package_projection import project_package_materials, retract_package_materials
from .store import ProjectedMaterialError


router = APIRouter(tags=["platform"])

logger = logging.getLogger(__name__)


def _operation_id(request: Request) -> str:
    """One teacher action = one operation id; a replay reuses the same job."""
    header = (request.headers.get("x-operation-id") or request.headers.get("x-request-id") or "").strip()
    return (header or uuid4().hex)[:80]


@router.get("/compendia", response_model=list[Compendium])
def list_compendia(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = None,
):
    return get_platform_store().list_compendia(limit=limit, status=status)


@router.post("/compendia/outline", response_model=Compendium, status_code=201)
def create_compendium_outline(request: CompendiumPlanRequest):
    proposal = plan_compendium(request)
    return get_platform_store().create_compendium(proposal)


@router.get("/compendia/{compendium_id}", response_model=Compendium)
def get_compendium(compendium_id: str):
    compendium = get_platform_store().get_compendium(compendium_id)
    if compendium is None:
        raise HTTPException(status_code=404, detail="Kompendiet finnes ikke.")
    return compendium


@router.patch("/compendia/{compendium_id}", response_model=Compendium)
def update_compendium(compendium_id: str, request: CompendiumUpdate):
    compendium = get_platform_store().update_compendium(compendium_id, request)
    if compendium is None:
        raise HTTPException(status_code=404, detail="Kompendiet finnes ikke.")
    return compendium


@router.patch("/compendia/{compendium_id}/chapters/{chapter_id}", response_model=Compendium)
def update_compendium_chapter(
    compendium_id: str,
    chapter_id: str,
    request: CompendiumChapterUpdate,
):
    store = get_platform_store()
    compendium = store.get_compendium(compendium_id)
    if compendium is None:
        raise HTTPException(status_code=404, detail="Kompendiet finnes ikke.")
    chapter = next((item for item in compendium.chapters if item.id == chapter_id), None)
    if chapter is None:
        raise HTTPException(status_code=404, detail="Kapitlet finnes ikke.")
    payload = chapter.model_dump()
    changes = request.model_dump(exclude_none=True)
    confirm_omissions = bool(changes.pop("confirm_omissions", False))
    payload.update(changes)
    if "content_markdown" in changes and "status" not in changes:
        payload["status"] = "generated"
    if (
        "content_markdown" in changes
        and changes["content_markdown"] != chapter.content_markdown
    ):
        payload["revision_summary"] = []
        payload["repair_summary"] = None
        payload["truth_passport"] = None
        payload["quarantine"] = []
    requested_status = changes.get("status")
    passport = payload.get("truth_passport")
    passport_status = (
        passport.status
        if hasattr(passport, "status")
        else passport.get("status")
        if isinstance(passport, dict)
        else None
    )
    passport_revision = (
        passport.content_revision
        if hasattr(passport, "content_revision")
        else passport.get("content_revision")
        if isinstance(passport, dict)
        else ""
    )
    if requested_status == "approved" and (
        passport_status != "verified"
        or (
            passport.version if hasattr(passport, "version")
            else passport.get("version", "") if isinstance(passport, dict)
            else ""
        ) != "2.0"
        or passport_revision != chapter.content_revision
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Kapitlet kan ikke godkjennes før faktapasset er grønt. "
                "Kjør «Sjekk og rett automatisk» først."
            ),
        )
    if requested_status == "approved" and payload.get("quarantine") and not confirm_omissions:
        raise HTTPException(
            status_code=409,
            detail="Bekreft at du har lest karantenelisten og godkjenner at punktene utelates.",
        )
    payload["updated_at"] = utc_now()
    updated = store.replace_compendium_chapter(
        compendium_id,
        CompendiumChapter.model_validate(payload),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Kapitlet finnes ikke.")
    return updated


@router.post("/compendia/{compendium_id}/chapters/{chapter_id}/generate", response_model=Compendium)
def produce_compendium_chapter(compendium_id: str, chapter_id: str):
    store = get_platform_store()
    compendium = store.get_compendium(compendium_id)
    if compendium is None:
        raise HTTPException(status_code=404, detail="Kompendiet finnes ikke.")
    try:
        chapter = generate_compendium_chapter(compendium, chapter_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    updated = store.replace_compendium_chapter(compendium_id, chapter)
    if updated is None:
        raise HTTPException(status_code=404, detail="Kapitlet finnes ikke.")
    return updated


def _accepted(job: RepairJob) -> RepairJobAccepted:
    return RepairJobAccepted(
        job_id=job.id,
        operation_id=job.operation_id,
        compendium_id=job.compendium_id,
        chapter_id=job.chapter_id,
        status=job.status,
        status_url=job.status_url,
    )


@router.post(
    "/compendia/{compendium_id}/chapters/{chapter_id}/repair",
    response_model=RepairJobAccepted,
    status_code=202,
)
def repair_compendium_chapter_endpoint(
    compendium_id: str,
    chapter_id: str,
    request: Request,
):
    """Register the repair durably and return immediately.

    No model call happens before this response is sent, so a client timeout or
    a dropped connection can no longer decide the fate of the work.
    """
    compendium = get_platform_store().get_compendium(compendium_id)
    if compendium is None:
        raise HTTPException(status_code=404, detail="Kompendiet finnes ikke.")
    try:
        job = get_repair_service().submit(
            compendium,
            chapter_id,
            operation_id=_operation_id(request),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RepairConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _accepted(job)


@router.get(
    "/compendia/{compendium_id}/chapters/{chapter_id}/repair",
    response_model=RepairJob,
)
def latest_chapter_repair_job(compendium_id: str, chapter_id: str):
    """Lets the page find its repair again after a reload."""
    job = get_platform_store().latest_repair_job(compendium_id, chapter_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingen reparasjon er registrert for kapitlet.")
    return job


@router.get("/repair-jobs/{job_id}", response_model=RepairJob)
def get_repair_job(job_id: str):
    job = get_platform_store().get_repair_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Reparasjonsjobben finnes ikke.")
    return job


@router.get("/repair-jobs/{job_id}/events", response_model=list[RepairLedgerEntry])
def list_repair_job_events(job_id: str, limit: int = Query(default=200, ge=1, le=500)):
    store = get_platform_store()
    if store.get_repair_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Reparasjonsjobben finnes ikke.")
    return store.list_repair_events(job_id, limit=limit)


@router.post("/compendia/{compendium_id}/compile", response_model=Compendium)
def compile_compendium(compendium_id: str):
    store = get_platform_store()
    compendium = store.get_compendium(compendium_id)
    if compendium is None:
        raise HTTPException(status_code=404, detail="Kompendiet finnes ikke.")
    incomplete = [
        chapter.title for chapter in compendium.chapters
        if (
            not chapter.content_markdown.strip()
            or chapter.status != "approved"
            or not chapter.truth_passport
            or chapter.truth_passport.status != "verified"
            or chapter.truth_passport.version != "2.0"
            or chapter.truth_passport.content_revision != chapter.content_revision
        )
    ]
    if incomplete:
        raise HTTPException(
            status_code=409,
            detail="Disse kapitlene må ferdigstilles før dokumentbygging: " + ", ".join(incomplete[:6]),
        )
    source_issues = [
        f"{chapter.title}: {note}"
        for chapter in compendium.chapters
        for note in _source_quality_notes(chapter.sources)
    ]
    if source_issues:
        raise HTTPException(
            status_code=409,
            detail=(
                "Kildesjekken stoppet byggingen. Rett eller oppgrader disse "
                "kildene først: " + "; ".join(source_issues[:6])
            ),
        )
    image = None
    try:
        if compendium.image_mode != "none":
            sample = "\n".join(chapter.content_markdown[:2500] for chapter in compendium.chapters[:3])
            image = resolve_image(
                compendium.image_mode,
                topic=compendium.topic,
                subject=compendium.subject,
                level=compendium.level,
                text=sample,
            )
        pdf, docx, pdf_filename, docx_filename = render_compendium(
            compendium,
            image_path=image.local_path if image and image.local_path else "",
            image_credit=image.credit if image else "",
        )
        saved = store.store_compendium_artifacts(
            compendium_id,
            pdf=pdf,
            docx=docx,
            pdf_filename=pdf_filename,
            docx_filename=docx_filename,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Dokumentbyggingen feilet: {exc}") from exc
    finally:
        if image and image.local_path:
            try:
                from pathlib import Path

                Path(image.local_path).unlink(missing_ok=True)
            except OSError:
                pass
    if saved is None:
        raise HTTPException(status_code=404, detail="Kompendiet finnes ikke.")
    return saved


@router.post("/compendia/{compendium_id}/approve", response_model=Compendium)
def approve_compendium(compendium_id: str):
    store = get_platform_store()
    compendium = store.get_compendium(compendium_id)
    if compendium is None:
        raise HTTPException(status_code=404, detail="Kompendiet finnes ikke.")
    if compendium.status == "approved":
        return compendium
    if any(chapter.status != "approved" for chapter in compendium.chapters):
        raise HTTPException(
            status_code=409,
            detail="Alle kapitler må godkjennes av læreren før kompendiet kan godkjennes.",
        )
    artifact = store.get_compendium_artifact(compendium_id, "pdf")
    if artifact is None:
        raise HTTPException(status_code=409, detail="Bygg PDF-en før kompendiet godkjennes.")
    _, path = artifact
    if compendium.year_plan_id and compendium.period_ids:
        plan = store.get_year_plan(compendium.year_plan_id)
        valid_periods = {period.id for period in plan.periods} if plan else set()
        if not plan or any(period_id not in valid_periods for period_id in compendium.period_ids):
            raise HTTPException(
                status_code=409,
                detail="Valgt årsplan eller periode finnes ikke lenger.",
            )
        pdf = path.read_bytes()
        for period_id in compendium.period_ids:
            result = store.add_year_plan_material(
                compendium.year_plan_id,
                period_id,
                YearPlanMaterialCreate(
                    title=f"Kompendium: {compendium.title}",
                    kind="compendium",
                    status="approved",
                    filename=compendium.pdf_filename,
                    mime_type="application/pdf",
                    notes=f"Godkjent kompendium, versjon {compendium.artifact_version}.",
                ),
                pdf,
            )
            if result is None:
                raise HTTPException(
                    status_code=409,
                    detail="Kunne ikke koble kompendiet til valgt årsplanperiode.",
                )
    approved = store.approve_compendium(compendium_id)
    if approved is None:
        raise HTTPException(status_code=404, detail="Kompendiet finnes ikke.")
    return approved


@router.get("/compendia/{compendium_id}/download/{artifact_type}")
def download_compendium(compendium_id: str, artifact_type: str):
    if artifact_type not in {"pdf", "docx"}:
        raise HTTPException(status_code=404, detail="Ukjent filtype.")
    result = get_platform_store().get_compendium_artifact(compendium_id, artifact_type)
    if result is None:
        raise HTTPException(status_code=404, detail="Dokumentfilen finnes ikke.")
    compendium, path = result
    if compendium.status != "approved":
        raise HTTPException(status_code=409, detail="Kompendiet må være lærer-godkjent før eksport.")
    for chapter in compendium.chapters:
        try:
            require_export_ready(
                export_id=f"platform.compendium.{artifact_type}",
                content=chapter.content_markdown,
                verification_status=chapter.truth_passport.status if chapter.truth_passport else "missing",
                verified_revision=chapter.truth_passport.content_revision if chapter.truth_passport else "",
                verification_version=chapter.truth_passport.version if chapter.truth_passport else "",
                teacher_approved=chapter.status == "approved" and bool(compendium.approved_at),
                approved_revision=chapter.content_revision,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    filename = compendium.pdf_filename if artifact_type == "pdf" else compendium.docx_filename
    mime = (
        "application/pdf"
        if artifact_type == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return Response(
        content=path.read_bytes(),
        media_type=mime,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"compendium-{compendium.id[:8]}.{artifact_type}\"; "
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )


# ---------------------------------------------------------------------------
# TeachingPackage
# ---------------------------------------------------------------------------


def _teaching_job_status_url(job_id: str) -> str:
    return f"/api/platform/jobs/{job_id}"


def _reset_package_approval(package: TeachingPackage, *, teacher: str = "", reason: str = "") -> None:
    if package.approved_at:
        package.approval_history.append(
            TeachingApprovalRecord(
                action="revoked",
                teacher=teacher or package.approved_by,
                package_revision=package.approved_revision or package.package_revision,
                artifact_versions={item.id: item.artifact_version for item in package.artifacts},
                unresolved_claims=unresolved_claims(package),
                reason=reason or "Innholdet eller kvalitetsstatusen ble endret etter godkjenning.",
            )
        )
        package.approval_history = package.approval_history[-50:]
    package.approved_at = None
    package.approved_by = ""
    package.approved_revision = 0
    package.approved_digest = ""


@router.post("/teaching-packages", response_model=TeachingPackage, status_code=201)
def create_teaching_package(request: TeachingPackageCreate):
    store = get_platform_store()
    plan = store.get_year_plan(request.year_plan_id)
    if plan is None:
        raise HTTPException(status_code=409, detail="Årsplanen finnes ikke.")
    period = next((item for item in plan.periods if item.id == request.period_id), None)
    if period is None:
        raise HTTPException(status_code=409, detail="Årsplanperioden finnes ikke.")
    existing = store.list_teaching_packages(
        year_plan_id=request.year_plan_id,
        period_id=request.period_id,
        limit=1,
    )
    if existing and existing[0].status != "archived":
        return existing[0]
    package = build_package_from_period(
        plan,
        period,
        artifact_types=request.artifact_types,
        audience=request.audience,
        source_brief=request.source_brief,
        sources=request.sources,
        title=request.title,
        project_id=request.project_id,
    )
    return store.create_teaching_package(package)


@router.get("/teaching-packages", response_model=list[TeachingPackage])
def list_teaching_packages(
    limit: int = Query(default=50, ge=1, le=200),
    year_plan_id: str | None = None,
    period_id: str | None = None,
    project_id: str | None = None,
):
    return get_platform_store().list_teaching_packages(
        limit=limit,
        year_plan_id=year_plan_id,
        period_id=period_id,
        project_id=project_id,
    )


@router.get("/teaching-packages/{package_id}", response_model=TeachingPackage)
def get_teaching_package(package_id: str):
    package = get_platform_store().get_teaching_package(package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Undervisningspakken finnes ikke.")
    return package


@router.patch("/teaching-packages/{package_id}", response_model=TeachingPackage)
def update_teaching_package(package_id: str, request: TeachingPackageUpdate):
    store = get_platform_store()
    package = store.get_teaching_package(package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Undervisningspakken finnes ikke.")
    changes = request.model_dump(exclude_none=True)
    if not changes:
        return package
    if "audience" in changes:
        package.audience = changes["audience"]
    if "source_brief" in changes:
        package.source_brief = changes["source_brief"]
    source_changed = "sources" in changes and changes["sources"] != package.sources
    if "sources" in changes:
        package.sources = changes["sources"]
    if "artifact_types" in changes:
        package.artifact_types = changes["artifact_types"]
    package.package_revision += 1
    for artifact in package.artifacts:
        artifact.package_revision = package.package_revision
        artifact.status = "needs_revision"
        artifact.approved_at = None
        artifact.approved_by = ""
        artifact.approved_revision = ""
        artifact.approved_digest = ""
        if source_changed:
            artifact.truth_passport = None
            artifact.quality_passport = None
            artifact.files = []
    _reset_package_approval(package, reason="Pakkens kilder eller rammer ble endret.")
    package.status = "needs_revision"
    package.updated_at = utc_now()
    return store.save_teaching_package(with_revision_digest(package))


@router.post(
    "/teaching-packages/{package_id}/generate",
    response_model=TeachingPackageJobAccepted,
    status_code=202,
)
def generate_teaching_package(package_id: str):
    store = get_platform_store()
    package = store.get_teaching_package(package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Undervisningspakken finnes ikke.")
    if package.package_job_id:
        parent = store.get_job(package.package_job_id)
        if parent and parent.status in {"queued", "planning", "generating", "verifying", "rendering"}:
            raise HTTPException(status_code=409, detail="Pakken genereres allerede. Du kan følge statusen her.")
    parent_id = f"pkg:{package.id}:r{package.package_revision}"
    queue = get_durable_job_queue()
    parent = queue.enqueue(
        parent_id,
        module="platform",
        kind="teaching_package",
        payload={"package_id": package.id, "package_revision": package.package_revision},
    )
    child_ids: list[str] = []
    for artifact in package.artifacts:
        child_id = f"art:{package.id}:r{package.package_revision}:{artifact.id}"
        child = queue.enqueue(
            child_id,
            module="platform",
            kind="teaching_artifact",
            payload={
                "package_id": package.id,
                "artifact_id": artifact.id,
                "artifact_type": artifact.artifact_type,
                "package_revision": package.package_revision,
            },
        )
        artifact.status = "generating"
        artifact.artifact_job_id = child.id
        artifact.generation_token = f"{child.id}:{child.attempt}"
        artifact.package_revision = package.package_revision
        child_ids.append(child.id)
    package.package_job_id = parent.id
    package.status = "generating"
    package.approved_at = None
    package.approved_by = ""
    package.approved_revision = 0
    package.approved_digest = ""
    store.save_teaching_package(with_revision_digest(package))
    start_package_worker(package.id, parent.id, child_ids)
    return TeachingPackageJobAccepted(
        package_job_id=parent.id,
        artifact_job_ids=child_ids,
        status=parent.status,
        status_url=_teaching_job_status_url(parent.id),
    )


@router.post(
    "/teaching-packages/{package_id}/artifacts/{artifact_id}/regenerate",
    response_model=TeachingArtifactJobAccepted,
    status_code=202,
)
def regenerate_teaching_artifact(package_id: str, artifact_id: str):
    store = get_platform_store()
    result = store.teaching_artifact(package_id, artifact_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Artefaktet finnes ikke.")
    package, artifact = result
    if artifact.generation_token:
        active = store.get_job(artifact.artifact_job_id or "")
        if active and active.status in {"queued", "planning", "generating", "verifying", "rendering"}:
            raise HTTPException(status_code=409, detail="Dette artefaktet genereres allerede.")
    job_id = f"art:{package.id}:r{package.package_revision}:{artifact.id}"
    job = get_durable_job_queue().enqueue(
        job_id,
        module="platform",
        kind="teaching_artifact",
        payload={"package_id": package.id, "artifact_id": artifact.id, "artifact_type": artifact.artifact_type, "package_revision": package.package_revision},
    )
    artifact.status = "generating"
    artifact.artifact_job_id = job.id
    artifact.generation_token = f"{job.id}:{job.attempt}"
    package.status = "generating"
    package.approved_at = None
    package.approved_by = ""
    package.approved_revision = 0
    package.approved_digest = ""
    store.save_teaching_package(with_revision_digest(package))
    start_artifact_worker(package.id, artifact.id, job.id)
    return TeachingArtifactJobAccepted(job_id=job.id, artifact_id=artifact.id, status=job.status, status_url=_teaching_job_status_url(job.id))


@router.patch("/teaching-packages/{package_id}/artifacts/{artifact_id}", response_model=TeachingPackage)
def update_teaching_artifact(package_id: str, artifact_id: str, request: TeachingArtifactUpdate):
    store = get_platform_store()
    result = store.teaching_artifact(package_id, artifact_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Artefaktet finnes ikke.")
    package, artifact = result
    changes = request.model_dump(exclude_none=True)
    if not changes:
        return package
    if changes.get("status") == "approved":
        raise HTTPException(status_code=409, detail="Godkjenning må gjøres med den eksplisitte godkjenn-handlingen.")
    was_approved = artifact.status == "approved"
    content_changed = "content_markdown" in changes and changes["content_markdown"] != artifact.content_markdown
    if content_changed:
        artifact.previous_content_markdown = artifact.content_markdown
        artifact.revision_count += 1
        artifact.content_markdown = changes["content_markdown"]
        artifact.content_revision = content_digest(artifact.content_markdown)
        artifact.truth_passport = None
        artifact.quality_passport = None
        artifact.quarantine = []
        artifact.files = []
        artifact.approved_at = None
        artifact.approved_by = ""
        artifact.approved_revision = ""
        artifact.approved_digest = ""
    artifact.status = changes.get("status") or "needs_review"
    if not content_changed and (was_approved or "status" in changes):
        artifact.approved_at = None
        artifact.approved_by = ""
        artifact.approved_revision = ""
        artifact.approved_digest = ""
    artifact.generation_token = None
    if content_changed:
        package.package_revision += 1
        for item in package.artifacts:
            item.package_revision = package.package_revision
            if item.id != artifact.id and item.status == "approved":
                item.status = "needs_revision"
                item.approved_at = None
                item.approved_by = ""
                item.approved_revision = ""
                item.approved_digest = ""
    package.status = "needs_revision"
    _reset_package_approval(package, reason="Læreren redigerte eller fjernet en påstand etter godkjenning.")
    updated = store.save_teaching_package(with_revision_digest(package))
    try:
        retract_package_materials(store, updated)
    except ValueError:
        pass
    return updated


@router.post("/teaching-packages/{package_id}/artifacts/{artifact_id}/claims/{claim_id}/remove", response_model=TeachingPackage)
def remove_teaching_claim(package_id: str, artifact_id: str, claim_id: str):
    """Remove one unresolved claim without regenerating the package."""
    store = get_platform_store()
    result = store.teaching_artifact(package_id, artifact_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Artefaktet finnes ikke.")
    package, artifact = result
    claim = next(
        (
            item for item in (artifact.truth_passport.claims if artifact.truth_passport else [])
            if item.id == claim_id and item.status != "verified"
        ),
        None,
    )
    quarantine = next(
        (item for item in artifact.quarantine if item.claim_id == claim_id or item.id == claim_id),
        None,
    )
    if claim is None and quarantine is None:
        raise HTTPException(status_code=404, detail="Den uløste påstanden finnes ikke.")
    content = artifact.content_markdown
    exact_text = claim.exact_text if claim is not None else quarantine.original_text
    if exact_text and content.count(exact_text) == 1:
        content = content.replace(exact_text, "", 1)
    else:
        raise HTTPException(status_code=409, detail="Påstanden kunne ikke fjernes sikkert automatisk. Rediger teksten i stedet.")
    artifact.previous_content_markdown = artifact.content_markdown
    artifact.revision_count += 1
    artifact.content_markdown = content
    artifact.content_revision = content_digest(content)
    artifact.truth_passport = None
    artifact.quality_passport = None
    artifact.files = []
    artifact.status = "needs_review"
    artifact.generation_token = None
    artifact.approved_at = None
    artifact.approved_by = ""
    artifact.approved_revision = ""
    artifact.approved_digest = ""
    package.package_revision += 1
    for item in package.artifacts:
        item.package_revision = package.package_revision
        if item.id != artifact.id and item.status == "approved":
            item.status = "needs_revision"
    _reset_package_approval(package, reason="Læreren fjernet en uløst påstand.")
    package.status = "needs_revision"
    updated = store.save_teaching_package(with_revision_digest(package))
    try:
        retract_package_materials(store, updated)
    except ValueError:
        pass
    return updated


@router.post(
    "/teaching-packages/{package_id}/artifacts/{artifact_id}/verify",
    response_model=TeachingArtifactJobAccepted,
    status_code=202,
)
def verify_teaching_artifact(package_id: str, artifact_id: str):
    store = get_platform_store()
    result = store.teaching_artifact(package_id, artifact_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Artefaktet finnes ikke.")
    package, artifact = result
    if not artifact.content_markdown.strip():
        raise HTTPException(status_code=409, detail="Artefaktet har ikke innhold som kan kontrolleres.")
    job_id = f"verify:{package.id}:r{package.package_revision}:{artifact.id}:{artifact.content_revision[:16]}"
    existing = store.get_job(job_id)
    if existing and existing.status in {"queued", "planning", "generating", "verifying", "rendering"}:
        raise HTTPException(status_code=409, detail="Faktapasset kjører allerede.")
    job = get_durable_job_queue().enqueue(
        job_id,
        module="platform",
        kind="teaching_artifact_verify",
        payload={"package_id": package.id, "artifact_id": artifact.id, "artifact_type": artifact.artifact_type, "package_revision": package.package_revision},
    )
    artifact.status = "generating"
    artifact.artifact_job_id = job.id
    artifact.generation_token = f"{job.id}:{job.attempt}"
    package.status = "generating"
    package.approved_at = None
    package.approved_by = ""
    package.approved_revision = 0
    package.approved_digest = ""
    store.save_teaching_package(with_revision_digest(package))
    start_artifact_worker(package.id, artifact.id, job.id, verify_only=True)
    return TeachingArtifactJobAccepted(job_id=job.id, artifact_id=artifact.id, status=job.status, status_url=_teaching_job_status_url(job.id))


@router.post(
    "/teaching-packages/{package_id}/artifacts/{artifact_id}/repair",
    response_model=TeachingArtifactJobAccepted,
    status_code=202,
)
def repair_teaching_artifact(package_id: str, artifact_id: str):
    """Start the bounded AI analyst/source/editor/control workflow."""
    store = get_platform_store()
    result = store.teaching_artifact(package_id, artifact_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Artefaktet finnes ikke.")
    package, artifact = result
    if not artifact.content_markdown.strip():
        raise HTTPException(status_code=409, detail="Artefaktet har ikke innhold som kan repareres.")
    if artifact.generation_token:
        active = store.get_job(artifact.artifact_job_id or "")
        if active and active.status in {"queued", "planning", "generating", "verifying", "rendering"}:
            raise HTTPException(status_code=409, detail="Kvalitetsflyten kjører allerede.")
    package.package_revision += 1
    for item in package.artifacts:
        item.package_revision = package.package_revision
        if item.id != artifact.id and item.status == "approved":
            item.status = "needs_revision"
            item.approved_at = None
            item.approved_by = ""
            item.approved_revision = ""
            item.approved_digest = ""
    _reset_package_approval(package, reason="AI-reparasjon startet en ny pakkerevisjon.")
    job_id = f"repair:{package.id}:r{package.package_revision}:{artifact.id}:{artifact.content_revision[:16]}"
    job = get_durable_job_queue().enqueue(
        job_id,
        module="platform",
        kind="teaching_artifact_repair",
        payload={
            "package_id": package.id,
            "artifact_id": artifact.id,
            "artifact_type": artifact.artifact_type,
            "package_revision": package.package_revision,
        },
    )
    artifact.status = "generating"
    artifact.artifact_job_id = job.id
    artifact.generation_token = f"{job.id}:{job.attempt}"
    package.status = "generating"
    store.save_teaching_package(with_revision_digest(package))
    start_artifact_worker(package.id, artifact.id, job.id, verify_only=True, quality_repair=True)
    return TeachingArtifactJobAccepted(job_id=job.id, artifact_id=artifact.id, status=job.status, status_url=_teaching_job_status_url(job.id))


@router.post("/teaching-packages/{package_id}/artifacts/{artifact_id}/approve", response_model=TeachingPackage)
def approve_teaching_artifact(package_id: str, request: TeachingApprovalRequest, artifact_id: str):
    store = get_platform_store()
    result = store.teaching_artifact(package_id, artifact_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Artefaktet finnes ikke.")
    package, artifact = result
    reasons = can_approve_artifact(artifact)
    if reasons:
        raise HTTPException(status_code=409, detail="Artefaktet kan ikke godkjennes ennå: " + " ".join(reasons[:6]))
    artifact.status = "approved"
    artifact.approved_by = request.teacher
    artifact.approved_at = utc_now()
    artifact.approved_revision = artifact.content_revision
    artifact.approved_digest = content_digest(artifact.content_markdown)
    package.status = aggregate_package_status(package)
    return store.save_teaching_package(with_revision_digest(package))


@router.post("/teaching-packages/{package_id}/approve", response_model=TeachingPackage)
def approve_teaching_package(package_id: str, request: TeachingApprovalRequest):
    store = get_platform_store()
    package = store.get_teaching_package(package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Undervisningspakken finnes ikke.")
    if unresolved_claims(package):
        raise HTTPException(
            status_code=409,
            detail="Pakken har karantenepunkter. Godkjenn eksplisitt at disse utelates fra eksport.",
        )
    reasons = can_approve_package(package)
    if reasons:
        raise HTTPException(status_code=409, detail="Pakken kan ikke godkjennes ennå: " + " ".join(reasons[:8]))
    package.approved_by = request.teacher
    package.approved_at = utc_now()
    package.approval_history.append(
        TeachingApprovalRecord(
            action="approved",
            teacher=request.teacher,
            at=package.approved_at,
            package_revision=package.package_revision,
            artifact_versions={item.id: item.artifact_version for item in package.artifacts},
            content_hashes={item.id: content_digest(item.content_markdown) for item in package.artifacts},
            verification_statuses={
                item.id: item.truth_passport.status if item.truth_passport else "missing"
                for item in package.artifacts
            },
            source_urls=sorted({
                source.url
                for item in package.artifacts
                for source in (item.truth_passport.sources if item.truth_passport else [])
                if source.url
            }),
            unresolved_claims=[],
            reason=getattr(request, "reason", "") or "Alle obligatoriske artefakter er kildekontrollert og lærer-godkjent.",
        )
    )
    package.approval_history = package.approval_history[-50:]
    try:
        approved, _ = project_package_materials(store, package)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return approved


@router.post("/teaching-packages/{package_id}/approve-with-exceptions", response_model=TeachingPackage)
def approve_teaching_package_with_exceptions(package_id: str, request: TeachingApprovalRequest):
    package = get_platform_store().get_teaching_package(package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Undervisningspakken finnes ikke.")
    if not request.confirm:
        raise HTTPException(
            status_code=409,
            detail=(
                "Bekreft at du har lest karantenelisten og godkjenner at punktene utelates."
            ),
        )
    reasons = can_approve_package_with_exceptions(package)
    if reasons:
        raise HTTPException(status_code=409, detail="Pakken kan ikke godkjennes med utelatelser ennå: " + " ".join(reasons[:8]))
    unsafe_open = [
        f"{artifact.title}: {claim.claim}"
        for artifact in package.artifacts
        for claim in (artifact.truth_passport.claims if artifact.truth_passport else [])
        if claim.status != "verified"
        and claim.id not in {item.claim_id for item in artifact.quarantine}
    ]
    if unsafe_open:
        raise HTTPException(
            status_code=409,
            detail="Påstander som fortsatt finnes i innholdet kan ikke omgås: " + "; ".join(unsafe_open[:6]),
        )
    unresolved = unresolved_claims(package)
    if not unresolved:
        raise HTTPException(status_code=409, detail="Det finnes ingen uløste punkter. Bruk vanlig godkjenning.")
    package.approved_by = request.teacher
    package.approved_at = utc_now()
    # This endpoint acknowledges a safe omission; it is not an alternate
    # responsibility-based approval state. The remaining, exact content has
    # already passed the ordinary artifact approvals and is exported through
    # the same central gate as every other approved package.
    package.status = "approved"
    package.approval_history.append(
        TeachingApprovalRecord(
            action="approved_with_exceptions",
            teacher=request.teacher,
            at=package.approved_at,
            package_revision=package.package_revision,
            artifact_versions={item.id: item.artifact_version for item in package.artifacts},
            content_hashes={item.id: content_digest(item.content_markdown) for item in package.artifacts},
            verification_statuses={
                item.id: item.truth_passport.status if item.truth_passport else "missing"
                for item in package.artifacts
            },
            source_urls=sorted({
                url
                for item in package.artifacts
                for source in (item.truth_passport.sources if item.truth_passport else [])
                for url in [source.url]
                if url
            }),
            omitted_claims=unresolved,
            unresolved_claims=unresolved,
            reason=getattr(request, "reason", "") or "Læreren har lest karantenelisten og godtar at punktene utelates fra eksport.",
        )
    )
    package.approval_history = package.approval_history[-50:]
    try:
        approved, _ = project_package_materials(get_platform_store(), package)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return approved


def _require_teaching_file(package_id: str, artifact_id: str, artifact_format: str):
    if artifact_format not in {"pdf", "docx", "pptx"}:
        raise HTTPException(status_code=404, detail="Ukjent filtype.")
    result = get_platform_store().get_teaching_artifact_file(package_id, artifact_id, artifact_format)
    if result is None:
        raise HTTPException(status_code=404, detail="Filen finnes ikke for denne pakkerevisjonen.")
    package, artifact, file, path = result
    if package.status != "approved" or file.package_revision != package.package_revision:
        raise HTTPException(status_code=409, detail="Filen kan lastes ned etter at riktig pakkerevisjon er godkjent.")
    try:
        require_export_ready(
            export_id=f"platform.teaching_package.{artifact_format}",
            content=artifact.content_markdown,
            verification_status=artifact.truth_passport.status if artifact.truth_passport else "missing",
            verified_revision=artifact.truth_passport.content_revision if artifact.truth_passport else "",
            verification_version=artifact.truth_passport.version if artifact.truth_passport else "",
            teacher_approved=bool(package.approved_at),
            approved_revision=artifact.approved_revision,
            quarantined_texts=[item.original_text for item in artifact.quarantine if item.status == "withheld"],
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return package, artifact, file, path


@router.get("/teaching-packages/{package_id}/artifacts/{artifact_id}/download/{artifact_format}")
def download_teaching_artifact(package_id: str, artifact_id: str, artifact_format: str):
    package, artifact, file, path = _require_teaching_file(package_id, artifact_id, artifact_format)
    return Response(
        content=path.read_bytes(),
        media_type=file.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{file.filename}\"; filename*=UTF-8''{quote(file.filename)}",
            "X-Artifact-Digest": file.digest,
            "X-Package-Revision": str(package.package_revision),
        },
    )


@router.get("/teaching-packages/{package_id}/download/zip")
def download_teaching_package_zip(package_id: str):
    package = get_platform_store().get_teaching_package(package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Undervisningspakken finnes ikke.")
    if package.status != "approved":
        raise HTTPException(status_code=409, detail="Godkjenn pakken før samlet nedlasting.")
    store = get_platform_store()
    output = io.BytesIO()
    included = 0
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for artifact in package.artifacts:
            try:
                require_export_ready(
                    export_id="platform.teaching_package.zip",
                    content=artifact.content_markdown,
                    verification_status=artifact.truth_passport.status if artifact.truth_passport else "missing",
                    verified_revision=artifact.truth_passport.content_revision if artifact.truth_passport else "",
                    verification_version=artifact.truth_passport.version if artifact.truth_passport else "",
                    teacher_approved=bool(package.approved_at),
                    approved_revision=artifact.approved_revision,
                    quarantined_texts=[item.original_text for item in artifact.quarantine if item.status == "withheld"],
                )
            except PermissionError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            for file in artifact.files:
                if file.package_revision != package.package_revision:
                    continue
                path = store.teaching_packages_dir / file.storage_key
                if not path.is_file():
                    continue
                archive.writestr(file.filename, path.read_bytes())
                included += 1
    if not included:
        raise HTTPException(status_code=404, detail="Ingen filer finnes for den godkjente pakkerevisjonen.")
    filename = f"undervisningspakke-{package.id[:8]}-r{package.package_revision}.zip"
    return Response(
        content=output.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/year-plans", response_model=list[YearPlan])
def list_year_plans(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = None,
    school_year: str | None = None,
):
    return get_platform_store().list_year_plans(
        limit=limit,
        status=status,
        school_year=school_year,
    )


@router.post("/year-plans", response_model=YearPlan, status_code=201)
def create_year_plan(request: YearPlanCreate):
    return get_platform_store().create_year_plan(request)


@router.post("/year-plans/generate", response_model=YearPlan, status_code=201)
def generate_year_plan(request: YearPlanGenerateRequest):
    proposal = build_year_plan(request)
    canonical = proposal.model_dump_json(exclude={
        "truth_passport", "quality_rounds", "quarantine", "quality_stop_reason",
        "content_revision", "approved_at", "approved_revision",
    })
    deterministic_audit = None
    if not request.use_ai:
        deterministic_audit = lambda **kwargs: TruthAudit(
            content=kwargs["content"],
            passport=TruthPassport(
                version="2.0",
                status="verified",
                topic=proposal.title,
                subject=proposal.subject,
                coverage_percent=100,
                summary="Deterministisk reserveplan; rammer og mål er lærerinput.",
            ),
        )
    quality = run_quality_pipeline(
        generator_id="platform.year_plan",
        content=canonical,
        topic=proposal.title,
        subject=proposal.subject,
        level=proposal.level,
        **({"audit": deterministic_audit} if deterministic_audit else {}),
    )
    if not quality.source_approved:
        raise HTTPException(status_code=409, detail="Årsplanen ble blokkert av den globale kvalitetskontrollen.")
    try:
        proposal = YearPlanCreate.model_validate_json(quality.approved_content)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Kontrollert årsplan kunne ikke leses som sikker struktur.") from exc
    proposal.truth_passport = quality.passport
    proposal.quality_rounds = quality.rounds
    proposal.quarantine = quality.quarantine
    proposal.quality_stop_reason = quality.stop_reason
    proposal.content_revision = gate_content_digest(quality.approved_content)
    return get_platform_store().create_year_plan(proposal)


@router.post("/year-plans/{plan_id}/approve", response_model=YearPlan)
def approve_year_plan(plan_id: str):
    store = get_platform_store()
    plan = store.get_year_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Årsplanen finnes ikke.")
    if not plan.truth_passport or plan.truth_passport.status != "verified" or plan.truth_passport.version != "2.0":
        raise HTTPException(status_code=409, detail="Årsplanen mangler gyldig global kontroll.")
    plan.approved_at = utc_now()
    plan.approved_revision = plan.content_revision
    plan.updated_at = plan.approved_at
    return store._save_year_plan(plan)


@router.post("/year-plans/{plan_id}/verify", response_model=YearPlan)
def verify_year_plan(plan_id: str):
    store = get_platform_store()
    plan = store.get_year_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Årsplanen finnes ikke.")
    proposal = YearPlanCreate.model_validate(plan.model_dump())
    canonical = proposal.model_dump_json(exclude={
        "truth_passport", "quality_rounds", "quarantine", "quality_stop_reason",
        "content_revision", "approved_at", "approved_revision",
    })
    deterministic_audit = None
    if plan.planning_source == "fallback":
        deterministic_audit = lambda **kwargs: TruthAudit(
            content=kwargs["content"],
            passport=TruthPassport(
                version="2.0",
                status="verified",
                topic=plan.title,
                subject=plan.subject,
                coverage_percent=100,
                summary="Deterministisk reserveplan; rammer og mål er lærerinput.",
            ),
        )
    quality = run_quality_pipeline(
        generator_id="platform.year_plan",
        content=canonical,
        topic=plan.title,
        subject=plan.subject,
        level=plan.level,
        **({"audit": deterministic_audit} if deterministic_audit else {}),
    )
    if not quality.source_approved:
        raise HTTPException(status_code=409, detail="Årsplanen ble blokkert av den globale kvalitetskontrollen.")
    try:
        controlled = YearPlanCreate.model_validate_json(quality.approved_content)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Kontrollert årsplan kunne ikke leses som sikker struktur.") from exc
    refreshed = YearPlan(
        **controlled.model_dump(exclude={
            "truth_passport", "quality_rounds", "quarantine", "quality_stop_reason",
            "content_revision", "approved_at", "approved_revision",
        }),
        id=plan.id,
        status=plan.status,
        created_at=plan.created_at,
        updated_at=utc_now(),
        truth_passport=quality.passport,
        quality_rounds=quality.rounds,
        quarantine=quality.quarantine,
        quality_stop_reason=quality.stop_reason,
        content_revision=gate_content_digest(quality.approved_content),
    )
    return store._save_year_plan(refreshed)


@router.get("/year-plans/{plan_id}", response_model=YearPlan)
def get_year_plan(plan_id: str):
    plan = get_platform_store().get_year_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Årsplanen finnes ikke.")
    return plan


@router.patch("/year-plans/{plan_id}", response_model=YearPlan)
def update_year_plan(plan_id: str, request: YearPlanUpdate):
    plan = get_platform_store().update_year_plan(plan_id, request)
    if plan is None:
        raise HTTPException(status_code=404, detail="Årsplanen finnes ikke.")
    return plan


@router.patch("/year-plans/{plan_id}/periods/{period_id}", response_model=YearPlan)
def update_year_plan_period(plan_id: str, period_id: str, request: YearPlanPeriodUpdate):
    plan = get_platform_store().update_year_plan_period(plan_id, period_id, request)
    if plan is None:
        raise HTTPException(status_code=404, detail="Årsplanen eller perioden finnes ikke.")
    return plan


@router.post("/year-plans/{plan_id}/periods/{period_id}/materials", status_code=201)
async def save_year_plan_material(
    plan_id: str,
    period_id: str,
    request: Request,
    title: str = Query(min_length=2, max_length=180),
    kind: str = Query(default="learning_sheet"),
    status: str = Query(default="approved"),
    filename: str = Query(min_length=1, max_length=240),
    notes: str = Query(default="", max_length=1200),
):
    content = await request.body()
    try:
        metadata = YearPlanMaterialCreate(
            title=title,
            kind=kind,
            status=status,
            filename=filename,
            mime_type=(request.headers.get("content-type") or "application/pdf").split(";", 1)[0],
            notes=notes,
        )
        result = get_platform_store().add_year_plan_material(
            plan_id,
            period_id,
            metadata,
            content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Årsplanen eller perioden finnes ikke.")
    plan, material = result
    return {"plan": plan, "material": material}


@router.patch("/year-plans/{plan_id}/periods/{period_id}/materials/{material_id}")
def update_year_plan_material(
    plan_id: str,
    period_id: str,
    material_id: str,
    request: YearPlanMaterialUpdate,
):
    try:
        result = get_platform_store().update_year_plan_material(
            plan_id,
            period_id,
            material_id,
            request,
        )
    except ProjectedMaterialError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Læremiddelet finnes ikke.")
    plan, material = result
    return {"plan": plan, "material": material}


@router.get("/year-plans/{plan_id}/materials/{material_id}/download")
def download_year_plan_material(plan_id: str, material_id: str):
    result = get_platform_store().get_year_plan_material(plan_id, material_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Læremiddelet eller filen finnes ikke.")
    material, path = result
    if material.status not in {"approved", "used"}:
        raise HTTPException(status_code=409, detail="Læremiddelet må være lærer-godkjent før nedlasting.")
    if material.source_kind == "teaching_package":
        package = get_platform_store().get_teaching_package(material.teaching_package_id or "")
        artifact = next((item for item in (package.artifacts if package else []) if item.id == material.artifact_id), None)
        if package is None or artifact is None:
            raise HTTPException(status_code=409, detail="Kvalitetsopphavet til læremiddelet finnes ikke.")
        try:
            require_export_ready(
                export_id="platform.year_plan.material",
                content=artifact.content_markdown,
                verification_status=artifact.truth_passport.status if artifact.truth_passport else "missing",
                verified_revision=artifact.truth_passport.content_revision if artifact.truth_passport else "",
                verification_version=artifact.truth_passport.version if artifact.truth_passport else "",
                teacher_approved=artifact.status == "approved" and bool(package.approved_at),
                approved_revision=artifact.approved_revision,
                quarantined_texts=[item.original_text for item in artifact.quarantine],
            )
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    filename = "".join(
        character for character in material.filename
        if character not in {'"', "\r", "\n", "\x00"}
    ) or "laeremiddel.pdf"
    return Response(
        content=path.read_bytes(),
        media_type=material.mime_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"material-{material.id[:8]}\"; "
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )


@router.get("/projects", response_model=list[Project])
def list_projects(limit: int = Query(default=50, ge=1, le=200), status: str | None = None):
    return get_platform_store().list_projects(limit=limit, status=status)


@router.post("/projects", response_model=Project, status_code=201)
def create_project(request: ProjectCreate):
    return get_platform_store().create_project(request)


@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: str):
    project = get_platform_store().get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Prosjektet finnes ikke.")
    return project


@router.patch("/projects/{project_id}", response_model=Project)
def update_project(project_id: str, request: ProjectUpdate):
    project = get_platform_store().update_project(project_id, request)
    if project is None:
        raise HTTPException(status_code=404, detail="Prosjektet finnes ikke.")
    return project


@router.get("/jobs", response_model=list[Job])
def list_jobs(limit: int = Query(default=100, ge=1, le=300), project_id: str | None = None):
    return get_platform_store().list_jobs(limit=limit, project_id=project_id)


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str):
    job = get_platform_store().get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Jobben finnes ikke i plattformhistorikken.")
    return job


@router.get("/queue", response_model=list[Job])
def list_queue(limit: int = Query(default=100, ge=1, le=300)):
    store = get_platform_store()
    # A crashed worker must not keep a chapter locked in the visible queue.
    store.expire_stale_repair_leases()
    return [
        job for job in store.list_jobs(limit=limit)
        if job.status in {"queued", "planning", "generating", "verifying", "rendering"}
    ]


@router.post("/jobs/{job_id}/cancel", response_model=Job)
def cancel_job(job_id: str):
    store = get_platform_store()
    if store.get_repair_job(job_id) is not None:
        # Repair owns a chapter lock, so cancelling has to go through its own
        # lifecycle rather than only flipping the shared ledger row.
        get_repair_service().cancel(job_id)
    else:
        job = store.get_job(job_id)
        if job and job.kind.startswith("teaching_"):
            cancel_teaching_job(job_id)
        else:
            get_durable_job_queue().cancel(job_id)
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Jobben finnes ikke i plattformhistorikken.")
    return job


@router.post("/feedback", response_model=Feedback, status_code=201)
def create_feedback(request: FeedbackCreate):
    return get_platform_store().create_feedback(request)


@router.post("/quality-passports", response_model=QualityPassport)
def create_quality_passport(request: QualityPassportRequest):
    return build_quality_passport(request)


@router.post("/theme-packs", response_model=ThemePack, status_code=201)
def create_theme_pack(request: ThemePackRequest):
    store = get_platform_store()
    project_request = ProjectCreate(
        title=request.title,
        theme=request.theme,
        subject=request.subject,
        level=request.level,
        description=request.description,
        competency_goals=request.competency_goals,
        metadata={
            "kind": "theme_pack",
            "norwegian_level": request.norwegian_level,
            "duration_lessons": request.duration_lessons,
            "include_assessment": request.include_assessment,
            "include_teacher_guide": request.include_teacher_guide,
            "source_text": request.source_text,
            "source_name": request.source_name,
        },
    )
    project = store.create_project(project_request, status="ready")
    common = {
        "topic": request.theme,
        "subject": request.subject,
        "level": request.level,
        "project": project.id,
    }
    norwegian_level = request.norwegian_level if "." in request.norwegian_level else f"{request.norwegian_level}.1"
    math_grade = {"VG1": "VG1 1T", "VG2": "VG2 R1", "VG3": "VG3 R2"}.get(request.level, request.level)
    task_specs = [
        (
            "fag",
            f"Fagtekst og undervisningsforløp: {request.theme}",
            f"Lag et kildebelagt undervisningsopplegg for {request.duration_lessons} timer, med elevark"
            + (" og lærerveiledning." if request.include_teacher_guide else "."),
            "/fag?" + urlencode(common),
        ),
        (
            "norsk",
            f"Språktilpasset versjon ({request.norwegian_level})",
            f"Tilpass kjerneteksten og oppgavene til CEFR {request.norwegian_level}, med begrepsstøtte.",
            "/norsk?" + urlencode({**common, "languageLevel": norwegian_level}),
        ),
        (
            "matematikk",
            f"Matematikk og data: {request.theme}",
            "Lag kontekstnære regneoppgaver med maskinelt verifiserbar fasit"
            + (" og vurderingsgrunnlag." if request.include_assessment else "."),
            "/matematikk?" + urlencode({**common, "grade": math_grade, "materialType": "arbeidsark"}),
        ),
    ]
    tasks = [ThemePackTask(id=uuid4().hex, module=module, title=title, brief=brief, href=href) for module, title, brief, href in task_specs]
    # The passport describes the whole plan, so it must see the whole plan.
    # Judging it on the three briefs alone made every theme pack fail the
    # "content present" check and hid the source the teacher supplied.
    plan_text = "\n".join([
        request.title,
        request.theme,
        f"{request.subject} {request.level}",
        request.description,
        *(f"{task.title}: {task.brief}" for task in tasks),
        *request.competency_goals,
    ])
    passport = build_quality_passport(QualityPassportRequest(
        module="platform",
        title=request.title,
        content=plan_text,
        sources=[request.source_name] if request.source_name.strip() else [],
        competency_goals=request.competency_goals,
        has_answer_key=request.include_assessment,
        prompt_version="theme-pack-planner-v1",
    ))
    metadata = dict(project.metadata)
    metadata["tasks"] = [task.model_dump() for task in tasks]
    project = store.update_project(project.id, ProjectUpdate(metadata=metadata)) or project
    guide = _theme_pack_guide(project)
    quality = run_quality_pipeline(
        generator_id="platform.theme_pack.teacher_guide",
        content=guide,
        topic=request.theme,
        subject=request.subject,
        level=request.level,
        provided_sources=([{"title": request.source_name, "content": request.source_text}] if request.source_text.strip() else []),
    )
    metadata = dict(project.metadata)
    metadata["teacher_guide_quality"] = {
        "content": quality.approved_content,
        "truth_passport": quality.passport.model_dump(mode="json"),
        "quality_rounds": [item.model_dump(mode="json") for item in quality.rounds],
        "quarantine": [item.model_dump(mode="json") for item in quality.quarantine],
        "quality_stop_reason": quality.stop_reason,
        "approved_at": None,
        "approved_digest": "",
    }
    project = store.update_project(project.id, ProjectUpdate(metadata=metadata)) or project
    return ThemePack(
        id=uuid4().hex,
        project=project,
        tasks=tasks,
        quality_passport=passport,
        truth_passport=quality.passport,
        quality_rounds=quality.rounds,
        quarantine=quality.quarantine,
        quality_stop_reason=quality.stop_reason,
    )


def _theme_pack_guide(project: Project) -> str:
    tasks = project.metadata.get("tasks", [])
    goals = "\n".join(f"- {goal}" for goal in project.competency_goals) or "- Legg til relevante kompetansemål før bruk."
    task_lines = "\n".join(f"{index}. **{task.get('title', 'Del')}** – {task.get('brief', '')}" for index, task in enumerate(tasks, 1))
    source = project.metadata.get("source_name") or "Ingen felles kilde oppgitt"
    return f"""# {project.title}\n\n## Felles ramme\n\nTema: {project.theme}\n\nFag/nivå: {project.subject} / {project.level}\n\nKilde: {source}\n\n{project.description}\n\n## Kompetansemål\n\n{goals}\n\n## Deler\n\n{task_lines}\n\n## Lærerens sluttkontroll\n\n- Kontroller fakta og kildehenvisninger.\n- Kontroller at språk- og regnenivå passer elevgruppen.\n- Gjennomfør oppgavene og fasiten før utdeling.\n- Tilpass personopplysninger og eksempler til klassen.\n"""


@router.post("/theme-packs/{project_id}/teacher-guide/approve")
def approve_theme_pack_teacher_guide(project_id: str):
    store = get_platform_store()
    project = store.get_project(project_id)
    if project is None or project.metadata.get("kind") != "theme_pack":
        raise HTTPException(status_code=404, detail="Temapakken finnes ikke.")
    quality = dict(project.metadata.get("teacher_guide_quality") or {})
    passport = quality.get("truth_passport") or {}
    reasons = source_approval_reasons(
        content=str(quality.get("content") or ""),
        verification_status=passport.get("status", "missing"),
        verified_revision=passport.get("content_revision", ""),
        verification_version=passport.get("version", ""),
        quarantined_texts=[item.get("original_text", "") for item in quality.get("quarantine", [])],
    )
    if reasons:
        raise HTTPException(status_code=409, detail="Lærerveiledningen kan ikke godkjennes: " + "; ".join(reasons))
    quality["approved_at"] = utc_now()
    quality["approved_digest"] = gate_content_digest(str(quality.get("content") or ""))
    metadata = dict(project.metadata)
    metadata["teacher_guide_quality"] = quality
    store.update_project(project.id, ProjectUpdate(metadata=metadata))
    return {"status": "approved", "approved_at": quality["approved_at"]}


@router.get("/theme-packs/{project_id}/teacher-guide")
def theme_pack_teacher_guide(project_id: str):
    project = get_platform_store().get_project(project_id)
    if project is None or project.metadata.get("kind") != "theme_pack":
        raise HTTPException(status_code=404, detail="Temapakken finnes ikke.")
    quality = project.metadata.get("teacher_guide_quality") or {}
    guide = str(quality.get("content") or "")
    passport = quality.get("truth_passport") or {}
    try:
        require_export_ready(
            export_id="platform.theme_pack.teacher_guide",
            content=guide,
            verification_status=passport.get("status", "missing"),
            verified_revision=passport.get("content_revision", ""),
            verification_version=passport.get("version", ""),
            teacher_approved=bool(quality.get("approved_at")),
            approved_revision=str(quality.get("approved_digest") or ""),
            quarantined_texts=[item.get("original_text", "") for item in quality.get("quarantine", [])],
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    filename = "".join(character if character.isalnum() or character in "-_" else "-" for character in project.title).strip("-") or "temapakke"
    return Response(
        guide,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}-laererveiledning.md"'},
    )
