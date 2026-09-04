"""
FieldOps AI – FastAPI Application Entry Point

Run with:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.middleware.cors import setup_cors
from app.middleware.logging import RequestLoggingMiddleware
from app.api.v1.router import api_v1_router

from app.database.seed import seed_db

# Configure structured logging before anything else
configure_logging()
logger = get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Application startup and shutdown lifecycle."""
    logger.info(
        "startup",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
        api_prefix=settings.API_PREFIX,
    )
    try:
        await seed_db()
    except Exception as err:
        logger.warning("startup_seed_warning", error=str(err))
    yield
    logger.info("shutdown", app=settings.APP_NAME)


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Enterprise-grade, AI-powered field operations management platform "
        "for intelligent technician dispatch and real-time ETA prediction."
    ),
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
setup_cors(app)
app.add_middleware(RequestLoggingMiddleware)

# ── Exception Handlers ────────────────────────────────────────────────────────
register_exception_handlers(app)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(api_v1_router, prefix=settings.API_PREFIX)
