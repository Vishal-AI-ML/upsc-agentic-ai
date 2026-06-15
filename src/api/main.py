"""FastAPI Main Application"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.logging_config import setup_logging
from src.core import observability
from src.core.db import init_db
from src.core.vector_store import ensure_vector_storage
from src.core.email_utils import smtp_configured
from src.api.deps import get_current_user
from src.api.rate_limit import RateLimitMiddleware
from src.api.upload_limit import MaxUploadSizeMiddleware
from src.graph.app_graph import build_app
from src.graph.memory import close_memory
from src.api.routes import (
    mentor, planner, ncert, lecture, current_affairs,
    upload, pyq, evaluator, auth, history, feedback, chat,
)

# -------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------
setup_logging()
logger = logging.getLogger(__name__)


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
    init_db()
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

for module in _protected_routers:
    app.include_router(
        module.router,
        prefix=settings.api_prefix,
        dependencies=[Depends(get_current_user)],
    )
