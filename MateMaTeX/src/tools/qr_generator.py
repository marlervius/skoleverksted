"""
QR Code Generator for MateMaTeX.
Creates QR codes linking to answer sheets and solutions.
"""

import base64
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

# Try to import qrcode, but make it optional
try:
    import qrcode
    from qrcode.image.pure import PyPNGImage
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False


def is_qr_available() -> bool:
    """Check if QR code generation is available."""
    return QR_AVAILABLE


def generate_qr_code(
    data: str,
    size: int = 200,
    error_correction: str = "M"
) -> Optional[bytes]:
    """
    Generate a QR code image.
    
    Args:
        data: Data to encode in QR code.
        size: Size of the image in pixels.
        error_correction: Error correction level (L, M, Q, H).
    
    Returns:
        PNG image data as bytes, or None if qrcode not available.
    """
    if not QR_AVAILABLE:
        return None
    
    error_levels = {
        "L": qrcode.constants.ERROR_CORRECT_L,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "H": qrcode.constants.ERROR_CORRECT_H,
    }
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=error_levels.get(error_correction, qrcode.constants.ERROR_CORRECT_M),
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    from io import BytesIO
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_answer_qr(
    answers: dict,
    title: str = "Fasit",
    include_explanations: bool = False
) -> Optional[dict]:
    """
    Generate a QR code for an answer sheet.
    
    Args:
        answers: Dictionary of question numbers to answers.
        title: Title for the answer sheet.
        include_explanations: Whether answers include explanations.
    
    Returns:
        Dictionary with QR image data and encoded URL, or None.
    """
    if not QR_AVAILABLE:
        return None
    
    # Create compact answer data
    answer_data = {
        "t": title,
        "a": answers,
        "ts": datetime.now().isoformat()[:10],
    }
    
    # Encode as JSON and base64
    json_str = json.dumps(answer_data, ensure_ascii=False, separators=(',', ':'))
    encoded = base64.urlsafe_b64encode(json_str.encode()).decode()
    
    # Create a simple hash for verification
    hash_val = hashlib.md5(json_str.encode()).hexdigest()[:8]
    
    # Create the data URL (could be a real URL in production)
    # For now, we encode answers directly in the QR
    qr_data = f"MATEMAX:{hash_val}:{encoded}"
    
    # Generate QR code
    qr_bytes = generate_qr_code(qr_data)
    
    if not qr_bytes:
        return None
    
    return {
        "image": qr_bytes,
        "data": qr_data,
        "hash": hash_val,
        "answers": answers,
    }


def decode_answer_qr(qr_data: str) -> Optional[dict]:
    """
    Decode an answer QR code.
    
    Args:
        qr_data: The QR code data string.
    
    Returns:
        Decoded answer data, or None if invalid.
    """
    if not qr_data.startswith("MATEMAX:"):
        return None
    
    try:
        parts = qr_data.split(":", 2)
        if len(parts) != 3:
            return None
        
        _, hash_val, encoded = parts
        
        # Decode base64
        json_str = base64.urlsafe_b64decode(encoded).decode()
        
        # Verify hash
        expected_hash = hashlib.md5(json_str.encode()).hexdigest()[:8]
        if expected_hash != hash_val:
            return None
        
        # Parse JSON
        data = json.loads(json_str)
        
        return {
            "title": data.get("t", "Fasit"),
            "answers": data.get("a", {}),
            "date": data.get("ts", ""),
        }
    
    except Exception:
        return None


def extract_answers_from_latex(latex_content: str) -> dict:
    """
    Extract answers from LaTeX content.
    
    Args:
        latex_content: The LaTeX source code.
    
    Returns:
        Dictionary of question numbers to answers.
    """
    import re
    
    answers = {}
    
    # Look for solutions section
    solutions_match = re.search(
        r'\\section\*?\{Løsningsforslag\}(.*?)(?=\\section|\\end\{document\}|$)',
        latex_content,
        re.DOTALL
    )
    
    if solutions_match:
        solutions_text = solutions_match.group(1)
        
        # Extract individual answers
        # Pattern: \textbf{Oppgave N} followed by answer
        answer_pattern = r'\\textbf\{Oppgave\s*(\d+)\}[:\s]*([^\\]+?)(?=\\textbf|$)'
        
        for match in re.finditer(answer_pattern, solutions_text, re.DOTALL):
            question_num = match.group(1)
            answer_text = match.group(2).strip()
            
            # Clean up the answer
            answer_text = re.sub(r'\s+', ' ', answer_text)
            answer_text = answer_text[:100]  # Limit length
            
            answers[question_num] = answer_text
    
    # Also look for losning environments
    losning_pattern = r'\\begin\{losning\}(.*?)\\end\{losning\}'
    losning_matches = list(re.finditer(losning_pattern, latex_content, re.DOTALL))
    
    for i, match in enumerate(losning_matches):
        if str(i + 1) not in answers:
            answer_text = match.group(1).strip()
            # Clean up LaTeX
            answer_text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', answer_text)
            answer_text = re.sub(r'\s+', ' ', answer_text)
            answer_text = answer_text[:100]
            answers[str(i + 1)] = answer_text
    
    return answers


def generate_qr_for_worksheet(
    latex_content: str,
    title: str = "Matematikk Fasit"
) -> Optional[dict]:
    """
    Generate a QR code for a complete worksheet.
    
    Args:
        latex_content: The LaTeX source code.
        title: Title for the QR code.
    
    Returns:
        QR code data dictionary, or None.
    """
    # Extract answers
    answers = extract_answers_from_latex(latex_content)
    
    if not answers:
        return None
    
    # Generate QR
    return generate_answer_qr(answers, title)


def get_qr_latex_code(qr_image_path: str, caption: str = "Skann for fasit") -> str:
    """
    Get LaTeX code for embedding a QR code image.
    
    Args:
        qr_image_path: Path to the QR code image.
        caption: Caption for the image.
    
    Returns:
        LaTeX code for the QR code.
    """
    return f"""\\begin{{figure}}[H]
\\centering
\\includegraphics[width=3cm]{{{qr_image_path}}}
\\caption*{{\\small {caption}}}
\\end{{figure}}
"""


def create_qr_placeholder() -> str:
    """
    Create a placeholder for when QR is not available.
    
    Returns:
        LaTeX code for a placeholder.
    """
    return r"""
\begin{center}
\fbox{\parbox{3cm}{\centering\small\vspace{1cm}QR-kode\\(krever qrcode-pakke)\vspace{1cm}}}
\end{center}
"""


def generate_simple_text_qr(text: str, max_length: int = 200) -> Optional[bytes]:
    """
    Generate a simple QR code with plain text.
    
    Args:
        text: Text to encode.
        max_length: Maximum text length.
    
    Returns:
        PNG image data, or None.
    """
    if not QR_AVAILABLE:
        return None
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    return generate_qr_code(text)
