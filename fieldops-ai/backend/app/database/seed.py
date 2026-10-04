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
from app.models.role import Role
from app.models.skill import Skill
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
        "full_name": "Field Technician",
        "role_name": UserRole.TECHNICIAN.value,
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
    NOTE: Field technicians are NOT created automatically; they must be provisioned
    by an Administrator via the Technician Management interface.
    """
    now = datetime.now(timezone.utc)

    # Seed realistic skills taxonomy idempotently (matching all enterprise categories)
    default_skills_data = [
        {"skill_name": "HVAC Master", "category": "HVAC", "description": "Master certification in industrial HVAC chilling and ventilation systems."},
        {"skill_name": "High Voltage Specialist", "category": "Electrical", "description": "Certification for high-voltage industrial grid maintenance and safety."},
        {"skill_name": "Fiber Optics Specialist", "category": "Telecommunications", "description": "Fiber optic splicing, OTDR testing, and infrastructure rollout."},
        {"skill_name": "Enterprise Router Admin", "category": "Network", "description": "Cisco/BGP routing configuration, VPN tunnels, and core network diagnostics."},
        {"skill_name": "Precision Sensor Calibration", "category": "Calibration", "description": "Industrial IoT sensor testing, pressure gauge calibration, and compliance documentation."},
        {"skill_name": "AC Repair", "category": "Electrical", "description": "Commercial and residential air conditioning maintenance, diagnosis, and refrigerant recovery."},
        {"skill_name": "Master Plumber & Pipefitter", "category": "Plumbing & Piping", "description": "Commercial piping, hydronic heating, backflow prevention, and drainage diagnostics."},
        {"skill_name": "Commercial Refrigeration Tech", "category": "Refrigeration", "description": "Walk-in freezers, supermarket refrigeration systems, and industrial chiller maintenance."},
        {"skill_name": "Fire Alarm & Life Safety Tech", "category": "Fire & Life Safety", "description": "NFPA compliance, fire alarm control panels, smoke suppression, and emergency sprinkler systems."},
        {"skill_name": "CCTV & Access Control Specialist", "category": "Security & Surveillance", "description": "IP surveillance cameras, biometric access control gates, and intrusion alarm systems."},
        {"skill_name": "Solar PV & Energy Storage Specialist", "category": "Renewable Energy", "description": "Commercial solar array installation, inverter commissioning, and battery energy storage systems (BESS)."},
        {"skill_name": "PLC & Industrial Automation Engineer", "category": "Industrial Automation", "description": "SCADA telemetry, Programmable Logic Controller (PLC) programming, and industrial robot diagnostics."},
        {"skill_name": "Hydraulics & Mechanical Specialist", "category": "Mechanical Systems", "description": "Industrial pumps, hydraulic presses, conveyor drive systems, and mechanical powertrain repair."},
    ]

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

    for user_info in DEFAULT_USERS:
        email = user_info["email"].strip().lower()
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        role = roles_map.get(user_info["role_name"])
        if not role:
            logger.error("seed_user_role_missing", role_name=user_info["role_name"])
            continue

        if existing_user:
            # PRESERVE existing user password hash and account state.
            # Never overwrite passwords on restart.
            if not existing_user.role_id:
                existing_user.role_id = role.id
                existing_user.updated_at = now
            logger.info("seed_user_preserved", email=email)
        else:
            hashed_pwd = get_password_hash(user_info["password"])
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
            logger.info("seed_user_created", email=email)


from app.models.assignment import Assignment
from app.models.job import Job
from app.models.technician import Technician


async def seed_demo_operational_data(session: AsyncSession) -> None:
    """
    DEPRECATED: Strictly excluded from application startup lifecycle.
    Operational entities (technicians, jobs, assignments, demo accounts) must NEVER
    be auto-created on normal application startup.
    This function is retained only for historical reference and must not be called by seed_db().
    """
    now = datetime.now(timezone.utc)
    user_stmt = select(User).where(User.email == "technician@fieldops.ai")
    tech_user = (await session.execute(user_stmt)).scalar_one_or_none()
    if not tech_user:
        return

    # Query a seeded skill for primary_skill_id
    skill_stmt = select(Skill).limit(1)
    skill_obj = (await session.execute(skill_stmt)).scalar_one_or_none()
    first_skill_id = skill_obj.id if skill_obj else None

    # 1. Ensure TECH-001 and TECH-002 exist
    tech1 = (await session.execute(select(Technician).where(Technician.employee_code == "TECH-001"))).scalar_one_or_none()
    if not tech1:
        tech1 = Technician(
            id=uuid.uuid4(),
            user_id=tech_user.id,
            employee_code="TECH-001",
            primary_skill_id=first_skill_id,
            current_latitude=37.7700,
            current_longitude=-122.4200,
            availability_status="AVAILABLE",
            years_experience=5,
            created_at=now,
            updated_at=now,
        )
        session.add(tech1)
        await session.flush()
    elif not tech1.primary_skill_id and first_skill_id:
        tech1.primary_skill_id = first_skill_id

    tech2 = (await session.execute(select(Technician).where(Technician.employee_code == "TECH-002"))).scalar_one_or_none()
    if not tech2:
        tech2_user = (await session.execute(select(User).where(User.email == "tech2@fieldops.ai"))).scalar_one_or_none()
        if not tech2_user:
            tech2_user = User(
                id=uuid.uuid4(),
                role_id=tech_user.role_id,
                email="tech2@fieldops.ai",
                full_name="Marcus Vance",
                password_hash=tech_user.password_hash,
                status=UserStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            session.add(tech2_user)
            await session.flush()

        tech2 = Technician(
            id=uuid.uuid4(),
            user_id=tech2_user.id,
            employee_code="TECH-002",
            primary_skill_id=first_skill_id,
            current_latitude=37.7749,
            current_longitude=-122.4194,
            availability_status="AVAILABLE",
            years_experience=7,
            created_at=now,
            updated_at=now,
        )
        session.add(tech2)
        await session.flush()
    elif not tech2.primary_skill_id and first_skill_id:
        tech2.primary_skill_id = first_skill_id

    # 2. Ensure JOB-10001 and JOB-10002 exist
    job1 = (await session.execute(select(Job).where(Job.job_number == "JOB-10001"))).scalar_one_or_none()
    if not job1:
        job1 = Job(
            id=uuid.uuid4(),
            job_number="JOB-10001",
            customer_name="Bay Area Power Grid",
            customer_phone="+1-555-0101",
            address="100 Mission St, San Francisco, CA",
            latitude=37.7600,
            longitude=-122.4190,
            priority=Priority.HIGH,
            status=JobStatus.ASSIGNED,
            created_at=now,
            updated_at=now,
        )
        session.add(job1)
        await session.flush()

    job2 = (await session.execute(select(Job).where(Job.job_number == "JOB-10002"))).scalar_one_or_none()
    if not job2:
        job2 = Job(
            id=uuid.uuid4(),
            job_number="JOB-10002",
            customer_name="Apex Telecommunications Grid",
            customer_phone="+1-555-0102",
            address="500 Market St, San Francisco, CA",
            latitude=37.7833,
            longitude=-122.4167,
            priority=Priority.CRITICAL,
            status=JobStatus.ASSIGNED,
            created_at=now,
            updated_at=now,
        )
        session.add(job2)
        await session.flush()

    # 3. Ensure assignments exist
    asg1 = (await session.execute(select(Assignment).where(Assignment.job_id == job1.id))).scalar_one_or_none()
    if not asg1:
        asg1 = Assignment(
            id=uuid.uuid4(),
            job_id=job1.id,
            technician_id=tech1.id,
            assignment_status="ASSIGNED",
            assigned_at=now,
        )
        session.add(asg1)

    asg2 = (await session.execute(select(Assignment).where(Assignment.job_id == job2.id))).scalar_one_or_none()
    if not asg2:
        asg2 = Assignment(
            id=uuid.uuid4(),
            job_id=job2.id,
            technician_id=tech2.id,
            assignment_status="ASSIGNED",
            assigned_at=now,
        )
        session.add(asg2)


import app.models  # Ensure all ORM models are registered
from app.database.base import Base
from app.database.session import AsyncSessionLocal, engine


async def seed_db() -> None:
    """Master idempotent database seed runner.
    Initializes only system-level baseline configuration (tables, roles, baseline accounts, skills taxonomy).
    Operational records (technicians, jobs, assignments) must NEVER be auto-created on startup.
    """
    logger.info("seed_db_start")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        try:
            roles_map = await seed_roles(session)
            await seed_users(session, roles_map)
            # ZERO operational records created automatically.
            await session.commit()
            logger.info("seed_db_success")
        except Exception as err:
            await session.rollback()
            logger.exception("seed_db_failed", error=str(err))
            raise


if __name__ == "__main__":
    asyncio.run(seed_db())
