from __future__ import annotations

from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from .models import (
    Job,
    Project,
    ProjectCreate,
    ProjectUpdate,
    QualityPassport,
    QualityPassportRequest,
    ThemePack,
    ThemePackRequest,
    ThemePackTask,
)
from .quality import build_quality_passport
from .store import get_platform_store


router = APIRouter(tags=["platform"])


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
    passport = build_quality_passport(QualityPassportRequest(
        module="platform",
        title=request.title,
        content=" ".join(task.brief for task in tasks),
        sources=[],
        competency_goals=request.competency_goals,
        has_answer_key=request.include_assessment,
        prompt_version="theme-pack-planner-v1",
    ))
    metadata = dict(project.metadata)
    metadata["tasks"] = [task.model_dump() for task in tasks]
    project = store.update_project(project.id, ProjectUpdate(metadata=metadata)) or project
    return ThemePack(id=uuid4().hex, project=project, tasks=tasks, quality_passport=passport)
