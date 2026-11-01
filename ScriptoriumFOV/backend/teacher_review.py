"""Language-only manual review; never manufacture an automatic fact passport."""
from __future__ import annotations

import hashlib
import json

from Skoleverksted.backend.platform.document_revision import canonical_document_content
from Skoleverksted.backend.platform.quality_gate import content_digest

REVIEW_MODE = "teacher-v1"


def review_document(content: str) -> dict:
    canonical = canonical_document_content(content)
    parsed = json.loads(canonical)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("text"), str) or not parsed["text"].strip():
        raise ValueError("Læringsarket mangler tekst for lærergjennomgang.")
    if not isinstance(parsed.get("worksheet"), str):
        raise ValueError("Læringsarket mangler oppgavefeltet.")
    if parsed.get("language_exercises") is not None and not isinstance(parsed["language_exercises"], dict):
        raise ValueError("Språkøvelsene har ugyldig format.")
    return {
        "review_mode": REVIEW_MODE,
        "content": canonical,
        "content_revision": content_digest(canonical),
        "teacher_approved_at": None,
        "approved_digest": "",
        "approved_artifact_hash": "",
    }


def review_ready(document: dict) -> bool:
    if document.get("review_mode") != REVIEW_MODE:
        return False
    try:
        expected = review_document(str(document.get("content") or ""))
    except (ValueError, TypeError):
        return False
    return expected["content_revision"] == document.get("content_revision")


def artifact_hash(progress: dict) -> str:
    payloads = [progress.get(key) for key in ("pdf_bytes", "zip_bytes") if progress.get(key)]
    if progress.get("job_status") != "completed" or len(payloads) != 1 or not isinstance(payloads[0], bytes):
        raise PermissionError("Filen er ikke klar for lærergodkjenning.")
    return hashlib.sha256(payloads[0]).hexdigest()


def require_review(document: dict, progress: dict, *, approved: bool) -> None:
    if not review_ready(document):
        raise PermissionError("Innholdet er endret. Lag en ny forhåndsvisning før godkjenning.")
    current_file = artifact_hash(progress)
    if approved and (
        not document.get("teacher_approved_at")
        or document.get("approved_digest") != content_digest(document["content"])
        or document.get("approved_artifact_hash") != current_file
    ):
        raise PermissionError("Gjennomgå innholdet og godkjenn denne versjonen før nedlasting.")
