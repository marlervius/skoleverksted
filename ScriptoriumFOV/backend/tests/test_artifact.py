import io
import zipfile
from pathlib import Path

import pytest
from pypdf import PdfWriter

from ScriptoriumFOV.backend.artifact import (
    ArtifactValidationError,
    validate_pdf_artifact,
    validate_pdf_bytes,
    validate_zip_artifact,
)


PDF_FIXTURE = Path(__file__).resolve().parents[3] / "test_laeringsark.pdf"


def test_generated_pdf_fixture_is_readable_and_has_safe_metadata():
    artifact = validate_pdf_artifact(PDF_FIXTURE.read_bytes(), "Arbeidsliv.pdf")
    assert artifact.content_type == "application/pdf"
    assert artifact.filename == "Arbeidsliv.pdf"
    assert artifact.size_bytes > 256


def test_corrupt_pdf_is_rejected_before_publish():
    with pytest.raises(ArtifactValidationError, match="pdf_signature_invalid"):
        validate_pdf_bytes(b"not a pdf" * 100)


def test_blank_pdf_is_rejected():
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    output = io.BytesIO()
    writer.write(output)

    with pytest.raises(ArtifactValidationError, match="pdf_is_blank"):
        validate_pdf_bytes(output.getvalue())


def test_zip_validation_checks_each_contained_pdf():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Arbeidsliv.pdf", PDF_FIXTURE.read_bytes())

    artifact = validate_zip_artifact(output.getvalue(), "Arbeidsliv.zip")
    assert artifact.content_type == "application/zip"
    assert artifact.kind == "student_pdf_bundle"
