from __future__ import annotations

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
    utc_now,
)
from .compendium import (
    generate_compendium_chapter,
    plan_compendium,
    repair_compendium_chapter,
)
from .compendium_renderer import render_compendium
from .images import resolve_image
from .quality import build_quality_passport
from .store import get_platform_store
from .queue import get_durable_job_queue
from .year_planner import build_year_plan


router = APIRouter(tags=["platform"])


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
    payload.update(changes)
    if "content_markdown" in changes and "status" not in changes:
        payload["status"] = "generated"
    if (
        "content_markdown" in changes
        and changes["content_markdown"] != chapter.content_markdown
    ):
        payload["revision_summary"] = []
        payload["truth_passport"] = None
    requested_status = changes.get("status")
    passport = payload.get("truth_passport")
    passport_status = (
        passport.status
        if hasattr(passport, "status")
        else passport.get("status")
        if isinstance(passport, dict)
        else None
    )
    if requested_status == "approved" and passport_status != "verified":
        raise HTTPException(
            status_code=409,
            detail=(
                "Kapitlet kan ikke godkjennes før faktapasset er grønt. "
                "Kjør «Sjekk og rett automatisk» først."
            ),
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


@router.post("/compendia/{compendium_id}/chapters/{chapter_id}/repair", response_model=Compendium)
def repair_compendium_chapter_endpoint(compendium_id: str, chapter_id: str):
    store = get_platform_store()
    compendium = store.get_compendium(compendium_id)
    if compendium is None:
        raise HTTPException(status_code=404, detail="Kompendiet finnes ikke.")
    try:
        chapter = repair_compendium_chapter(compendium, chapter_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    updated = store.replace_compendium_chapter(compendium_id, chapter)
    if updated is None:
        raise HTTPException(status_code=404, detail="Kapitlet finnes ikke.")
    return updated


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
            or chapter.status in {"planned", "needs_revision"}
            or not chapter.truth_passport
            or chapter.truth_passport.status != "verified"
        )
    ]
    if incomplete:
        raise HTTPException(
            status_code=409,
            detail="Disse kapitlene må ferdigstilles før dokumentbygging: " + ", ".join(incomplete[:6]),
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
    return get_platform_store().create_year_plan(proposal)


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
    result = get_platform_store().update_year_plan_material(
        plan_id,
        period_id,
        material_id,
        request,
    )
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
    return [
        job for job in get_platform_store().list_jobs(limit=limit)
        if job.status in {"queued", "planning", "generating", "verifying", "rendering"}
    ]


@router.post("/jobs/{job_id}/cancel", response_model=Job)
def cancel_job(job_id: str):
    job = get_durable_job_queue().cancel(job_id)
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
    return ThemePack(id=uuid4().hex, project=project, tasks=tasks, quality_passport=passport)


@router.get("/theme-packs/{project_id}/teacher-guide")
def theme_pack_teacher_guide(project_id: str):
    project = get_platform_store().get_project(project_id)
    if project is None or project.metadata.get("kind") != "theme_pack":
        raise HTTPException(status_code=404, detail="Temapakken finnes ikke.")
    tasks = project.metadata.get("tasks", [])
    goals = "\n".join(f"- {goal}" for goal in project.competency_goals) or "- Legg til relevante kompetansemål før bruk."
    task_lines = "\n".join(f"{index}. **{task.get('title', 'Del')}** – {task.get('brief', '')}" for index, task in enumerate(tasks, 1))
    source = project.metadata.get("source_name") or "Ingen felles kilde oppgitt"
    guide = f"""# {project.title}\n\n## Felles ramme\n\nTema: {project.theme}\n\nFag/nivå: {project.subject} / {project.level}\n\nKilde: {source}\n\n{project.description}\n\n## Kompetansemål\n\n{goals}\n\n## Deler\n\n{task_lines}\n\n## Lærerens sluttkontroll\n\n- Kontroller fakta og kildehenvisninger.\n- Kontroller at språk- og regnenivå passer elevgruppen.\n- Gjennomfør oppgavene og fasiten før utdeling.\n- Tilpass personopplysninger og eksempler til klassen.\n"""
    filename = "".join(character if character.isalnum() or character in "-_" else "-" for character in project.title).strip("-") or "temapakke"
    return Response(
        guide,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}-laererveiledning.md"'},
    )
