from Skoleverksted.backend.platform.text_quality import inspect_markdown


def test_structural_quality_accepts_complete_markdown():
    text = "## Et kapittel\n\n" + ("Dette er en komplett setning med dokumentert innhold. " * 35)
    assert inspect_markdown(text) == []


def test_document_title_with_first_subheading_is_not_empty():
    text = "## Kapittel\n\n### Innledning\n\nDette er innholdet under kapittelet."
    assert inspect_markdown(text, min_words=1) == []


def test_structural_quality_rejects_observed_fragments_and_empty_headings():
    text = "## Aktører\n\nSærlig ble en finansiell katastrofe.\n\n## Tom overskrift\n"
    codes = {issue.code for issue in inspect_markdown(text, min_words=5)}
    assert "sentence_fragment" in codes
    assert "empty_heading" in codes


def test_structural_quality_rejects_truncation_and_html():
    text = "## Innhold\n\n" + ("Et avsnitt med innhold. " * 10) + "..."
    text = text.replace("Et avsnitt", "<br>Et avsnitt", 1)
    codes = {issue.code for issue in inspect_markdown(text, min_words=5)}
    assert {"possible_truncation", "html_markup"}.issubset(codes)
