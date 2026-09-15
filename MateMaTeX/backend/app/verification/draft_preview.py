"""Watermark every page of a review draft without reusing an approved PDF."""

import re


def watermarked_draft(document: str) -> str:
    if r"\begin{document}" not in document:
        raise ValueError("Utkastet mangler dokumentramme")
    # Every page identifies itself as unapproved. The stored original and its
    # approval proof are never changed.
    marker = r"""
\usepackage{draftwatermark}
\SetWatermarkText{UTKAST -- IKKE GODKJENT}
\SetWatermarkScale{0.45}
\SetWatermarkLightness{0.8}
"""
    document = re.sub(r"\\SetWatermark\w+\{[^}]*\}", "", document)
    return document.replace(r"\begin{document}", marker + r"\begin{document}", 1)
