"""Validation and metadata helpers for generated Norsklæring artefacts."""

from __future__ import annotations

import io
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
