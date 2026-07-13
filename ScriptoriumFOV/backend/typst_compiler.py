"""
Typst PDF compilation module.

Wraps the system `typst` CLI to compile .typ source files to PDF bytes.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional

if __package__:
    from .config import TYPST_COMPILE_TIMEOUT_SECONDS
else:
    from config import TYPST_COMPILE_TIMEOUT_SECONDS


def compile_typst(source: str, image_path: Optional[str] = None) -> bytes:
    """
    Compile Typst source to PDF using the CLI.

    Uses subprocess to call the system typst executable, which is more
    reliable on Windows than the Python library.

    Args:
        source: Typst source code as a string
        image_path: Optional path to an image file to include

    Returns:
        PDF bytes

    Raises:
        RuntimeError: If compilation fails
    """
    typst_exe = shutil.which("typst")
    if not typst_exe:
        raise RuntimeError(
            "Typst executable not found. Please install Typst: https://typst.app/"
        )

    temp_dir = tempfile.mkdtemp(prefix="fov_typst_")
    source_path = os.path.join(temp_dir, "document.typ")
    output_path = os.path.join(temp_dir, "output.pdf")

    try:
        if image_path and os.path.exists(image_path):
            raw_filename = os.path.basename(image_path)
            safe_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_filename)
            temp_image_path = os.path.join(temp_dir, safe_filename)
            shutil.copy2(image_path, temp_image_path)

        with open(source_path, "w", encoding="utf-8") as f:
            f.write(source)

        result = subprocess.run(
            [typst_exe, "compile", source_path, output_path],
            capture_output=True,
            text=True,
            timeout=TYPST_COMPILE_TIMEOUT_SECONDS,
            cwd=temp_dir,
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise RuntimeError(f"Typst compilation failed: {error_msg}")

        if not os.path.exists(output_path):
            raise RuntimeError("Typst did not produce output file")

        with open(output_path, "rb") as f:
            return f.read()

    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Ignore cleanup errors
