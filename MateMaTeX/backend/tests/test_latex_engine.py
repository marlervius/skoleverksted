"""Tests for LaTeX engine selection.

A TeX Live installation can ship the ``lualatex`` binary without the font
loader ``fontspec`` needs. Choosing it then breaks every single compilation,
so the resolver must verify the engine can actually typeset before using it.
"""

from app.latex import compiler


def test_file_line_errors_include_the_cause_not_just_the_source_line():
    from app.verification.latex_checker import LatexChecker
    log = "/tmp/matematex/document.tex:572: LaTeX Error: Something's wrong--perhaps a missing \\item.\nl.572 \\begin{center}\n"
    errors = LatexChecker._extract_errors(log)
    assert "missing \\item" in errors[0]
    assert r"l.572 \begin{center}" in errors


def _reset_cache():
    compiler.engine_is_usable.cache_clear()


def test_unusable_opentype_engines_fall_back_to_pdflatex(monkeypatch):
    """Debian ships lualatex/xelatex in texlive-binaries without the font loaders."""
    _reset_cache()
    monkeypatch.setattr(compiler.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        compiler.subprocess,
        "run",
        lambda *_a, **_k: type("P", (), {"returncode": 1, "stdout": ""})(),
    )

    assert compiler.engine_is_usable("lualatex") is False
    assert compiler.engine_is_usable("xelatex") is False
    assert compiler.resolve_engine("auto") == "pdflatex"
    assert compiler.resolve_engine("lualatex") == "pdflatex"
    _reset_cache()


def test_usable_lualatex_is_preferred(monkeypatch):
    _reset_cache()
    monkeypatch.setattr(compiler.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        compiler.subprocess,
        "run",
        lambda *_a, **_k: type("P", (), {"returncode": 0, "stdout": "/path/to/file"})(),
    )

    assert compiler.engine_is_usable("lualatex") is True
    assert compiler.resolve_engine("auto") == "lualatex"
    _reset_cache()


def test_pdflatex_needs_no_font_loader(monkeypatch):
    _reset_cache()
    monkeypatch.setattr(compiler.shutil, "which", lambda name: "/usr/bin/pdflatex" if name == "pdflatex" else None)
    assert compiler.engine_is_usable("pdflatex") is True
    assert compiler.resolve_engine("auto") == "pdflatex"
    _reset_cache()


def test_compile_reports_permission_error_as_controlled_export_failure(monkeypatch):
    monkeypatch.setattr(compiler, "resolve_engine", lambda _preferred=None: "pdflatex")

    def denied(*_args, **_kwargs):
        raise PermissionError("access denied")

    monkeypatch.setattr(compiler.subprocess, "run", denied)

    pdf_path, log = compiler.compile_to_pdf_with_log(
        r"\documentclass{article}\begin{document}Test\end{document}",
    )

    assert pdf_path is None
    assert "tilgang nektet" in log
