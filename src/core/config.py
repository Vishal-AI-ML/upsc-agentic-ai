"""Core configuration - Pydantic Settings"""
from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.secret_utils import resolve_jwt_secret


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "UPSC AI Pro"
    app_version: str = "2.0.0"
    debug: bool = False

    # API
    api_prefix: str = "/api/v1"

    # LLM - Google Gemini
    google_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    llm_fast_model: str = "gemini-2.5-flash-lite"
    llm_temperature: float = 0.3
    llm_max_retries: int = 1  # fail fast -> fallback provider (quota errors dont recover on retry)

    # LLM fallback provider - Groq (free tier; used when Gemini hits 429)
    # Free key: https://console.groq.com  |  empty key => Gemini-only (no change)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"
    groq_whisper_model: str = "whisper-large-v3-turbo"  # Groq Speech-to-Text (audio -> text)
    enable_provider_fallback: bool = True

    # Embeddings
    embedding_model: str = "models/gemini-embedding-001"

    # Vector Store (Chroma = local dev fallback; Qdrant = production/cloud)
    chroma_persist_dir: str = "chroma_db"
    chunk_size: int = 1000
    chunk_overlap: int = 150

    # Qdrant managed vector DB. Empty qdrant_url => automatically falls back to
    # local Chroma (so local dev keeps working without Qdrant).
    #   Cloud free cluster:
    #     QDRANT_URL=https://<id>.<region>.aws.cloud.qdrant.io:6333
    #     QDRANT_API_KEY=<your-api-key>
    #   Self-hosted later (e.g. Oracle VM): QDRANT_URL=http://localhost:6333
    #     (api key optional for a private self-hosted instance)
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    # Network timeout (seconds) for Qdrant client operations.
    qdrant_timeout: int = 30

    # NCERT content library (folder of class/subject/chapter PDFs).
    # Empty/missing => NCERT browse shows no content (app still runs, no crash).
    # In prod point to a persistent path, e.g. NCERT_DATA_DIR=/var/data/ncert
    ncert_data_dir: str = "data/ncert"

    # Uploads
    max_upload_mb: int = 20  # is se badi file -> 413 (Too Large)

    # Database (multi-user + history). Postgres in prod, SQLite local fallback.
    # e.g. DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
    database_url: str = ""

    # Tavily Search
    tavily_api_key: str = ""

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds

    # CORS - sirf apne asli frontend origins (NOT "*" with credentials).
    # .env mein override kar sakte ho, e.g.:
    #   CORS_ORIGINS=["http://localhost:8501","https://myapp.com"]
    cors_origins: list[str] = [
        "http://localhost:8501",   # Streamlit default
        "http://127.0.0.1:8501",
        "http://localhost:3000",   # React/Next dev (agar use karo)
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        
    ]

    # Observability - Langfuse (empty keys => tracing OFF, app unchanged)
    langfuse_enabled: bool = True
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Logging - DEBUG/INFO/WARNING/ERROR; empty => auto from debug flag
    log_level: str = ""

    # Auth / JWT
    jwt_secret: str = ""                      # .env se aayega
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440   # 24 hours
    # Refresh token validity (minutes) - default 30 days. Access tokens can
    # stay short-lived because a long-lived, ROTATING & REVOCABLE refresh
    # token (see /auth/refresh + /auth/logout) keeps sessions alive. Lower
    # access_token_expire_minutes to ~30 once the frontend wires up refresh.
    refresh_token_expire_minutes: int = 43200  # 30 days

    # Email (SMTP) - password reset links.
    # Empty SMTP creds => reset link is logged to the server console instead of emailed (dev).
    # Gmail: smtp_host=smtp.gmail.com, smtp_port=587, smtp_user=<you@gmail.com>,
    #   smtp_password=<16-char Gmail App Password>, smtp_from=<you@gmail.com>
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""                        # blank => uses smtp_user
    smtp_use_tls: bool = True
    # Frontend base URL used to build the reset link (no trailing slash)
    frontend_url: str = "http://localhost:8501"
    # Password reset token validity (minutes)
    reset_token_expire_minutes: int = 30
    # Email verification token validity (minutes) - default 24 hours
    verification_token_expire_minutes: int = 1440
    # Require email verification before login (strict). Set REQUIRE_EMAIL_VERIFICATION=false in .env to disable.
    require_email_verification: bool = True

    # Response cache (Upstash Redis, REST) - skip re-running the agent graph for
    # a repeated identical question -> lower latency + LLM cost.
    # Empty creds OR response_cache_enabled=false => cache is a no-op (app unchanged).
    #   Free DB: https://console.upstash.com -> Redis -> REST API (URL + TOKEN)
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    response_cache_enabled: bool = False
    response_cache_ttl_seconds: int = 86400   # 24h
    response_cache_scope: str = "thread"       # thread | user | global

    # Reflection / self-critique (#7). After generation, a critic scores the
    # answer and (when weak) a bounded revise pass rewrites it. Fail-open: any
    # critic error keeps the original answer. reflection_enabled=false restores
    # the previous single-pass behaviour.
    reflection_enabled: bool = True
    reflection_min_score: int = 7          # 1-10; below this triggers a revise
    reflection_max_revisions: int = 1      # bounded loop (cost + latency guard)

    # Plan-and-execute (#7). For genuinely complex, multi-part questions the
    # mentor path can decompose -> execute each sub-step -> synthesize. OFF by
    # default because it issues several extra LLM calls (latency + free-tier
    # quota). Enable with PLAN_EXECUTE_ENABLED=true.
    plan_execute_enabled: bool = False
    plan_execute_min_words: int = 30       # complexity gate (aligns w/ model_router)
    plan_execute_max_steps: int = 5        # cap sub-steps (cost guard)

    # MCP (Model Context Protocol) server - expose KB/tools to external MCP
    # clients (Claude Desktop, Cursor, other agents). Opt-in; when disabled
    # no MCP dependency loads and app boot is unchanged.
    mcp_enabled: bool = False
    mcp_transport: str = "stdio"   # "stdio" (local desktop) | "http"/"sse" (remote)
    mcp_http_path: str = "/mcp"    # mount path when served over HTTP inside FastAPI

    # Error monitoring - Sentry (empty SENTRY_DSN => disabled, app unchanged).
    # Free Developer plan: 5K errors/month. FastAPI + Starlette integrations
    # auto-enable. Fail-open: any init error never blocks app boot.
    #   Free project + DSN: https://sentry.io  (create a Python -> FastAPI project)
    sentry_dsn: str = ""
    sentry_environment: str = "production"
    sentry_traces_sample_rate: float = 0.0   # perf tracing off by default (cost)
    sentry_profiles_sample_rate: float = 0.0

    @model_validator(mode="after")
    def _normalize_env_values(self):
        """Clean secrets/URLs pasted into hosting dashboards.

        Hosting UIs (Render etc.) often capture surrounding quotes or stray
        whitespace. Strip them so downstream clients (SQLAlchemy, psycopg,
        Qdrant) receive valid values. Also upgrade the legacy ``postgres://``
        scheme that SQLAlchemy 2.0 no longer accepts.
        """
        def _clean(value):
            if isinstance(value, str):
                return value.strip().strip('"').strip("'").strip()
            return value

        for field_name in (
            "database_url", "qdrant_url", "qdrant_api_key",
            "google_api_key", "groq_api_key", "tavily_api_key",
            "jwt_secret", "langfuse_public_key", "langfuse_secret_key",
            "langfuse_host", "embedding_model",
            "upstash_redis_rest_url", "upstash_redis_rest_token",
            "sentry_dsn", "sentry_environment",
        ):
            setattr(self, field_name, _clean(getattr(self, field_name)))

        if self.database_url.startswith("postgres://"):
            self.database_url = "postgresql://" + self.database_url[len("postgres://") :]

        # Fail fast on a forgeable JWT secret in production; ephemeral in dev.
        self.jwt_secret = resolve_jwt_secret(
            self.jwt_secret, is_production=not self.debug
        )

        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
