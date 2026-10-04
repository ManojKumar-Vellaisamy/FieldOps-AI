"""
Database utility for test operational data teardown in ISOLATED TEST DATABASES ONLY.

CRITICAL SAFETY GUARD:
This utility contains strict safety verification ensuring it CANNOT execute against
the development database ('fieldops_ai') or any production database.
It will fail closed with a RuntimeError if the active database target does not
explicitly target an isolated test database.
"""

import asyncio
from urllib.parse import urlparse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.eta_override import ETAOverride
from app.models.job import Job
from app.models.role import Role
from app.models.skill import Skill
from app.models.technician import Technician
from app.models.user import User

LEGITIMATE_EMAILS = {"admin@fieldops.ai", "dispatcher@fieldops.ai", "technician@fieldops.ai"}
LEGITIMATE_SKILLS = {
    "HVAC Master",
    "High Voltage Specialist",
    "Fiber Optics Specialist",
    "Enterprise Router Admin",
    "Precision Sensor Calibration",
    "AC Repair",
}


def assert_safe_test_database_context(session: AsyncSession) -> None:
    """
    Safety guard: Verifies that cleanup is strictly executing against an isolated test database.
    Fails closed immediately if targeted at development ('fieldops_ai') or production.
    """
    db_name = ""
    bind = session.bind
    if bind and hasattr(bind, "url") and bind.url:
        db_name = (bind.url.database or "").lower()
    elif settings.DATABASE_URL:
        db_name = urlparse(settings.DATABASE_URL).path.lstrip("/").lower()

    if not (db_name.endswith("_test") or "fieldops_ai_test" in db_name):
        raise RuntimeError(
            f"FATAL SAFETY GUARD VIOLATION: Database cleanup was attempted against active database '{db_name}'. "
            "Destructive cleanup is strictly prohibited on production and development databases! "
            "Tests must be executed against a dedicated test database (e.g. 'fieldops_ai_test')."
        )


async def cleanup_database(session: AsyncSession | None = None) -> dict[str, int]:
    """
    Purges test operational data in ISOLATED TEST DATABASES ONLY.
    Fails closed if invoked against the development database.
    """
    async def _do_cleanup(sess: AsyncSession):
        assert_safe_test_database_context(sess)

        # 1. Delete all ETA overrides
        await sess.execute(delete(ETAOverride))

        # 2. Delete assignments
        await sess.execute(delete(Assignment))

        # 3. Delete audit logs
        await sess.execute(delete(AuditLog))

        # 4. Delete demo/test jobs
        await sess.execute(delete(Job))

        # 5. Delete test technicians
        await sess.execute(delete(Technician))

        # 6. Delete test users
        await sess.execute(delete(User).where(~User.email.in_(LEGITIMATE_EMAILS)))

        # 7. Delete test skills
        await sess.execute(delete(Skill).where(~Skill.skill_name.in_(LEGITIMATE_SKILLS)))

        await sess.commit()

        counts = {
            "users": await sess.scalar(select(func.count(User.id))),
            "technicians": await sess.scalar(select(func.count(Technician.id))),
            "jobs": await sess.scalar(select(func.count(Job.id))),
            "assignments": await sess.scalar(select(func.count(Assignment.id))),
            "eta_overrides": await sess.scalar(select(func.count(ETAOverride.id))),
            "audit_logs": await sess.scalar(select(func.count(AuditLog.id))),
            "skills": await sess.scalar(select(func.count(Skill.id))),
            "roles": await sess.scalar(select(func.count(Role.id))),
        }
        return counts

    if session is not None:
        return await _do_cleanup(session)

    async with AsyncSessionLocal() as sess:
        return await _do_cleanup(sess)


async def cleanup_test_jobs(session: AsyncSession | None = None) -> int:
    """Safely cleans test jobs in test database only."""
    async def _do(sess: AsyncSession):
        assert_safe_test_database_context(sess)
        await sess.execute(delete(ETAOverride))
        await sess.execute(delete(Assignment))
        await sess.execute(delete(AuditLog))
        await sess.execute(delete(Job))
        await sess.commit()
        return 0

    if session is not None:
        return await _do(session)
    async with AsyncSessionLocal() as sess:
        return await _do(sess)


async def cleanup_demo_technicians(session: AsyncSession | None = None) -> int:
    """Safely cleans test technicians in test database only."""
    async def _do(sess: AsyncSession):
        assert_safe_test_database_context(sess)
        await sess.execute(delete(Assignment))
        await sess.execute(delete(Technician))
        await sess.execute(delete(User).where(~User.email.in_(LEGITIMATE_EMAILS)))
        await sess.commit()
        return 0

    if session is not None:
        return await _do(session)
    async with AsyncSessionLocal() as sess:
        return await _do(sess)


async def main():
    print("Verifying test database safety guard...")
    try:
        await cleanup_database()
        print("Cleanup completed.")
    except RuntimeError as err:
        print(f"Safety guard properly prevented execution: {err}")


if __name__ == "__main__":
    asyncio.run(main())
