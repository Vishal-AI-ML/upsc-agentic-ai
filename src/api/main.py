"""FastAPI Main Application"""
import importlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.logging_config import setup_logging
from src.core import observability
from src.core.error_monitoring import init_sentry, sentry_enabled
from src.core.db import init_db
from src.core.vector_store import ensure_vector_storage
from src.core.email_utils import smtp_configured
from src.api.deps import get_current_user
from src.api.rate_limit import RateLimitMiddleware
from src.api.upload_limit import MaxUploadSizeMiddleware
from src.graph.app_graph import build_app
from src.graph.memory import close_memory

# Core routers are always present.
from src.api.routes import (
    mentor, planner, ncert, lecture, current_affairs,
    upload, pyq, evaluator, auth, history, feedback, chat,
)

# -------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------
setup_logging()
logger = logging.getLogger(__name__)

# Optional HTTP-metrics middleware (admin-only monitoring dashboard). Older
# checkouts may not ship this module, so import defensively and fail-open.
try:
    from src.api.http_metrics_mw import HttpMetricsMiddleware
except Exception:  # pragma: no cover - optional feature
    HttpMetricsMiddleware = None
    logger.warning("HttpMetricsMiddleware not available; monitoring metrics off")


def _load_optional_routers(names):
    """Import optional route modules by name, skipping any that are absent.

    Keeps the app booting on older checkouts that do not yet ship the admin
    dashboard / background-job routes (cost, experiments, monitoring, etc.).
    """
    modules = []
    for name in names:
        try:
            modules.append(importlib.import_module(f"src.api.routes.{name}"))
        except Exception:
            logger.warning(
                "Optional route module '%s' not available; skipping", name
            )
    return modules


# Error monitoring (Sentry). No-op when SENTRY_DSN is unset; fail-open on error.
init_sentry()


# -------------------------------------------------------------------
# LIFESPAN
# -------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"\U0001f680 Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"\U0001f4cd API Prefix: {settings.api_prefix}")
    logger.info(f"\U0001f527 Debug Mode: {settings.debug}")
    logger.info(f"\U0001f4ca Langfuse: {observability.langfuse_enabled()}")
    logger.info(f"\U0001f6a8 Sentry: {sentry_enabled()}")
    init_db()
    # Best-effort purge of dead auth-token rows on boot (fail-open). A cron /
    # platform scheduler can also run scripts/cron_cleanup.py for periodic
    # hygiene between restarts.
    try:
        from src.core.token_cleanup import purge_expired_tokens
        purge_expired_tokens()
    except Exception:
        logger.warning("Startup token cleanup skipped", exc_info=True)
    # Register background job handlers so both the web process and any rq
    # worker can execute enqueued jobs (#10). Optional; fail-open.
    try:
        from src.core.job_handlers import register_all
        register_all()
    except Exception:
        logger.warning("Background job handlers not registered", exc_info=True)
    ensure_vector_storage()
    # Build the LangGraph supervisor once (checkpointer + long-term store wired)
    # and reuse it across all requests.
    app.state.agent_graph = build_app()
    logger.info("\U0001f916 Agent graph ready (supervisor + memory wired)")
    if settings.require_email_verification and not smtp_configured():
        logger.warning(
            "REQUIRE_EMAIL_VERIFICATION is on but SMTP is not configured -> "
            "email verification auto-disabled to avoid login lockout. "
            "Configure SMTP_* or set REQUIRE_EMAIL_VERIFICATION=false."
        )
    yield
    logger.info("\U0001f44b Shutting down...")
    observability.flush()  # push any pending Langfuse traces
    close_memory()  # release LangGraph DB pools cleanly


# -------------------------------------------------------------------
# APP
# -------------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-Powered UPSC Preparation System",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# -------------------------------------------------------------------
# CORS
# -------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# RATE LIMITING (per IP: rate_limit_requests / rate_limit_period)
# -------------------------------------------------------------------
app.add_middleware(RateLimitMiddleware)

# -------------------------------------------------------------------
# MAX UPLOAD SIZE (reject files larger than max_upload_mb)
# -------------------------------------------------------------------
app.add_middleware(MaxUploadSizeMiddleware)

# -------------------------------------------------------------------
# HTTP METRICS (roadmap #18) - optional, admin-only monitoring dashboard
# -------------------------------------------------------------------
# Records latency / status / endpoint per request. Added last so it is the
# OUTERMOST app middleware and times the full pipeline. Skipped when the module
# is not present in this checkout. Fail-open.
if HttpMetricsMiddleware is not None:
    app.add_middleware(HttpMetricsMiddleware)

# -------------------------------------------------------------------
# GLOBAL EXCEPTION HANDLER
# -------------------------------------------------------------------
# Catch-all for *unhandled* exceptions so the API always returns a clean JSON
# envelope and never leaks a stack trace to the client. FastAPI's own handlers
# for HTTPException (401/403/404/...) and request validation (422) still run
# as normal; this only fires for unexpected 500-class errors, which are logged
# server-side with the request method + path for debugging.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )


# -------------------------------------------------------------------
# PUBLIC ROUTES (no auth)
# -------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "app": settings.app_name,
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


# Auth router - OPEN (login yahin hota hai, protect nahi kar sakte)
app.include_router(auth.router, prefix=settings.api_prefix)

# -------------------------------------------------------------------
# PROTECTED ROUTES (JWT required)
# -------------------------------------------------------------------
_protected_routers = [
    mentor, planner, ncert, lecture,
    current_affairs, upload, pyq, evaluator,
    history, feedback, chat,
]

# Optional routers (admin dashboards + background jobs). Silently skipped if the
# corresponding module is not present in this checkout, so the app always boots.
_protected_routers += _load_optional_routers(
    ["progress", "cost", "jobs", "experiments", "monitoring"]
)

for module in _protected_routers:
    app.include_router(
        module.router,
        prefix=settings.api_prefix,
        dependencies=[Depends(get_current_user)],
    )
