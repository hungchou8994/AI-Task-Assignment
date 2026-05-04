from functools import lru_cache
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET_KEY_DEFAULTS = {
    "dev-session-secret-change-me",
    "change-me-in-production",
    "secret",
    "changeme",
}


class Settings(BaseSettings):
    """Single source of truth for all backend configuration.

    Values are read from environment variables (case-insensitive) or the .env
    file in the backend root.  All tuneable magic numbers live here so there
    are no scattered literals or os.environ calls throughout the codebase.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields in .env
    )

    # ------------------------------------------------------------------ #
    # Database                                                           #
    # ------------------------------------------------------------------ #
    database_url: str = Field(alias="DATABASE_URL")

    # ------------------------------------------------------------------ #
    # Gemini AI                                                          #
    # ------------------------------------------------------------------ #
    ai_agent_provider: str = Field(default="gemini", alias="AI_AGENT_PROVIDER")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_temperature: float = 0.2

    # ------------------------------------------------------------------ #
    # OpenAI-compatible AI                                               #
    # ------------------------------------------------------------------ #
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.2, alias="OPENAI_TEMPERATURE")

    # ------------------------------------------------------------------ #
    # AI pipeline tuning                                                 #
    # ------------------------------------------------------------------ #
    # Maximum bytes for a single email attachment; larger files are skipped
    ai_max_attachment_bytes: int = 10 * 1024 * 1024  # 10 MB
    # Number of URLs extracted from email body to actually fetch
    ai_url_fetch_cap: int = 5
    # Maximum characters kept after stripping a fetched URL's HTML
    ai_url_strip_chars: int = 20_000
    # Characters of source content stored as the "excerpt" in the DB
    ai_source_excerpt_chars: int = 500
    # Maximum characters stored for a task title
    ai_task_title_max_chars: int = 500
    # Minimum confidence required to auto-apply the top assignee recommendation.
    # Below this threshold recommendations are retained for review, but assignee
    # auto-application is disabled (manual-only mode).
    ai_assignee_auto_apply_confidence_threshold: float = 0.8
    # Extraction job orchestration hardening
    ai_extraction_job_max_attempts: int = Field(
        default=3,
        alias="AI_EXTRACTION_JOB_MAX_ATTEMPTS",
    )
    ai_extraction_job_retry_backoff_seconds: float = Field(
        default=0.35,
        alias="AI_EXTRACTION_JOB_RETRY_BACKOFF_SECONDS",
    )
    ai_extraction_job_timeout_seconds: float = Field(
        default=180.0,
        alias="AI_EXTRACTION_JOB_TIMEOUT_SECONDS",
    )
    ai_extraction_circuit_breaker_failure_threshold: int = Field(
        default=4,
        alias="AI_EXTRACTION_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
    )
    ai_extraction_circuit_breaker_cooldown_seconds: int = Field(
        default=120,
        alias="AI_EXTRACTION_CIRCUIT_BREAKER_COOLDOWN_SECONDS",
    )
    ai_extraction_dead_letter_ttl_seconds: int = Field(
        default=60 * 60 * 24,
        alias="AI_EXTRACTION_DEAD_LETTER_TTL_SECONDS",
    )

    # ------------------------------------------------------------------ #
    # MemPalace memory integration                                        #
    # ------------------------------------------------------------------ #
    memory_enabled: bool = Field(default=False, alias="MEMORY_ENABLED")
    memory_palace_root: str = Field(
        default="/var/lib/ai-task-memory",
        alias="MEMORY_PALACE_ROOT",
    )
    memory_default_results: int = Field(default=5, alias="MEMORY_DEFAULT_RESULTS")
    memory_max_context_chars: int = Field(
        default=2500,
        alias="MEMORY_MAX_CONTEXT_CHARS",
    )
    memory_allowed_scope_widening: bool = Field(
        default=True,
        alias="MEMORY_ALLOWED_SCOPE_WIDENING",
    )
    memory_redaction_enabled: bool = Field(
        default=True,
        alias="MEMORY_REDACTION_ENABLED",
    )
    memory_command_timeout_seconds: int = Field(
        default=20,
        alias="MEMORY_COMMAND_TIMEOUT_SECONDS",
    )

    # ------------------------------------------------------------------ #
    # Prompt version                                                     #
    # ------------------------------------------------------------------ #
    prompt_version: str = Field(default="v2", alias="PROMPT_VERSION")

    # ------------------------------------------------------------------ #
    # CORS                                                               #
    # ------------------------------------------------------------------ #
    cors_allowed_origins: List[str] = ["http://localhost:5173"]

    # ------------------------------------------------------------------ #
    # Auth / Session                                                     #
    # ------------------------------------------------------------------ #
    session_secret_key: str = Field(
        default="dev-session-secret-change-me",
        alias="SESSION_SECRET_KEY",
    )
    session_cookie_name: str = "ai_task_session"
    session_cookie_secure: bool = Field(default=False, alias="SESSION_COOKIE_SECURE")

    # ------------------------------------------------------------------ #
    # Telegram notifications                                             #
    # ------------------------------------------------------------------ #
    telegram_notifications_enabled: bool = Field(
        default=False,
        alias="TELEGRAM_NOTIFICATIONS_ENABLED",
    )
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    app_base_url: str = Field(default="http://localhost:3000", alias="APP_BASE_URL")

    @field_validator("session_secret_key")
    @classmethod
    def _reject_insecure_secret_key(cls, value: str) -> str:
        if value.lower() in _INSECURE_SECRET_KEY_DEFAULTS:
            import warnings

            warnings.warn(
                "SESSION_SECRET_KEY is set to an insecure default value. "
                "Set a strong random secret in production via the SESSION_SECRET_KEY "
                "environment variable (e.g. `openssl rand -hex 32`).",
                stacklevel=2,
            )
        return value

    @field_validator("ai_agent_provider")
    @classmethod
    def _validate_ai_agent_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"gemini", "openai"}:
            raise ValueError("AI_AGENT_PROVIDER must be one of: gemini, openai")
        return normalized

    @field_validator(
        "memory_default_results",
        "memory_max_context_chars",
        "memory_command_timeout_seconds",
    )
    @classmethod
    def _validate_positive_memory_bounds(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("memory bounds must be positive")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
