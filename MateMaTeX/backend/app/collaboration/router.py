"""
Collaboration API — school exercise bank, comments, version history.

Provides endpoints for school-level sharing, threaded comments on
generations, and document version history with restore capability.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user

logger = structlog.get_logger()

router = APIRouter(tags=["collaboration"])


from app.stores import collaboration_store as collab


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

# --- School ---
class SchoolExerciseOut(BaseModel):
    id: str
    title: str
    topic: str
    grade_level: str
    difficulty: str
    latex_content: str
    published_by: str = ""
    published_at: str = ""


class PublishRequest(BaseModel):
    exercise_id: str
    school: str = ""


class SchoolListResponse(BaseModel):
    exercises: list[SchoolExerciseOut]
    total: int


# --- Comments ---
class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    parent_id: str | None = None


class CommentOut(BaseModel):
    id: str
    content: str
    user_name: str
    parent_id: str | None = None
    created_at: str
    replies: list[CommentOut] = []


class CommentListResponse(BaseModel):
    comments: list[CommentOut]
    total: int


# --- Versions ---
class VersionOut(BaseModel):
    id: str
    version_number: int
    change_summary: str
    latex_body: str
    created_at: str


class VersionCreateRequest(BaseModel):
    latex_body: str = Field(..., min_length=1)
    change_summary: str = ""


class VersionListResponse(BaseModel):
    versions: list[VersionOut]
    total: int


# ---------------------------------------------------------------------------
# School exercise bank endpoints
# ---------------------------------------------------------------------------

school_router = APIRouter(prefix="/school", tags=["collaboration"])


@school_router.get(
    "/exercises",
    response_model=SchoolListResponse,
    summary="List exercises shared with the school",
)
async def list_school_exercises(
    topic: str | None = None,
    grade_level: str | None = None,
    school: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
) -> SchoolListResponse:
    """List exercises published to the school's shared bank."""
    results = list(collab.school_exercises().values())

    scope = school or (user_id if user_id not in ("anonymous", "api-user") else "")
    if scope:
        results = [
            r for r in results
            if r.get("school_id") == scope or r.get("published_by") == scope
        ]

    if topic:
        results = [r for r in results if topic.lower() in r.get("topic", "").lower()]
    if grade_level:
        results = [r for r in results if grade_level.lower() in r.get("grade_level", "").lower()]

    total = len(results)
    start = (page - 1) * page_size
    page_results = results[start:start + page_size]

    return SchoolListResponse(
        exercises=[SchoolExerciseOut(**{k: v for k, v in d.items()}) for d in page_results],
        total=total,
    )


@school_router.post(
    "/exercises/{exercise_id}/publish",
    summary="Publish an exercise to the school's shared bank",
)
async def publish_to_school(exercise_id: str, req: PublishRequest, user_id: str = Depends(get_current_user)):
    """Make an exercise available to all teachers at the school."""
    # Use the public API to fetch the exercise instead of importing private stores
    from app.exercises.router import get_exercise as _get_exercise

    try:
        exercise = await _get_exercise(exercise_id, user_id=user_id)
    except HTTPException:
        raise HTTPException(404, "Exercise not found")

    school_entry = {
        "id": exercise.id,
        "title": exercise.title,
        "topic": exercise.topic,
        "grade_level": exercise.grade_level,
        "difficulty": exercise.difficulty,
        "latex_content": exercise.latex_content,
        "published_by": req.school or user_id,
        "school_id": req.school or user_id,
        "published_at": datetime.now().isoformat(),
    }
    collab.school_exercises()[exercise_id] = school_entry
    collab.save_school_exercises()

    logger.info("exercise_published_to_school", exercise_id=exercise_id, user=user_id)
    return {"published": True, "exercise_id": exercise_id}


# ---------------------------------------------------------------------------
# Comments endpoints
# ---------------------------------------------------------------------------

comments_router = APIRouter(prefix="/generations", tags=["collaboration"])


@comments_router.get(
    "/{generation_id}/comments",
    response_model=CommentListResponse,
    summary="List comments on a generation",
)
async def list_comments(generation_id: str, user_id: str = Depends(get_current_user)) -> CommentListResponse:
    """Get all comments for a generation, threaded by parent_id."""
    all_comments = collab.all_comments(generation_id)

    # Build threaded structure
    top_level = [c for c in all_comments if c.get("parent_id") is None]
    comment_map = {c["id"]: c for c in all_comments}

    def build_tree(comment: dict) -> CommentOut:
        replies = [
            build_tree(r)
            for r in all_comments
            if r.get("parent_id") == comment["id"]
        ]
        return CommentOut(
            id=comment["id"],
            content=comment["content"],
            user_name=comment.get("user_name", "Anonym"),
            parent_id=comment.get("parent_id"),
            created_at=comment["created_at"],
            replies=replies,
        )

    threaded = [build_tree(c) for c in top_level]

    return CommentListResponse(comments=threaded, total=len(all_comments))


@comments_router.post(
    "/{generation_id}/comments",
    response_model=CommentOut,
    summary="Add a comment to a generation",
)
async def add_comment(generation_id: str, req: CommentCreate, user_id: str = Depends(get_current_user)) -> CommentOut:
    """Add a comment (optionally threaded) to a generation."""
    if req.parent_id:
        parent = next(
            (c for c in collab.all_comments(generation_id) if c.get("id") == req.parent_id),
            None,
        )
        if not parent:
            raise HTTPException(400, "parent_id not found for this generation")

    display_name = "Lærer" if user_id in ("anonymous", "api-user") else f"Bruker {user_id[:8]}"
    comment = {
        "id": uuid.uuid4().hex[:12],
        "content": req.content,
        "user_name": display_name,
        "parent_id": req.parent_id,
        "created_at": datetime.now().isoformat(),
    }

    collab.add_comment(generation_id, comment)

    logger.info("comment_added", generation_id=generation_id, comment_id=comment["id"])

    return CommentOut(**comment)


# ---------------------------------------------------------------------------
# Version history endpoints
# ---------------------------------------------------------------------------

versions_router = APIRouter(prefix="/generations", tags=["collaboration"])


@versions_router.get(
    "/{generation_id}/versions",
    response_model=VersionListResponse,
    summary="List all versions of a generation",
)
async def list_versions(generation_id: str, user_id: str = Depends(get_current_user)) -> VersionListResponse:
    """Get the version history of a generation."""
    versions = collab.all_versions(generation_id)
    return VersionListResponse(
        versions=[VersionOut(**v) for v in versions],
        total=len(versions),
    )


@versions_router.post(
    "/{generation_id}/versions",
    response_model=VersionOut,
    summary="Create a new version of a generation",
)
async def create_version(
    generation_id: str,
    req: VersionCreateRequest,
    user_id: str = Depends(get_current_user),
) -> VersionOut:
    """Save a new version of the generation's LaTeX content."""
    version_number = len(collab.all_versions(generation_id)) + 1

    version = {
        "id": uuid.uuid4().hex[:12],
        "version_number": version_number,
        "latex_body": req.latex_body,
        "change_summary": req.change_summary,
        "created_at": datetime.now().isoformat(),
    }
    collab.add_version(generation_id, version)

    logger.info(
        "version_created",
        generation_id=generation_id,
        version_number=version_number,
    )

    return VersionOut(**version)


@versions_router.post(
    "/{generation_id}/versions/{version_id}/restore",
    summary="Restore a specific version",
)
async def restore_version(generation_id: str, version_id: str, user_id: str = Depends(get_current_user)):
    """Restore a previous version, creating a new version entry."""
    versions = collab.all_versions(generation_id)
    target = next((v for v in versions if v["id"] == version_id), None)

    if not target:
        raise HTTPException(404, "Version not found")

    # Create a new version with the restored content
    new_version = {
        "id": uuid.uuid4().hex[:12],
        "version_number": len(versions) + 1,
        "latex_body": target["latex_body"],
        "change_summary": f"Gjenopprettet fra versjon {target['version_number']}",
        "created_at": datetime.now().isoformat(),
    }
    collab.add_version(generation_id, new_version)

    logger.info(
        "version_restored",
        generation_id=generation_id,
        restored_version=target["version_number"],
        new_version=new_version["version_number"],
    )

    return {
        "restored": True,
        "new_version_number": new_version["version_number"],
        "restored_from": target["version_number"],
    }


# Combine all sub-routers
router = APIRouter()
router.include_router(school_router)
router.include_router(comments_router)
router.include_router(versions_router)
