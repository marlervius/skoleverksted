"""
PDF Preview for MateMaTeX.
Provides inline PDF preview functionality.
"""

import base64
from pathlib import Path
from typing import Optional


def get_pdf_base64(pdf_path: str) -> Optional[str]:
    """
    Convert a PDF file to base64 string.
    
    Args:
        pdf_path: Path to the PDF file.
    
    Returns:
        Base64 encoded string or None if file not found.
    """
    try:
        path = Path(pdf_path)
        if path.exists():
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    except (IOError, OSError):
        pass
    return None


def get_pdf_bytes_base64(pdf_bytes: bytes) -> str:
    """
    Convert PDF bytes to base64 string.
    
    Args:
        pdf_bytes: PDF content as bytes.
    
    Returns:
        Base64 encoded string.
    """
    return base64.b64encode(pdf_bytes).decode()


def create_pdf_preview_html(
    pdf_base64: str,
    height: int = 600,
    width: str = "100%"
) -> str:
    """
    Create HTML for inline PDF preview.
    
    Args:
        pdf_base64: Base64 encoded PDF.
        height: Height of the preview in pixels.
        width: Width of the preview (CSS value).
    
    Returns:
        HTML string for embedding.
    """
    return f"""
<div style="
    border: 1px solid #374151;
    border-radius: 8px;
    overflow: hidden;
    background: #1e293b;
">
    <div style="
        background: #0f172a;
        padding: 0.5rem 1rem;
        border-bottom: 1px solid #374151;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    ">
        <span style="color: #f0b429;">📄</span>
        <span style="color: #e2e8f0; font-size: 0.875rem;">PDF Forhåndsvisning</span>
    </div>
    <iframe
        src="data:application/pdf;base64,{pdf_base64}"
        width="{width}"
        height="{height}px"
        style="border: none; display: block;"
        title="PDF Preview"
    ></iframe>
</div>
"""


def create_pdf_preview_with_controls(
    pdf_base64: str,
    height: int = 600,
    filename: str = "document.pdf"
) -> str:
    """
    Create HTML for PDF preview with control buttons.
    
    Args:
        pdf_base64: Base64 encoded PDF.
        height: Height of the preview in pixels.
        filename: Filename for download.
    
    Returns:
        HTML string with controls.
    """
    return f"""
<div style="
    border: 1px solid #374151;
    border-radius: 12px;
    overflow: hidden;
    background: #1e293b;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
">
    <div style="
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 0.75rem 1rem;
        border-bottom: 1px solid #374151;
        display: flex;
        align-items: center;
        justify-content: space-between;
    ">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span style="font-size: 1.25rem;">📄</span>
            <span style="color: #f0b429; font-weight: 500;">Forhåndsvisning</span>
        </div>
        <div style="display: flex; gap: 0.5rem;">
            <a 
                href="data:application/pdf;base64,{pdf_base64}"
                download="{filename}"
                style="
                    background: #f0b429;
                    color: #0f172a;
                    padding: 0.5rem 1rem;
                    border-radius: 6px;
                    text-decoration: none;
                    font-size: 0.875rem;
                    font-weight: 500;
                    display: inline-flex;
                    align-items: center;
                    gap: 0.25rem;
                "
            >
                ⬇️ Last ned
            </a>
            <button
                onclick="window.open('data:application/pdf;base64,{pdf_base64}', '_blank')"
                style="
                    background: #374151;
                    color: #e2e8f0;
                    padding: 0.5rem 1rem;
                    border-radius: 6px;
                    border: none;
                    font-size: 0.875rem;
                    cursor: pointer;
                    display: inline-flex;
                    align-items: center;
                    gap: 0.25rem;
                "
            >
                🔗 Åpne i ny fane
            </button>
        </div>
    </div>
    <iframe
        src="data:application/pdf;base64,{pdf_base64}#toolbar=1&navpanes=0"
        width="100%"
        height="{height}px"
        style="border: none; display: block; background: white;"
        title="PDF Forhåndsvisning"
    ></iframe>
</div>
"""


def create_pdf_fallback_html(pdf_base64: str, filename: str = "document.pdf") -> str:
    """
    Create fallback HTML when PDF preview is not supported.
    
    Args:
        pdf_base64: Base64 encoded PDF.
        filename: Filename for download.
    
    Returns:
        HTML string with download link.
    """
    return f"""
<div style="
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #374151;
    border-radius: 12px;
    padding: 2rem;
    text-align: center;
">
    <div style="font-size: 3rem; margin-bottom: 1rem;">📄</div>
    <h3 style="color: #f0b429; margin-bottom: 0.5rem;">PDF Generert</h3>
    <p style="color: #9ca3af; margin-bottom: 1.5rem;">
        Nettleseren din støtter ikke inline PDF-visning.
    </p>
    <a 
        href="data:application/pdf;base64,{pdf_base64}"
        download="{filename}"
        style="
            background: #f0b429;
            color: #0f172a;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        "
    >
        ⬇️ Last ned PDF
    </a>
</div>
"""


def get_pdf_page_count(pdf_bytes: bytes) -> int:
    """
    Get the number of pages in a PDF.
    
    Args:
        pdf_bytes: PDF content as bytes.
    
    Returns:
        Number of pages, or 0 if unable to determine.
    """
    try:
        # Simple heuristic: count "/Page" occurrences
        content = pdf_bytes.decode('latin-1', errors='ignore')
        # This is a rough estimate
        count = content.count('/Type /Page') - content.count('/Type /Pages')
        return max(count, 1)
    except Exception:
        return 0


def create_preview_thumbnail_html(pdf_base64: str, page: int = 1) -> str:
    """
    Create a small thumbnail preview of the PDF.
    
    Args:
        pdf_base64: Base64 encoded PDF.
        page: Page number to show.
    
    Returns:
        HTML string for thumbnail.
    """
    return f"""
<div style="
    width: 120px;
    height: 170px;
    border: 1px solid #374151;
    border-radius: 4px;
    overflow: hidden;
    background: white;
    position: relative;
">
    <iframe
        src="data:application/pdf;base64,{pdf_base64}#page={page}&toolbar=0&navpanes=0&scrollbar=0"
        width="120"
        height="170"
        style="border: none; transform: scale(0.3); transform-origin: top left; width: 400px; height: 566px;"
        title="PDF Thumbnail"
    ></iframe>
    <div style="
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        background: rgba(15, 23, 42, 0.8);
        color: white;
        font-size: 0.625rem;
        padding: 0.25rem;
        text-align: center;
    ">
        Side {page}
    </div>
</div>
"""
