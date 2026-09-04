"""
Development database seed module.
Populates PostgreSQL with default enterprise security roles and development demo users idempotently.
"""

import asyncio
from datetime import datetime, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.database.session import AsyncSessionLocal
from app.models.enums import JobStatus, Priority, UserRole, UserStatus
from app.models.job import Job
from app.models.role import Role
from app.models.skill import Skill
from app.models.technician import Technician
from app.models.user import User

logger = get_logger(__name__)

# Default Enterprise Security Roles
DEFAULT_ROLES = [
    {
        "name": UserRole.ADMINISTRATOR.value,
        "description": "Full enterprise platform administration, user management, and system configuration.",
    },
    {
        "name": UserRole.DISPATCHER.value,
        "description": "Dispatch control center monitoring, job management, and technician assignment.",
    },
    {
        "name": UserRole.TECHNICIAN.value,
        "description": "Field workforce work order execution, route navigation, and status updates.",
    },
]

# Development Seed Users (Clean Enterprise Credentials)
DEFAULT_USERS = [
    {
        "email": "admin@fieldops.ai",
        "password": "Admin@123",
        "full_name": "System Administrator",
        "role_name": UserRole.ADMINISTRATOR.value,
    },
    {
        "email": "dispatcher@fieldops.ai",
        "password": "Dispatch@123",
        "full_name": "Priya Nair",
        "role_name": UserRole.DISPATCHER.value,
    },
    {
        "email": "technician@fieldops.ai",
        "password": "Tech@123",
        "full_name": "Alex Rivera",
        "role_name": UserRole.TECHNICIAN.value,
        "employee_code": "TECH-001",
    },
    {
        "email": "tech@fieldops.ai",
        "password": "Tech@123",
        "full_name": "Alex Rivera",
        "role_name": UserRole.TECHNICIAN.value,
        "employee_code": "TECH-002",
    },
]


async def seed_roles(session: AsyncSession) -> dict[str, Role]:
    """
    Insert default enterprise roles if they do not exist.
    Returns a dictionary mapping role name -> Role instance.
    """
    roles_map: dict[str, Role] = {}
    for role_info in DEFAULT_ROLES:
        stmt = select(Role).where(Role.name == role_info["name"])
        result = await session.execute(stmt)
        existing_role = result.scalar_one_or_none()

        if existing_role:
            roles_map[existing_role.name] = existing_role
        else:
            new_role = Role(
                id=uuid.uuid4(),
                name=role_info["name"],
                description=role_info["description"],
            )
            session.add(new_role)
            await session.flush()
            roles_map[new_role.name] = new_role
            logger.info("seed_role_created", role=new_role.name)

    return roles_map


async def seed_users(session: AsyncSession, roles_map: dict[str, Role]) -> None:
    """
    Insert development users idempotently.
    Updates credentials and status if existing to guarantee demo login functionality.
    """
    now = datetime.now(timezone.utc)

    # Seed realistic skills taxonomy idempotently
    default_skills_data = [
        {"skill_name": "HVAC Master", "category": "HVAC", "description": "Master certification in industrial HVAC chilling and ventilation systems."},
        {"skill_name": "High Voltage Specialist", "category": "Electrical", "description": "Certification for high-voltage industrial grid maintenance and safety."},
        {"skill_name": "Fiber Optics Specialist", "category": "Telecommunications", "description": "Fiber optic splicing, OTDR testing, and infrastructure rollout."},
        {"skill_name": "Enterprise Router Admin", "category": "Network", "description": "Cisco/BGP routing configuration, VPN tunnels, and core network diagnostics."},
        {"skill_name": "Precision Sensor Calibration", "category": "Calibration", "description": "Industrial IoT sensor testing, pressure gauge calibration, and compliance documentation."},
    ]

    hvac_skill = None
    for s_info in default_skills_data:
        s_stmt = select(Skill).where(Skill.skill_name == s_info["skill_name"])
        s_res = await session.execute(s_stmt)
        existing_s = s_res.scalar_one_or_none()
        if not existing_s:
            new_s = Skill(
                id=uuid.uuid4(),
                skill_name=s_info["skill_name"],
                category=s_info["category"],
                description=s_info["description"],
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            session.add(new_s)
            await session.flush()
            if s_info["skill_name"] == "HVAC Master":
                hvac_skill = new_s
        else:
            if s_info["skill_name"] == "HVAC Master":
                hvac_skill = existing_s


    for user_info in DEFAULT_USERS:
        email = user_info["email"].strip().lower()
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        role = roles_map.get(user_info["role_name"])
        if not role:
            logger.error("seed_user_role_missing", role_name=user_info["role_name"])
            continue

        hashed_pwd = get_password_hash(user_info["password"])

        if existing_user:
            existing_user.password_hash = hashed_pwd
            existing_user.role_id = role.id
            existing_user.status = UserStatus.ACTIVE
            existing_user.updated_at = now
            user_obj = existing_user
            logger.info("seed_user_updated", email=email)
        else:
            new_user = User(
                id=uuid.uuid4(),
                role_id=role.id,
                email=email,
                full_name=user_info["full_name"],
                password_hash=hashed_pwd,
                status=UserStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            session.add(new_user)
            await session.flush()
            user_obj = new_user
            logger.info("seed_user_created", email=email, role=role.name)

        # Create Technician profile if user role is Technician
        if user_info["role_name"] == UserRole.TECHNICIAN.value:
            tech_stmt = select(Technician).where(Technician.user_id == user_obj.id)
            tech_res = await session.execute(tech_stmt)
            existing_tech = tech_res.scalar_one_or_none()
            if not existing_tech:
                new_tech = Technician(
                    id=uuid.uuid4(),
                    user_id=user_obj.id,
                    employee_code=user_info.get("employee_code", f"TECH-{str(user_obj.id)[:4]}"),
                    primary_skill_id=hvac_skill.id if hvac_skill else None,
                    years_experience=5,
                    availability_status="AVAILABLE",
                    current_latitude=37.7550,
                    current_longitude=-122.4300,
                )
                session.add(new_tech)
                await session.flush()
                logger.info("seed_technician_profile_created", user_id=str(user_obj.id))
            else:
                if existing_tech.current_latitude is None or existing_tech.current_longitude is None:
                    existing_tech.current_latitude = 37.7550
                    existing_tech.current_longitude = -122.4300
                    await session.flush()



async def seed_jobs(session: AsyncSession) -> None:
    """Seed initial development jobs idempotently."""
    now = datetime.now(timezone.utc)

    job_chk = await session.execute(select(Job).where(Job.job_number == "JOB-10001"))
    if job_chk.scalar_one_or_none():
        return

    disp_res = await session.execute(select(User).where(User.email == "dispatcher@fieldops.ai"))
    disp_user = disp_res.scalar_one_or_none()

    skill_res = await session.execute(select(Skill).where(Skill.skill_name == "HVAC Master"))
    hvac_skill = skill_res.scalar_one_or_none()

    if not hvac_skill:
        return

    default_jobs = [
        {
            "job_number": "JOB-10001",
            "customer_name": "Acme Industrial Logistics",
            "customer_phone": "+1 (555) 234-5678",
            "address": "742 Evergreen Terrace, Sector 4, Springfield",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "priority": Priority.HIGH,
            "status": JobStatus.NEW,
            "description": "Emergency HVAC chiller unit main compressor overhaul and coolant flush.",
        },
        {
            "job_number": "JOB-10002",
            "customer_name": "Apex Telecommunications Grid",
            "customer_phone": "+1 (555) 876-5432",
            "address": "100 Innovation Way, Building B, Tech City",
            "latitude": 37.7833,
            "longitude": -122.4167,
            "priority": Priority.MEDIUM,
            "status": JobStatus.NEW,
            "description": "Routine quarterly inspection of rooftop ventilation and climate control.",
        },
    ]

    for j_data in default_jobs:
        j_obj = Job(
            id=uuid.uuid4(),
            job_number=j_data["job_number"],
            customer_name=j_data["customer_name"],
            customer_phone=j_data["customer_phone"],
            address=j_data["address"],
            latitude=j_data["latitude"],
            longitude=j_data["longitude"],
            required_skill_id=hvac_skill.id,
            priority=j_data["priority"],
            status=j_data["status"],
            scheduled_time=now,
            description=j_data["description"],
            created_by=disp_user.id if disp_user else None,
        )
        session.add(j_obj)
    await session.flush()


import app.models  # Ensure all ORM models are registered
from app.database.base import Base
from app.database.session import AsyncSessionLocal, engine


async def seed_db() -> None:
    """Master idempotent database seed runner."""
    logger.info("seed_db_start")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        try:
            roles_map = await seed_roles(session)
            await seed_users(session, roles_map)
            await seed_jobs(session)
            await session.commit()
            logger.info("seed_db_success")
        except Exception as err:
            await session.rollback()
            logger.exception("seed_db_failed", error=str(err))
            raise


if __name__ == "__main__":
    asyncio.run(seed_db())
