"""
API v1 router — aggregates all v1 endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.assignments import router as assignments_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.eta import router as eta_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.jobs import router as jobs_router
from app.api.v1.endpoints.skills import router as skills_router
from app.api.v1.endpoints.technicians import router as technicians_router

# ── v1 Router ─────────────────────────────────────────────────────────────────
api_v1_router = APIRouter()

# ── Include sub-routers ───────────────────────────────────────────────────────
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router, prefix="/auth")
api_v1_router.include_router(technicians_router, prefix="/technicians")
api_v1_router.include_router(skills_router, prefix="/skills")
api_v1_router.include_router(jobs_router, prefix="/jobs")
api_v1_router.include_router(assignments_router, prefix="/assignments")
api_v1_router.include_router(assignments_router)
api_v1_router.include_router(eta_router)
api_v1_router.include_router(eta_router, prefix="/eta")

