"""Small, deterministic PDF fixture used by the Norsk artifact tests."""

from __future__ import annotations

import io

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def build_valid_pdf_bytes() -> bytes:
    """Return a one-page PDF without depending on a local generated file."""

    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): font_reference}
            )
        }
    )

    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 770 Td (Arbeidsliv) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
