"""
QR code generation for embedding in worksheets.

Generates QR codes linking to digital solutions, hints, or shared resources.
Can be embedded in LaTeX output via \\includegraphics.
"""

from __future__ import annotations

import base64
import io
import os
import tempfile

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import get_current_user

logger = structlog.get_logger()

router = APIRouter(prefix="/export", tags=["export"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class QrGenerateRequest(BaseModel):
    url: str = Field(..., min_length=1, description="URL to encode")
    size: int = Field(10, ge=5, le=40, description="Box size in pixels")
    label: str = Field("", description="Optional label text below QR code")


class QrGenerateResponse(BaseModel):
    success: bool
    png_base64: str = ""
    latex_include: str = ""
    error: str = ""

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "png_base64": "iVBOR...",
                "latex_include": r"\includegraphics[width=2cm]{qr_abc123.png}",
            }
        }


class QrBatchRequest(BaseModel):
    """Generate QR codes for multiple exercises."""
    items: list[dict] = Field(
        ...,
        description="List of {exercise_id, url} objects",
    )


class QrBatchResponse(BaseModel):
    success: bool
    codes: list[dict] = []
    errors: list[str] = []


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
def generate_qr_png(
    url: str,
    box_size: int = 10,
    border: int = 2,
) -> bytes:
    """Generate a QR code as PNG bytes."""
    try:
        import qrcode

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    except ImportError:
        logger.error("qrcode_package_not_installed")
        raise ImportError("qrcode[pil] package is required for QR generation")


def qr_to_latex_file(
    url: str,
    output_dir: str,
    filename: str = "qr",
    width: str = "2cm",
) -> str:
    """
    Generate a QR code PNG and return LaTeX \\includegraphics command.

    Saves the PNG to output_dir and returns the LaTeX inclusion command.
    """
    png_bytes = generate_qr_png(url)
    filepath = os.path.join(output_dir, f"{filename}.png")

    with open(filepath, "wb") as f:
        f.write(png_bytes)

    return rf"\includegraphics[width={width}]{{{filename}}}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/qr",
    response_model=QrGenerateResponse,
    summary="Generate a QR code PNG for a URL",
)
async def generate_qr(req: QrGenerateRequest, user_id: str = Depends(get_current_user)) -> QrGenerateResponse:
    """Generate a QR code PNG encoded as base64."""
    try:
        png_bytes = generate_qr_png(req.url, box_size=req.size)

        # Also generate LaTeX include command
        latex_cmd = rf"\includegraphics[width=2cm]{{qr}}"

        return QrGenerateResponse(
            success=True,
            png_base64=base64.b64encode(png_bytes).decode(),
            latex_include=latex_cmd,
        )
    except Exception as e:
        return QrGenerateResponse(success=False, error=str(e))


@router.post(
    "/qr/batch",
    response_model=QrBatchResponse,
    summary="Generate QR codes for multiple exercises",
)
async def generate_qr_batch(req: QrBatchRequest, user_id: str = Depends(get_current_user)) -> QrBatchResponse:
    """Generate QR codes for a batch of exercise URLs."""
    codes = []
    errors = []

    for item in req.items:
        try:
            url = item.get("url", "")
            exercise_id = item.get("exercise_id", "unknown")

            png_bytes = generate_qr_png(url)
            codes.append({
                "exercise_id": exercise_id,
                "png_base64": base64.b64encode(png_bytes).decode(),
                "url": url,
            })
        except Exception as e:
            errors.append(f"Failed for {item}: {e}")

    return QrBatchResponse(
        success=len(errors) == 0,
        codes=codes,
        errors=errors,
    )
