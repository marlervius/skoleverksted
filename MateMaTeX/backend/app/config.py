"""
Application configuration via environment variables.
Uses pydantic-settings for validation and typing.
Supports both local development (.env) and production (Render/Supabase).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Unified application settings."""

    # ---- Database (PostgreSQL; optional) ----
    database_url: str = Field(
        default="",
        description="PostgreSQL connection string (asyncpg), e.g. Neon or self-hosted",
    )

    # ---- Optional API protection ----
    mate_api_key: str = Field(
        default="",
        description="If set, protected routes require X-API-Key or Bearer matching this value",
    )

    # ---- LLM API keys ----
    google_api_key: str = Field(default="", description="Google Gemini API key")
    anthropic_api_key: str = Field(default="", description="Anthropic Claude API key")
    openai_api_key: str = Field(default="", description="OpenAI API key")
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama base URL (local dev only)",
    )

    # ---- LLM defaults ----
    primary_provider: str = Field(default="google")
    primary_model: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model ID used everywhere. See https://ai.google.dev/gemini-api/docs/models",
    )
    fallback_provider: str = Field(default="anthropic")
    fallback_model: str = Field(
        default="claude-3-5-haiku-latest",
        description="Model used when primary fails.",
    )
    temperature: float = Field(default=0.15, ge=0.0, le=2.0)
    max_retries: int = Field(default=3, ge=1, le=10)

    # ---- App ----
    environment: str = Field(
        default="development",
        description="'development' or 'production'",
    )
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    pdflatex_path: str = Field(default="pdflatex")
    latex_engine: str = Field(
        default="auto",
        description=(
            "LaTeX engine for final PDF compilation: 'auto' prefers lualatex "
            "(professional OpenType fonts) and falls back to pdflatex; or force "
            "'lualatex' | 'xelatex' | 'pdflatex'."
        ),
    )
    output_dir: str = Field(default="output")
    max_verification_retries: int = Field(default=2, ge=1, le=10)
    max_content_quality_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Author retries when kapittel fails the content-quality gate",
    )
    skip_editor: bool = Field(
        default=False,
        description="If True, skip the LLM editor pass for all material types",
    )
    skip_editor_material_types: str = Field(
        default="arbeidsark,prøve,differensiert",
        description="Comma-separated material types that skip the LLM editor (faster)",
    )
    pipeline_max_seconds: int = Field(
        default=420,
        ge=30,
        le=3600,
        description=(
            "Soft wall-clock budget for a job. When exceeded, the pipeline stops "
            "retrying and delivers the best document it has (fallback if needed)."
        ),
    )
    max_author_runs: int = Field(
        default=5,
        ge=2,
        le=15,
        description="Hard cap on author LLM invocations per job (prevents retry loops)",
    )
    verification_fail_open: bool = Field(
        default=False,
        description=(
            "If True, SymPy-confirmed fasit errors may still be delivered as "
            "completed_with_warnings. Default False enforces grunnlov §1."
        ),
    )
    launch_grades: str = Field(
        default="VG1 1T,VG2 R1",
        description=(
            "Comma-separated grades shown by default in the UI (grunnlov §5 — "
            "smalt slår bredt). Set to empty to expose all grades."
        ),
    )
    max_latex_chars: int = Field(
        default=500_000,
        description="Maximum LaTeX body size accepted by compile/export endpoints",
    )
    max_concurrent_compiles: int = Field(
        default=2,
        ge=1,
        le=8,
        description=(
            "Global cap on simultaneous LaTeX engine processes. Keep low (1-2) "
            "on memory-constrained hosts like Render free tier (512MB)."
        ),
    )
    max_concurrent_jobs: int = Field(
        default=2,
        ge=1,
        le=8,
        description="Max generation pipelines running at the same time",
    )
    database_ssl_verify: bool = Field(
        default=True,
        description="Verify TLS certificates for DATABASE_URL (disable only in local dev)",
    )

    # ---- Supabase auth (optional) ----
    supabase_jwt_secret: str = Field(
        default="",
        description="Supabase JWT secret for verifying Bearer tokens (HS256)",
    )
    dev_user_uuid: str = Field(
        default="",
        description="Fallback UUID for DB writes when auth returns anonymous/api-user",
    )

    # ---- CORS ----
    frontend_url: str = Field(
        default="http://localhost:3000",
        description="Frontend URL (overridden in production)",
    )

    # ---- Render ----
    port: int = Field(default=10000)

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()


# Backward-compatible aliases used by existing code
class LLMProviderConfig:
    """Thin wrapper that delegates to Settings for backward compat."""

    def __init__(self) -> None:
        s = get_settings()
        self.primary_provider = s.primary_provider
        self.primary_model = s.primary_model
        self.fallback_provider = s.fallback_provider
        self.fallback_model = s.fallback_model
        self.google_api_key = s.google_api_key
        self.anthropic_api_key = s.anthropic_api_key
        self.openai_api_key = s.openai_api_key
        self.ollama_base_url = s.ollama_base_url
        self.temperature = s.temperature
        self.max_retries = s.max_retries


class AppConfig:
    """Thin wrapper that delegates to Settings for backward compat."""

    def __init__(self) -> None:
        s = get_settings()
        self.debug = s.debug
        self.log_level = s.log_level
        self.pdflatex_path = s.pdflatex_path
        self.latex_engine = s.latex_engine
        self.output_dir = s.output_dir
        self.max_verification_retries = s.max_verification_retries
        self.max_content_quality_retries = s.max_content_quality_retries
        self.verification_fail_open = s.verification_fail_open
        self.launch_grades = s.launch_grades
        self.max_latex_chars = s.max_latex_chars
        self.skip_editor = s.skip_editor
        self.skip_editor_material_types = s.skip_editor_material_types
        self.pipeline_max_seconds = s.pipeline_max_seconds
        self.max_author_runs = s.max_author_runs
        self.llm = LLMProviderConfig()


def get_config() -> AppConfig:
    """Backward-compatible config getter used by existing modules."""
    return AppConfig()
