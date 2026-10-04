"""
Pytest configuration and global async fixtures.
Enforces strict test database isolation (TEST_DATABASE_URL / fieldops_ai_test).
Protects the production and development database ('fieldops_ai') from test mutations and cleanup.
"""

import asyncio
import os
from urllib.parse import urlparse
import httpx
from httpx import ASGITransport
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# ── 1. Strict Test Database Isolation & Safety Verification ────────────────────
test_db_url = settings.effective_test_database_url

parsed = urlparse(test_db_url)
db_name = parsed.path.lstrip("/").lower()

if not (db_name.endswith("_test") or "fieldops_ai_test" in db_name):
    raise RuntimeError(
        f"CRITICAL SAFETY VIOLATION: Test database URL '{test_db_url}' does not target a dedicated test database! "
        "Test execution is aborted to protect development data."
    )

if test_db_url == settings.DATABASE_URL and not settings.DATABASE_URL.endswith("_test"):
    raise RuntimeError(
        f"CRITICAL SAFETY VIOLATION: Test database '{test_db_url}' is identical to development database! "
        "Tests must run in an isolated test database."
    )

# Override runtime settings and environment so all app modules use the isolated test database
settings.DATABASE_URL = test_db_url
settings.TEST_DATABASE_URL = test_db_url
os.environ["DATABASE_URL"] = test_db_url
os.environ["TEST_DATABASE_URL"] = test_db_url

# ── 2. Bind Test Engine & AsyncSessionLocal to Test Database ───────────────────
import app.database.session as db_session_module

test_engine = create_async_engine(
    test_db_url,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=False,
    future=True,
)
test_async_session_maker = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Replace module-level engine and sessionmaker so all app services use the test database
db_session_module.engine = test_engine
db_session_module.AsyncSessionLocal = test_async_session_maker

# Now safe to import app models, seed, and main application
from app.database.base import Base
from app.database.seed import seed_db, seed_demo_operational_data
from app.main import app

# Auto-patch httpx.AsyncClient to use ASGITransport when no transport is provided
_original_async_client_init = httpx.AsyncClient.__init__


def _patched_async_client_init(self, *args, **kwargs):
    if "transport" not in kwargs or kwargs["transport"] is None:
        kwargs["transport"] = ASGITransport(app=app)
    _original_async_client_init(self, *args, **kwargs)


httpx.AsyncClient.__init__ = _patched_async_client_init


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def seed_test_database(event_loop):
    """
    Session fixture:
    Initializes schema and baseline system seed on the ISOLATED TEST DATABASE ONLY.
    Teardown cleans test records from the TEST database only.
    The development database ('fieldops_ai') is NEVER touched.
    """
    # 1. Ensure test database tables exist
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Seed baseline system configuration (roles, skills, baseline user accounts) into test DB
    await seed_db()

    yield

    # 3. Teardown: Safely clean up the TEST database only
    try:
        from app.database.cleanup_test_data import cleanup_database
        async with test_async_session_maker() as test_session:
            await cleanup_database(test_session)
    except Exception as e:
        print(f"Post-test cleanup warning: {e}")


@pytest.fixture(autouse=True)
async def ensure_test_baseline_data(request):
    """
    Fixture ensuring that tests requiring TECH-001 have it available
    in the TEST database, while allowing test_persistence_and_admin_security to
    verify the zero-operational startup baseline.
    """
    if "test_persistence_and_admin_security" in request.node.nodeid:
        yield
        return

    # Check if TECH-001 exists in test database; if not, seed test operational data
    from app.models.technician import Technician
    async with test_async_session_maker() as session:
        tech1 = (
            await session.execute(
                select(Technician).where(Technician.employee_code == "TECH-001")
            )
        ).scalar_one_or_none()
        if not tech1:
            await seed_demo_operational_data(session)
            await session.commit()

    yield
