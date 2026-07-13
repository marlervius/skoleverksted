"""
LaTeX compilation — wraps pdflatex with proper error handling.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import structlog

logger = structlog.get_logger()

# Global cap on simultaneous LaTeX engine processes — every compile in the app
# (pipeline, editor preview, export) must go through this. Each pdflatex run
# can use 100MB+; uncapped concurrency OOM-kills the Render free tier.
_compile_gate: threading.BoundedSemaphore | None = None
_gate_lock = threading.Lock()


def get_compile_gate() -> threading.BoundedSemaphore:
    """Lazily build the global compile semaphore from settings."""
    global _compile_gate
    if _compile_gate is None:
        with _gate_lock:
            if _compile_gate is None:
                try:
                    from app.config import get_settings

                    limit = get_settings().max_concurrent_compiles
                except Exception:  # pragma: no cover - config import guard
                    limit = 2
                _compile_gate = threading.BoundedSemaphore(limit)
    return _compile_gate


_DOUBLE_PASS_TRIGGERS = (
    "\\ref{",
    "\\pageref{",
    "\\tableofcontents",
    "\\listoffigures",
    "\\listoftables",
    "\\cite{",
    "\\printindex",
)

# Recognised engines (in auto-preference order). LuaLaTeX gives the best
# typography (OpenType fonts + unicode-math); pdfLaTeX is the universal fallback.
_ENGINE_PREFERENCE = ("lualatex", "xelatex", "pdflatex")
_VALID_ENGINES = frozenset(_ENGINE_PREFERENCE)


def resolve_engine(preferred: str | None = None) -> str:
    """
    Decide which LaTeX engine binary to invoke.

    ``preferred`` (or ``settings.latex_engine``) may be a concrete engine name
    or ``"auto"``. We only ever return an engine that is actually installed; if
    nothing is found we return ``"pdflatex"`` so the caller still produces a
    sensible "not found" error rather than silently picking a missing binary.
    """
    if preferred is None:
        try:
            from app.config import get_settings

            preferred = get_settings().latex_engine
        except Exception:  # pragma: no cover - config import guard
            preferred = "auto"

    pref = (preferred or "auto").strip().lower()

    if pref in _VALID_ENGINES:
        if shutil.which(pref):
            return pref
        # Requested engine missing — degrade gracefully to anything available.
        for eng in _ENGINE_PREFERENCE:
            if shutil.which(eng):
                logger.warning("latex_engine_fallback", requested=pref, using=eng)
                return eng
        return "pdflatex"

    # "auto" (or anything unrecognised): prefer the richest engine present.
    for eng in _ENGINE_PREFERENCE:
        if shutil.which(eng):
            return eng
    return "pdflatex"


def _engine_binary(engine: str, pdflatex_path: str) -> str:
    """Map an engine name to the executable, honouring a pdflatex path override."""
    if engine == "pdflatex" and pdflatex_path and pdflatex_path != "pdflatex":
        return pdflatex_path
    return engine


def compile_to_pdf_with_log(
    latex_content: str,
    output_path: str | Path | None = None,
    pdflatex_path: str = "pdflatex",
    engine: str | None = None,
) -> tuple[str | None, str]:
    """
    Compile a LaTeX document and return (pdf_path_or_None, log_excerpt).

    The engine is chosen via :func:`resolve_engine` (LuaLaTeX preferred, with a
    pdfLaTeX fallback). The log excerpt is the last portion of the engine .log
    file, suitable for surfacing to end users on failure.
    """
    log_excerpt = ""
    engine_name = resolve_engine(engine)
    binary = _engine_binary(engine_name, pdflatex_path)

    from app.latex.text_sanitize import sanitize_latex_body

    latex_content = sanitize_latex_body(latex_content)

    with get_compile_gate(), tempfile.TemporaryDirectory(prefix="matematex_") as tmpdir:
        tex_path = Path(tmpdir) / "document.tex"
        tex_path.write_text(latex_content, encoding="utf-8")

        needs_double_pass = any(t in latex_content for t in _DOUBLE_PASS_TRIGGERS)
        passes = 2 if needs_double_pass else 1

        last_return_code: int | None = None
        for _pass_num in range(passes):
            try:
                proc = subprocess.run(
                    [
                        binary,
                        "-interaction=nonstopmode",
                        # halt on first hard error so we don't loop on a broken doc
                        "-halt-on-error",
                        "-file-line-error",
                        "-output-directory", str(tmpdir),
                        str(tex_path),
                    ],
                    capture_output=True,
                    text=False,  # engines mix UTF-8 and latin1 in output
                    timeout=180,
                    cwd=tmpdir,
                )
                last_return_code = proc.returncode
                if proc.returncode != 0:
                    # No point running another pass after a hard failure.
                    break
            except FileNotFoundError as e:
                logger.error("latex_engine_not_found", engine=binary, error=str(e))
                return None, f"LaTeX-motor ikke funnet: '{binary}'."
            except subprocess.TimeoutExpired as e:
                logger.error("latex_timeout", engine=binary, error=str(e))
                return None, f"{engine_name} tidsavbrudd (>180s)."

        # Capture log excerpt (last ~80 lines is usually enough to find the cause)
        log_path = Path(tmpdir) / "document.log"
        if log_path.exists():
            try:
                full_log = log_path.read_text(encoding="utf-8", errors="replace")
                log_excerpt = "\n".join(full_log.splitlines()[-80:])
            except OSError:
                log_excerpt = ""

        pdf_in_tmp = Path(tmpdir) / "document.pdf"
        if not pdf_in_tmp.exists() or (last_return_code not in (0, None)):
            logger.error(
                "pdf_not_generated",
                engine=engine_name,
                return_code=last_return_code,
                has_log=bool(log_excerpt),
            )
            return None, log_excerpt

        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf_in_tmp, out)
            return str(out), log_excerpt

        # Caller is responsible for reading the file before tmpdir cleanup.
        return str(pdf_in_tmp), log_excerpt


def compile_to_pdf(
    latex_content: str,
    output_path: str | Path | None = None,
    pdflatex_path: str = "pdflatex",
    engine: str | None = None,
) -> str | None:
    """Backwards-compatible wrapper that discards the log excerpt."""
    pdf_path, _log = compile_to_pdf_with_log(
        latex_content=latex_content,
        output_path=output_path,
        pdflatex_path=pdflatex_path,
        engine=engine,
    )
    return pdf_path


def compile_latex_to_bytes(
    latex_content: str,
    pdflatex_path: str = "pdflatex",
    engine: str | None = None,
) -> tuple[bytes | None, str]:
    """Compile LaTeX and return PDF bytes plus log excerpt."""
    with tempfile.TemporaryDirectory(prefix="matematex_bytes_") as tmpdir:
        out = Path(tmpdir) / "document.pdf"
        pdf_path, log_excerpt = compile_to_pdf_with_log(
            latex_content=latex_content,
            output_path=out,
            pdflatex_path=pdflatex_path,
            engine=engine,
        )
        if pdf_path and Path(pdf_path).is_file():
            return Path(pdf_path).read_bytes(), log_excerpt
        return None, log_excerpt
