"""
Sharing API — create and resolve shareable links.

Supports: password protection, expiry dates, view limits, cloning.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.job_store import get_resource_snapshot, store_shared_resource
from app.rate_limit import limiter
from app.stores import sharing_store as share_store

logger = structlog.get_logger()

router = APIRouter(prefix="/sharing", tags=["sharing"])


def _get_link(token: str) -> dict:
    link = share_store.get_link(token)
    if not link:
        raise HTTPException(404, "Shared link not found")
    return link


def _persist_link(token: str, link: dict) -> None:
    share_store.save_link(token, link)


class ShareRequest(BaseModel):
    resource_type: str = Field(
        ...,
        description="'generation', 'exercise_set', or 'folder'",
    )
    resource_id: str = Field(..., description="ID of the resource to share")
    password: str | None = Field(None, description="Optional password protection")
    expires_hours: int | None = Field(None, ge=1, le=8760)
    max_views: int | None = Field(None, ge=1)
    allow_download: bool = True
    allow_clone: bool = True


class ShareResponse(BaseModel):
    success: bool
    token: str = ""
    share_url: str = ""
    expires_at: str | None = None
    error: str = ""


class SharedResourceResponse(BaseModel):
    success: bool
    resource_type: str = ""
    resource_id: str = ""
    content: dict = {}
    allow_download: bool = True
    allow_clone: bool = True
    error: str = ""


class CloneResponse(BaseModel):
    success: bool
    new_resource_id: str = ""
    error: str = ""


class VerifyPasswordRequest(BaseModel):
    password: str


class CloneRequest(BaseModel):
    password: str | None = Field(None, description="Required when the link is password-protected")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode(), stored_hash.encode())
        except ValueError:
            return False
    legacy = hashlib.sha256(password.encode()).hexdigest()
    return secrets.compare_digest(legacy, stored_hash)


def _check_link_valid(link: dict) -> tuple[bool, str]:
    if link.get("expires_at"):
        expires = datetime.fromisoformat(link["expires_at"])
        if datetime.now() > expires:
            return False, "Link has expired"
    if link.get("max_views") is not None and link["view_count"] >= link["max_views"]:
        return False, "Maximum views reached"
    return True, ""


def _resolve_shared_content(link: dict) -> dict:
    return get_resource_snapshot(link["resource_type"], link["resource_id"]) or {}


@router.post("", response_model=ShareResponse, summary="Create a shareable link")
@limiter.limit("30/minute")
async def create_share(
    request: Request,
    req: ShareRequest,
    user_id: str = Depends(get_current_user),
) -> ShareResponse:
    snapshot = get_resource_snapshot(req.resource_type, req.resource_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Resource not found")

    store_shared_resource(req.resource_id, snapshot)
    token = secrets.token_urlsafe(24)

    link_data = {
        "id": uuid.uuid4().hex,
        "token": token,
        "resource_type": req.resource_type,
        "resource_id": req.resource_id,
        "password_hash": _hash_password(req.password) if req.password else None,
        "expires_at": (
            (datetime.now() + timedelta(hours=req.expires_hours)).isoformat()
            if req.expires_hours
            else None
        ),
        "max_views": req.max_views,
        "view_count": 0,
        "allow_download": req.allow_download,
        "allow_clone": req.allow_clone,
        "created_at": datetime.now().isoformat(),
    }
    _persist_link(token, link_data)

    logger.info("share_created", token=token[:8], resource_type=req.resource_type)
    return ShareResponse(
        success=True,
        token=token,
        share_url=f"/shared/{token}",
        expires_at=link_data["expires_at"],
    )


@router.get("/{token}", response_model=SharedResourceResponse)
@limiter.limit("60/minute")
async def get_shared(request: Request, token: str) -> SharedResourceResponse:
    link = _get_link(token)
    valid, error = _check_link_valid(link)
    if not valid:
        raise HTTPException(410, error)
    if link["password_hash"]:
        raise HTTPException(401, "Password required — use POST /sharing/{token}/access")
    link["view_count"] += 1
    _persist_link(token, link)
    return SharedResourceResponse(
        success=True,
        resource_type=link["resource_type"],
        resource_id=link["resource_id"],
        content=_resolve_shared_content(link),
        allow_download=link["allow_download"],
        allow_clone=link["allow_clone"],
    )


@router.post("/{token}/access", response_model=SharedResourceResponse)
@limiter.limit("30/minute")
async def access_shared(
    request: Request,
    token: str,
    req: VerifyPasswordRequest,
) -> SharedResourceResponse:
    link = _get_link(token)
    valid, error = _check_link_valid(link)
    if not valid:
        raise HTTPException(410, error)
    if link["password_hash"] and not _check_password(req.password, link["password_hash"]):
        raise HTTPException(403, "Incorrect password")
    link["view_count"] += 1
    _persist_link(token, link)
    return SharedResourceResponse(
        success=True,
        resource_type=link["resource_type"],
        resource_id=link["resource_id"],
        content=_resolve_shared_content(link),
        allow_download=link["allow_download"],
        allow_clone=link["allow_clone"],
    )


@router.post("/{token}/clone", response_model=CloneResponse)
async def clone_shared(
    token: str,
    req: CloneRequest | None = None,
    user_id: str = Depends(get_current_user),
) -> CloneResponse:
    link = _get_link(token)
    if not link.get("allow_clone", True):
        raise HTTPException(403, "Cloning not allowed")
    valid, error = _check_link_valid(link)
    if not valid:
        raise HTTPException(410, error)
    # Password-protected links must be unlocked to clone, mirroring read access.
    if link["password_hash"]:
        provided = req.password if req else None
        if not provided:
            raise HTTPException(401, "Password required to clone this resource")
        if not _check_password(provided, link["password_hash"]):
            raise HTTPException(403, "Incorrect password")
    new_id = uuid.uuid4().hex
    original = get_resource_snapshot(link["resource_type"], link["resource_id"]) or {}
    store_shared_resource(new_id, {**original, "id": new_id, "cloned_from": link["resource_id"]})
    return CloneResponse(success=True, new_resource_id=new_id)


@router.get("/{token}/pdf")
@limiter.limit("30/minute")
async def get_shared_pdf(request: Request, token: str):
    """Return PDF for a shared generation (public via token). Cached after first compile."""
    import os

    link = _get_link(token)
    valid, error = _check_link_valid(link)
    if not valid:
        raise HTTPException(410, error)

    content = _resolve_shared_content(link)
    full_doc = str(content.get("full_document") or "")
    if not full_doc.strip():
        raise HTTPException(404, "Ingen PDF-kilde i delt ressurs")

    from app.config import get_settings
    from app.latex.compiler import compile_to_pdf

    doc_hash = hashlib.sha256(full_doc.encode("utf-8")).hexdigest()[:16]
    cache_dir = Path(get_settings().output_dir) / "shared_pdfs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{token}.pdf"

    if link.get("pdf_doc_hash") == doc_hash and cache_path.is_file():
        pdf_bytes = cache_path.read_bytes()
    else:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "shared.pdf")
            pdf_path = await asyncio.to_thread(compile_to_pdf, full_doc, out_path)
            if not pdf_path or not os.path.isfile(pdf_path):
                raise HTTPException(500, "Kunne ikke kompilere PDF")
            pdf_bytes = Path(pdf_path).read_bytes()
        cache_path.write_bytes(pdf_bytes)
        link["pdf_doc_hash"] = doc_hash
        _persist_link(token, link)

    link["view_count"] = link.get("view_count", 0) + 1
    _persist_link(token, link)

    from fastapi.responses import Response

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="matematex-delt-{token[:8]}.pdf"',
            "Cache-Control": "private, max-age=3600",
            "ETag": f'"{doc_hash}"',
        },
    )
