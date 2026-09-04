"""
Technician Service Layer managing business workflows, validations, and transaction orchestration.
"""

import math
from typing import Optional
import uuid

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import get_password_hash
from app.models.enums import UserRole, UserStatus
from app.models.technician import Technician
from app.models.user import User
from app.repositories.technician_repository import TechnicianRepository
from app.schemas.technician import (
    PaginatedTechnicianResponse,
    SkillSummary,
    TechnicianCreate,
    TechnicianResponse,
    TechnicianSkillsResponse,
    TechnicianStatusPatch,
    TechnicianUpdate,
)


class TechnicianService:
    """Business service layer for technician management operations."""


    def __init__(self, repository: TechnicianRepository | None = None) -> None:
        self.repo = repository or TechnicianRepository()

    async def list_technicians(
        self,
        search: Optional[str] = None,
        availability_status: Optional[str] = None,
        skill_id: Optional[uuid.UUID] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> PaginatedTechnicianResponse:
        """Query paginated technicians with filtering and sorting."""
        items, total = await self.repo.list_technicians(
            search=search,
            availability_status=availability_status,
            skill_id=skill_id,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return PaginatedTechnicianResponse(
            items=[TechnicianResponse.model_validate(tech) for tech in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_technician_by_id(self, tech_id: uuid.UUID) -> TechnicianResponse:
        """Fetch technician profile by UUID."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))
        return TechnicianResponse.model_validate(tech)

    async def create_technician(
        self,
        payload: TechnicianCreate,
        actor_id: Optional[uuid.UUID] = None,
    ) -> TechnicianResponse:
        """Create new technician profile and user account."""
        # 1. Validate employee code uniqueness
        existing_code = await self.repo.get_by_employee_code(payload.employee_code)
        if existing_code:
            raise ConflictError(f"Employee code '{payload.employee_code}' already exists.")

        # 2. Validate email uniqueness
        existing_email = await self.repo.get_user_by_email(payload.email)
        if existing_email:
            raise ConflictError(f"User email '{payload.email}' already exists.")

        # 3. Validate required primary skill
        skill = await self.repo.get_skill_by_id(payload.primary_skill_id)
        if not skill:
            raise ValidationError(f"Primary skill with ID '{payload.primary_skill_id}' does not exist.")

        # 4. Fetch Technician security role
        role = await self.repo.get_role_by_name(UserRole.TECHNICIAN.value)
        if not role:
            raise ValidationError("Technician security role is missing in system configuration.")

        # 5. Build entities
        user_obj = User(
            id=uuid.uuid4(),
            role_id=role.id,
            email=payload.email.strip().lower(),
            full_name=payload.full_name.strip(),
            password_hash=get_password_hash(payload.password),
            phone=payload.phone.strip() if payload.phone else None,
            status=UserStatus.ACTIVE,
        )

        tech_obj = Technician(
            id=uuid.uuid4(),
            employee_code=payload.employee_code.strip().upper(),
            primary_skill_id=payload.primary_skill_id,
            years_experience=payload.years_experience,
            availability_status=payload.availability_status.strip().upper(),
            current_latitude=payload.current_latitude,
            current_longitude=payload.current_longitude,
        )

        created_tech = await self.repo.create_technician_with_user(user_obj, tech_obj, actor_id=actor_id)
        return TechnicianResponse.model_validate(created_tech)

    async def update_technician(
        self,
        tech_id: uuid.UUID,
        payload: TechnicianUpdate,
        actor_id: Optional[uuid.UUID] = None,
    ) -> TechnicianResponse:
        """Update existing technician profile details."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))

        user_obj = tech.user
        if not user_obj:
            raise NotFoundError("User", str(tech.user_id))

        old_summary = f"Name: {user_obj.full_name}, Email: {user_obj.email}, Phone: {user_obj.phone}, Exp: {tech.years_experience}, Status: {tech.availability_status}"

        if payload.email and payload.email.strip().lower() != user_obj.email.lower():
            existing_email = await self.repo.get_user_by_email(payload.email)
            if existing_email:
                raise ConflictError(f"User email '{payload.email}' already exists.")
            user_obj.email = payload.email.strip().lower()

        if payload.full_name is not None:
            user_obj.full_name = payload.full_name.strip()

        if payload.phone is not None:
            user_obj.phone = payload.phone.strip() if payload.phone else None

        if payload.primary_skill_id is not None:
            skill = await self.repo.get_skill_by_id(payload.primary_skill_id)
            if not skill:
                raise ValidationError(f"Skill with ID '{payload.primary_skill_id}' does not exist.")
            tech.primary_skill_id = payload.primary_skill_id

        if payload.years_experience is not None:
            tech.years_experience = payload.years_experience

        if payload.availability_status is not None:
            tech.availability_status = payload.availability_status.strip().upper()

        if payload.current_latitude is not None:
            tech.current_latitude = payload.current_latitude

        if payload.current_longitude is not None:
            tech.current_longitude = payload.current_longitude

        new_summary = f"Name: {user_obj.full_name}, Email: {user_obj.email}, Phone: {user_obj.phone}, Exp: {tech.years_experience}, Status: {tech.availability_status}"

        updated_tech = await self.repo.update_technician_with_user(
            tech, user_obj, old_summary, new_summary, actor_id=actor_id
        )
        return TechnicianResponse.model_validate(updated_tech)

    async def patch_status(
        self,
        tech_id: uuid.UUID,
        payload: TechnicianStatusPatch,
        actor_id: Optional[uuid.UUID] = None,
    ) -> TechnicianResponse:
        """Update technician availability status."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))

        old_status = tech.availability_status
        new_status = payload.availability_status.strip().upper()

        updated_tech = await self.repo.update_status(tech, old_status, new_status, actor_id=actor_id)
        return TechnicianResponse.model_validate(updated_tech)

    async def delete_technician(
        self,
        tech_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Deactivate technician profile."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))

        await self.repo.delete_technician(tech_id, actor_id=actor_id)


    async def get_technician_skills(self, tech_id: uuid.UUID) -> TechnicianSkillsResponse:
        """Fetch technician primary and secondary skill associations."""
        tech = await self.repo.get_by_id(tech_id)
        if not tech:
            raise NotFoundError("Technician", str(tech_id))

        primary = SkillSummary.model_validate(tech.primary_skill) if tech.primary_skill else None
        skills = [primary] if primary else []

        return TechnicianSkillsResponse(
            technician_id=tech.id,
            employee_code=tech.employee_code,
            primary_skill=primary,
            skills=skills,
        )

