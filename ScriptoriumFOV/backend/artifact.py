"""Validation and metadata helpers for generated Norsklæring artefacts."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass


MIN_PDF_BYTES = 256


class ArtifactValidationError(ValueError):
    """Raised when generated output is not safe to publish."""


@dataclass(frozen=True)
class ValidatedArtifact:
    """Validated bytes and the transport metadata exposed to the frontend."""

    content: bytes
    content_type: str
    filename: str
    kind: str

    @property
    def size_bytes(self) -> int:
        return len(self.content)


def validate_pdf_bytes(pdf_bytes: bytes) -> None:
    """Fail closed unless bytes are a readable, non-empty PDF with a page."""

    if not isinstance(pdf_bytes, bytes) or len(pdf_bytes) < MIN_PDF_BYTES:
        raise ArtifactValidationError("pdf_too_small")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ArtifactValidationError("pdf_signature_invalid")

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
        if len(reader.pages) < 1:
            raise ArtifactValidationError("pdf_has_no_pages")
        has_content = False
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            contents = page.get("/Contents")
            if text or contents:
                has_content = True
                break
        if not has_content:
            raise ArtifactValidationError("pdf_is_blank")
    except ArtifactValidationError:
        raise
    except Exception as exc:
        raise ArtifactValidationError("pdf_unreadable") from exc


def validate_pdf_artifact(pdf_bytes: bytes, filename: str) -> ValidatedArtifact:
    """Validate a PDF and return normalized metadata inputs."""

    safe_filename = filename if filename.lower().endswith(".pdf") else f"{filename}.pdf"
    validate_pdf_bytes(pdf_bytes)
    return ValidatedArtifact(
        content=pdf_bytes,
        content_type="application/pdf",
        filename=safe_filename,
        kind="student_pdf",
    )


MAX_TRAINER_BYTES = 2 * 1024 * 1024
# Anything that would make a downloaded trainer reach out to another host.
_EXTERNAL_REFERENCE_RE = re.compile(
    r"""(?ix)
    (?:\b(?:src|href|action|poster|data)\s*=\s*["']?\s*(?:https?:)?//)
    | url\(\s*["']?\s*(?:https?:)?//
    | @import
    | <\s*(?:link|iframe|object|embed|form)\b
    """
)


def validate_trainer_html(html: str) -> bytes:
    """Fail closed unless the trainer is one self-contained, offline document."""

    if not isinstance(html, str) or not html.strip():
        raise ArtifactValidationError("trainer_empty")
    payload = html.encode("utf-8")
    if len(payload) > MAX_TRAINER_BYTES:
        raise ArtifactValidationError("trainer_too_large")
    if not html.lstrip().lower().startswith("<!doctype html>"):
        raise ArtifactValidationError("trainer_not_html")
    if 'id="trainer-data"' not in html:
        raise ArtifactValidationError("trainer_data_missing")
    if 'http-equiv="Content-Security-Policy"' not in html or "default-src 'none'" not in html:
        raise ArtifactValidationError("trainer_csp_missing")
    if _EXTERNAL_REFERENCE_RE.search(html):
        raise ArtifactValidationError("trainer_external_reference")
    return payload


def validate_trainer_artifact(html: str, filename: str) -> ValidatedArtifact:
    """Validate a concept trainer and return normalized metadata inputs."""

    payload = validate_trainer_html(html)
    safe_filename = filename if filename.lower().endswith(".html") else f"{filename}.html"
    return ValidatedArtifact(
        content=payload,
        content_type="text/html; charset=utf-8",
        filename=safe_filename,
        kind="concept_trainer",
    )


def validate_zip_artifact(zip_bytes: bytes, filename: str) -> ValidatedArtifact:
    """Validate a ZIP and every PDF it contains before publishing it."""

    if not isinstance(zip_bytes, bytes) or len(zip_bytes) < MIN_PDF_BYTES:
        raise ArtifactValidationError("zip_too_small")
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            pdf_names = [name for name in archive.namelist() if name.lower().endswith(".pdf")]
            if not pdf_names:
                raise ArtifactValidationError("zip_has_no_pdfs")
            for name in pdf_names:
                validate_pdf_bytes(archive.read(name))
    except ArtifactValidationError:
        raise
    except Exception as exc:
        raise ArtifactValidationError("zip_unreadable") from exc

    safe_filename = filename if filename.lower().endswith(".zip") else f"{filename}.zip"
    return ValidatedArtifact(
        content=zip_bytes,
        content_type="application/zip",
        filename=safe_filename,
        kind="student_pdf_bundle",
    )
