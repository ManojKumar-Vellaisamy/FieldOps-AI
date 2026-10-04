"""
Pristine Enterprise Data Seeder & Cleaner.
Transforms development database into a clean, 100% authentic enterprise Field Service environment.

Actions:
1. Removes dummy test jobs (ETA Test..., Module 21..., Traffic Test..., dummy cricketer names).
2. Cleans & elevates active test job JOB-10066 to authentic enterprise work order:
   Chettinad Heritage Mansion & Cultural Centre, Athangudi.
3. Seeds realistic Tamil Nadu regional enterprise service orders across NEW, ASSIGNED, IN_PROGRESS, COMPLETED.
4. Upgrades technicians with professional enterprise profiles, skills, and regional hubs.
5. Populates authentic audit logs explaining dispatch events and plan reasoning.
"""

import asyncio
from datetime import datetime, timezone, timedelta
import uuid

from sqlalchemy import delete, select, func
from app.database.session import AsyncSessionLocal
from app.models.job import Job
from app.models.technician import Technician
from app.models.user import User
from app.models.role import Role
from app.models.skill import Skill
from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.eta_override import ETAOverride
from app.models.enums import AssignmentType, JobStatus, Priority, UserRole, UserStatus
from app.core.security import get_password_hash


async def main():
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        print("=" * 70)
        print("FIELDOPS AI — CLEAN ENTERPRISE DATA SEEDER")
        print("=" * 70)

        # 1. Fetch Skills Map
        skill_res = await session.execute(select(Skill))
        skills = {s.skill_name: s for s in skill_res.scalars().all()}
        print(f"[Skills Loaded] {len(skills)} enterprise certifications found.")

        # Ensure all standard enterprise skills exist
        req_skills = [
            ("HVAC Master", "HVAC", "Master certification in commercial/industrial chillers, VRF ventilation and cooling."),
            ("High Voltage Specialist", "Electrical", "Industrial substation transformer maintenance, HT breakers and grid safety."),
            ("Fiber Optics Specialist", "Telecommunications", "FTTH/Backbone cable splicing, OTDR laser testing and optical network rollout."),
            ("Precision Sensor Calibration", "Calibration", "Industrial IoT transducers, pressure sensors, and cleanroom air monitoring."),
            ("AC Repair", "Electrical", "Commercial air conditioning, compressor overhaul, and refrigerant recovery."),
            ("Enterprise Router Admin", "Network", "Cisco routing, industrial firewall, and SCADA telemetry diagnostics."),
        ]
        for name, cat, desc in req_skills:
            if name not in skills:
                sk = Skill(
                    id=uuid.uuid4(),
                    skill_name=name,
                    category=cat,
                    description=desc,
                    status="ACTIVE",
                    created_at=now,
                    updated_at=now,
                )
                session.add(sk)
                skills[name] = sk
        await session.flush()

        # 2. Fetch or Ensure Default Roles
        role_res = await session.execute(select(Role))
        roles = {r.name: r for r in role_res.scalars().all()}

        # 3. Clean up Test/Dummy Jobs (ETA Test..., Module 21..., Traffic Test..., dummy cricketer names)
        dummy_job_patterns = [
            "ETA Test", "Module 21", "Module 23", "Traffic Test", "Scenario 1", "Scenario 5",
            "Lifecycle Customer", "Virat Kohli", "Rocky", "Gill", "Pujara", "King", "Seq 1", "Seq 2",
            "Example", "Haridas", "Kohli", "Logesh", "Giridharan"
        ]

        all_jobs_res = await session.execute(select(Job))
        all_jobs = all_jobs_res.scalars().all()
        
        deleted_count = 0
        preserved_job_10066 = None

        for j in all_jobs:
            if j.job_number == "JOB-10066":
                preserved_job_10066 = j
                continue

            # Check if job matches any test dummy pattern
            is_dummy = False
            for pat in dummy_job_patterns:
                if pat.lower() in (j.customer_name or "").lower() or pat.lower() in (j.address or "").lower():
                    is_dummy = True
                    break

            if is_dummy:
                # Remove assignments & overrides for this job first
                await session.execute(delete(Assignment).where(Assignment.job_id == j.id))
                await session.execute(delete(ETAOverride).where(ETAOverride.job_id == j.id))
                await session.execute(delete(AuditLog).where(AuditLog.entity_id == str(j.id)))
                await session.delete(j)
                deleted_count += 1

        await session.flush()
        print(f"[Cleanup] Purged {deleted_count} automated test & dummy records from PostgreSQL.")

        # 4. Elevate JOB-10066 to Authentic Enterprise Customer
        if preserved_job_10066:
            preserved_job_10066.customer_name = "Chettinad Heritage Mansion & Research Centre"
            preserved_job_10066.customer_phone = "+91 94431 82345"
            preserved_job_10066.address = "MLM Heritage House, 5P4H+Q52, Athangudi, Karaikkudi, Tamil Nadu 630101"
            preserved_job_10066.latitude = 10.1571
            preserved_job_10066.longitude = 78.7278
            preserved_job_10066.description = "Emergency Rooftop Solar Inverter DC Isolator Fault & VRF Chiller Loop Inspection."
            preserved_job_10066.priority = Priority.HIGH
            preserved_job_10066.status = JobStatus.ASSIGNED
            preserved_job_10066.required_skill_id = skills["High Voltage Specialist"].id
            preserved_job_10066.scheduled_time = now + timedelta(hours=1)
            print("[Job 10066 Updated] Elevated active job to Chettinad Heritage Mansion (Athangudi).")

        # 5. Clean & Standardize Enterprise Technicians
        # We ensure 4 enterprise field specialists located in Karaikudi, Coimbatore, Madurai, and Trichy
        tech_data = [
            {
                "email": "row@fieldops.ai",
                "full_name": "Russow M.",
                "emp_code": "TECH-KKDI-01",
                "phone": "+91 98421 11001",
                "lat": 10.0731,
                "lon": 78.7802,
                "city": "Karaikudi Hub",
                "skill": "High Voltage Specialist",
                "status": "ON_JOB",
                "exp": 6,
            },
            {
                "email": "rohit@fieldops.ai",
                "full_name": "Rohit Sharma",
                "emp_code": "TECH-CBE-02",
                "phone": "+91 98421 22002",
                "lat": 11.0168,
                "lon": 76.9558,
                "city": "Coimbatore Metro",
                "skill": "HVAC Master",
                "status": "AVAILABLE",
                "exp": 8,
            },
            {
                "email": "manoj.tech@fieldops.ai",
                "full_name": "Manoj Kumar V.",
                "emp_code": "TECH-MDU-03",
                "phone": "+91 98421 33003",
                "lat": 9.9252,
                "lon": 78.1198,
                "city": "Madurai Hub",
                "skill": "Fiber Optics Specialist",
                "status": "AVAILABLE",
                "exp": 5,
            },
            {
                "email": "karthik.tech@fieldops.ai",
                "full_name": "Karthik Sundaram",
                "emp_code": "TECH-TRY-04",
                "phone": "+91 98421 44004",
                "lat": 10.8285,
                "lon": 78.6865,
                "city": "Tiruchirappalli Hub",
                "skill": "Precision Sensor Calibration",
                "status": "AVAILABLE",
                "exp": 7,
            },
        ]

        tech_objects = {}
        tech_role = roles[UserRole.TECHNICIAN.value]
        pwd_hash = get_password_hash("Tech@123")

        # Cleanup existing odd technician users
        for t_info in tech_data:
            u_stmt = select(User).where(User.email == t_info["email"])
            u = (await session.execute(u_stmt)).scalar_one_or_none()
            if not u:
                u = User(
                    id=uuid.uuid4(),
                    role_id=tech_role.id,
                    email=t_info["email"],
                    full_name=t_info["full_name"],
                    phone=t_info["phone"],
                    password_hash=pwd_hash,
                    status=UserStatus.ACTIVE,
                    created_at=now,
                    updated_at=now,
                )
                session.add(u)
                await session.flush()
            else:
                u.full_name = t_info["full_name"]
                u.phone = t_info["phone"]
                u.status = UserStatus.ACTIVE

            # Technician profile
            t_stmt = select(Technician).where(Technician.user_id == u.id)
            tech = (await session.execute(t_stmt)).scalar_one_or_none()
            if not tech:
                tech = Technician(
                    id=uuid.uuid4(),
                    user_id=u.id,
                    employee_code=t_info["emp_code"],
                    primary_skill_id=skills[t_info["skill"]].id,
                    current_latitude=t_info["lat"],
                    current_longitude=t_info["lon"],
                    availability_status=t_info["status"],
                    years_experience=t_info["exp"],
                    created_at=now,
                    updated_at=now,
                )
                session.add(tech)
                await session.flush()
            else:
                tech.employee_code = t_info["emp_code"]
                tech.primary_skill_id = skills[t_info["skill"]].id
                tech.current_latitude = t_info["lat"]
                tech.current_longitude = t_info["lon"]
                tech.availability_status = t_info["status"]
                tech.years_experience = t_info["exp"]

            tech_objects[t_info["email"]] = tech
            print(f"[Technician Verified] {t_info['full_name']} ({t_info['city']}) -> {t_info['skill']}")

        await session.flush()

        # Connect JOB-10066 assignment to Russow
        if preserved_job_10066:
            russow = tech_objects["row@fieldops.ai"]
            # Check existing assignment
            asgn_stmt = select(Assignment).where(Assignment.job_id == preserved_job_10066.id)
            existing_asgn = (await session.execute(asgn_stmt)).scalar_one_or_none()
            if not existing_asgn:
                asgn = Assignment(
                    id=uuid.uuid4(),
                    job_id=preserved_job_10066.id,
                    technician_id=russow.id,
                    assigned_at=now - timedelta(minutes=15),
                    assignment_status="ASSIGNED",
                    assignment_type=AssignmentType.MANUAL,
                )
                session.add(asgn)
            else:
                existing_asgn.technician_id = russow.id
                existing_asgn.assignment_status = "ASSIGNED"

        # 6. Seed Additional Pristine Enterprise Field Orders
        # Realistic service requests across Karaikudi, Devakottai, Madurai, Coimbatore, and Trichy
        enterprise_jobs = [
            {
                "job_number": "JOB-10070",
                "customer_name": "Alagappa University Central Instrumentation Facility",
                "customer_phone": "+91 94432 76543",
                "address": "College Road, Alagappa Puram, Karaikudi, Tamil Nadu 630003",
                "latitude": 10.0768,
                "longitude": 78.7845,
                "priority": Priority.HIGH,
                "status": JobStatus.NEW,
                "skill": "Precision Sensor Calibration",
                "description": "Cleanroom humidity transducer drift calibration & clean air differential pressure validation.",
                "scheduled": now + timedelta(hours=2),
            },
            {
                "job_number": "JOB-10071",
                "customer_name": "TVS Dynamic Industrial Auto Components",
                "customer_phone": "+91 94433 89012",
                "address": "SIDCO Industrial Estate, Devakottai Road, Karaikudi 630005",
                "latitude": 10.0450,
                "longitude": 78.8020,
                "priority": Priority.MEDIUM,
                "status": JobStatus.NEW,
                "skill": "HVAC Master",
                "description": "Central plant chiller screw compressor oil pressure alarm and refrigerant leak containment.",
                "scheduled": now + timedelta(hours=3),
            },
            {
                "job_number": "JOB-10072",
                "customer_name": "Apollo Speciality Hospitals Madurai",
                "customer_phone": "+91 94434 12345",
                "address": "Lake View Road, K.K. Nagar, Madurai, Tamil Nadu 625020",
                "latitude": 9.9325,
                "longitude": 78.1482,
                "priority": Priority.CRITICAL,
                "status": JobStatus.ASSIGNED,
                "skill": "HVAC Master",
                "tech_email": "manoj.tech@fieldops.ai",
                "description": "Critical care ICU air exchange HEPA filtration pressure drop & ventilator standby motor inspection.",
                "scheduled": now + timedelta(minutes=45),
            },
            {
                "job_number": "JOB-10073",
                "customer_name": "Bosch Engineering & Technology Center",
                "customer_phone": "+91 94435 67890",
                "address": "CHIL-SEZ IT Park, Saravanampatti, Coimbatore, Tamil Nadu 641035",
                "latitude": 11.0825,
                "longitude": 76.9958,
                "priority": Priority.HIGH,
                "status": JobStatus.WORKING,
                "skill": "HVAC Master",
                "tech_email": "rohit@fieldops.ai",
                "description": "Server room precision air conditioner cooling loop maintenance and inverter PCB replacement.",
                "scheduled": now - timedelta(hours=1),
            },
            {
                "job_number": "JOB-10074",
                "customer_name": "Sri Meenakshi Cotton Mills & Logistics Hub",
                "customer_phone": "+91 94436 23456",
                "address": "Trichy Highway Bypass, Madurai, Tamil Nadu 625014",
                "latitude": 9.9512,
                "longitude": 78.1585,
                "priority": Priority.MEDIUM,
                "status": JobStatus.COMPLETED,
                "skill": "High Voltage Specialist",
                "tech_email": "manoj.tech@fieldops.ai",
                "description": "HT Transformer 11kV dielectric oil filtration, thermal imaging scan, and lightning arrestor earth test.",
                "scheduled": now - timedelta(days=1),
            },
            {
                "job_number": "JOB-10075",
                "customer_name": "BSNL Regional Optical Fiber Exchange",
                "customer_phone": "+91 94437 34567",
                "address": "Subramaniapuram 5th Street, Karaikudi, Tamil Nadu 630002",
                "latitude": 10.0710,
                "longitude": 78.7750,
                "priority": Priority.HIGH,
                "status": JobStatus.COMPLETED,
                "skill": "Fiber Optics Specialist",
                "tech_email": "row@fieldops.ai",
                "description": "Core 96-fiber backbone trunk cable restoration and bidirectional optical loss certification.",
                "scheduled": now - timedelta(days=2),
            },
            {
                "job_number": "JOB-10076",
                "customer_name": "Kovai Medical Center & Hospital (KMCH)",
                "customer_phone": "+91 94438 45678",
                "address": "Avinashi Road, Peelamedu, Coimbatore, Tamil Nadu 641014",
                "latitude": 11.0312,
                "longitude": 77.0175,
                "priority": Priority.HIGH,
                "status": JobStatus.COMPLETED,
                "skill": "HVAC Master",
                "tech_email": "rohit@fieldops.ai",
                "description": "Diagnostic imaging center chiller pump seal replacement and automated balancing valve servicing.",
                "scheduled": now - timedelta(days=3),
            },
            {
                "job_number": "JOB-10077",
                "customer_name": "BHEL Township Electrical Substation",
                "customer_phone": "+91 94439 56789",
                "address": "Thiruverumbur, Tiruchirappalli, Tamil Nadu 620014",
                "latitude": 10.7725,
                "longitude": 78.7850,
                "priority": Priority.HIGH,
                "status": JobStatus.NEW,
                "skill": "High Voltage Specialist",
                "description": "Substation vacuum circuit breaker trip timing test and sulfur hexafluoride (SF6) gas pressure check.",
                "scheduled": now + timedelta(hours=4),
            },
        ]

        # Insert or update enterprise jobs
        dispatcher_stmt = select(User).where(User.email == "dispatcher@fieldops.ai")
        dispatcher_user = (await session.execute(dispatcher_stmt)).scalar_one_or_none()
        dispatcher_id = dispatcher_user.id if dispatcher_user else None

        for ej in enterprise_jobs:
            stmt = select(Job).where(Job.job_number == ej["job_number"])
            existing_job = (await session.execute(stmt)).scalar_one_or_none()
            if not existing_job:
                new_j = Job(
                    id=uuid.uuid4(),
                    job_number=ej["job_number"],
                    customer_name=ej["customer_name"],
                    customer_phone=ej["customer_phone"],
                    address=ej["address"],
                    latitude=ej["latitude"],
                    longitude=ej["longitude"],
                    priority=ej["priority"],
                    status=ej["status"],
                    required_skill_id=skills[ej["skill"]].id,
                    description=ej["description"],
                    scheduled_time=ej["scheduled"],
                    created_by=dispatcher_id,
                    created_at=now - timedelta(days=1),
                    updated_at=now,
                )
                session.add(new_j)
                await session.flush()
                print(f"[New Enterprise Job] Created {ej['job_number']}: {ej['customer_name']}")

                # If job has assigned technician
                if ej.get("tech_email") and ej["status"] in (JobStatus.ASSIGNED, JobStatus.WORKING, JobStatus.COMPLETED):
                    t = tech_objects.get(ej["tech_email"])
                    if t:
                        asgn = Assignment(
                            id=uuid.uuid4(),
                            job_id=new_j.id,
                            technician_id=t.id,
                            assigned_at=ej["scheduled"] - timedelta(minutes=30),
                            assignment_status=ej["status"].value,
                            assignment_type=AssignmentType.SYSTEM,
                        )
                        session.add(asgn)

        # 7. Seed Clean, Authentic Audit Logs
        # Add rich, realistic operational audit records
        audit_events = [
            ("JOB_ASSIGNED", "Job", "Assigned technician Russow M. to Chettinad Heritage Mansion. Reason: Proximity (15.2 km) and High Voltage Specialist match."),
            ("ETA_CALCULATED", "ETA", "Calculated baseline transit (15m) + weather adjustment (+5m) + traffic delay (+6m) = 26 min ETA."),
            ("STATUS_CHANGED", "Job", "Status updated to ASSIGNED for JOB-10066 by Dispatcher Priya Nair."),
            ("DISPATCH_OPTIMIZED", "Assignment", "Smart assignment recommended Russow M. (Composite score: 94.2) for Athangudi service order."),
            ("JOB_CREATED", "Job", "Created high-priority work order JOB-10070 for Alagappa University Nanotechnology Lab."),
            ("JOB_COMPLETED", "Job", "JOB-10075 completed by Russow M. Customer signature captured. SLA met in 42 minutes."),
            ("JOB_COMPLETED", "Job", "JOB-10074 completed by Manoj Kumar V. 11kV Substation maintenance certified."),
        ]

        for action, entity, reason in audit_events:
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=dispatcher_id,
                action=action,
                entity=entity,
                reason=reason,
                created_at=now - timedelta(minutes=int(uuid.uuid4().int % 180)),
            )
            session.add(audit)

        await session.commit()
        print("\n" + "=" * 70)
        print("DATABASE SUCCESSFULLY PURGED & ELEVATED TO 100% PRISTINE ENTERPRISE STATE!")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
