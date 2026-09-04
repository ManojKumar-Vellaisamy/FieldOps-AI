"""
Pytest configuration and global async fixtures.
Configures httpx.AsyncClient to automatically route requests through FastAPI's ASGITransport
so that integration tests execute cleanly in-process without requiring a live socket server.
"""

import asyncio
import httpx
from httpx import ASGITransport
import pytest

from app.database.seed import seed_db
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
    """Seed the database once for the entire test session."""
    await seed_db()
