"""
Skill Service Layer managing business workflows, validations, and transaction orchestration.
"""

import math
from typing import Optional
import uuid

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.skill import Skill
from app.repositories.skill_repository import SkillRepository
from app.schemas.skill import (
    PaginatedSkillResponse,
    SkillCreate,
    SkillResponse,
    SkillStatusPatch,
    SkillTechnicianSummary,
    SkillUpdate,
    SkillWithTechniciansResponse,
)


class SkillService:
    """Business service layer for skill management operations."""

    def __init__(self, repository: SkillRepository | None = None) -> None:
        self.repo = repository or SkillRepository()

    async def list_skills(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> PaginatedSkillResponse:
        """Query paginated skills with filtering and technician counts."""
        items_with_count, total, active_count, inactive_count = await self.repo.list_skills(
            search=search,
            category=category,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        skill_responses = []
        for skill_obj, tech_count in items_with_count:
            resp = SkillResponse.model_validate(skill_obj)
            resp.technician_count = tech_count
            skill_responses.append(resp)

        return PaginatedSkillResponse(
            items=skill_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_active=active_count,
            total_inactive=inactive_count,
        )

    async def get_skill_by_id(self, skill_id: uuid.UUID) -> SkillResponse:
        """Fetch single skill details by UUID."""
        skill = await self.repo.get_by_id(skill_id)
        if not skill:
            raise NotFoundError("Skill", str(skill_id))

        tech_count = await self.repo.get_technician_count_for_skill(skill_id)
        resp = SkillResponse.model_validate(skill)
        resp.technician_count = tech_count
        return resp

    async def create_skill(
        self,
        payload: SkillCreate,
        actor_id: Optional[uuid.UUID] = None,
    ) -> SkillResponse:
        """Create new Skill taxonomy record."""
        # 1. Validate non-empty fields
        if not payload.skill_name or not payload.skill_name.strip():
            raise ValidationError("Skill name cannot be empty.")

        if not payload.category or not payload.category.strip():
            raise ValidationError("Category cannot be empty.")

        # 2. Case-insensitive uniqueness check
        existing = await self.repo.get_by_name(payload.skill_name)
        if existing:
            raise ConflictError(f"Skill name '{payload.skill_name.strip()}' already exists.")

        # 3. Create entity
        skill_obj = Skill(
            id=uuid.uuid4(),
            skill_name=payload.skill_name.strip(),
            category=payload.category.strip(),
            description=payload.description.strip() if payload.description else None,
            status=payload.status.strip().upper(),
        )

        created = await self.repo.create_skill(skill_obj, actor_id=actor_id)
        resp = SkillResponse.model_validate(created)
        resp.technician_count = 0
        return resp

    async def update_skill(
        self,
        skill_id: uuid.UUID,
        payload: SkillUpdate,
        actor_id: Optional[uuid.UUID] = None,
    ) -> SkillResponse:
        """Update existing Skill entity details."""
        skill = await self.repo.get_by_id(skill_id)
        if not skill:
            raise NotFoundError("Skill", str(skill_id))

        old_summary = f"Name: {skill.skill_name}, Category: {skill.category}, Status: {skill.status}"

        if payload.skill_name is not None and payload.skill_name.strip().lower() != skill.skill_name.lower():
            existing = await self.repo.get_by_name(payload.skill_name)
            if existing and existing.id != skill_id:
                raise ConflictError(f"Skill name '{payload.skill_name.strip()}' already exists.")
            skill.skill_name = payload.skill_name.strip()

        if payload.category is not None:
            if not payload.category.strip():
                raise ValidationError("Category cannot be empty.")
            skill.category = payload.category.strip()

        if payload.description is not None:
            skill.description = payload.description.strip() if payload.description else None

        if payload.status is not None:
            skill.status = payload.status.strip().upper()

        new_summary = f"Name: {skill.skill_name}, Category: {skill.category}, Status: {skill.status}"

        updated = await self.repo.update_skill(skill, old_summary, new_summary, actor_id=actor_id)
        tech_count = await self.repo.get_technician_count_for_skill(skill_id)
        resp = SkillResponse.model_validate(updated)
        resp.technician_count = tech_count
        return resp

    async def patch_status(
        self,
        skill_id: uuid.UUID,
        payload: SkillStatusPatch,
        actor_id: Optional[uuid.UUID] = None,
    ) -> SkillResponse:
        """Toggle or update skill active/inactive status (Soft Deactivation)."""
        skill = await self.repo.get_by_id(skill_id)
        if not skill:
            raise NotFoundError("Skill", str(skill_id))

        old_status = skill.status
        new_status = payload.status.strip().upper()

        updated = await self.repo.update_status(skill, old_status, new_status, actor_id=actor_id)
        tech_count = await self.repo.get_technician_count_for_skill(skill_id)
        resp = SkillResponse.model_validate(updated)
        resp.technician_count = tech_count
        return resp

    async def get_skill_with_technicians(self, skill_id: uuid.UUID) -> SkillWithTechniciansResponse:
        """Fetch skill details along with list of associated qualified technicians."""
        skill = await self.repo.get_by_id(skill_id)
        if not skill:
            raise NotFoundError("Skill", str(skill_id))

        techs = await self.repo.get_technicians_by_skill(skill_id)
        tech_summaries = [
            SkillTechnicianSummary(
                id=t.id,
                employee_code=t.employee_code,
                full_name=t.user.full_name if t.user else "Unknown",
                email=t.user.email if t.user else "",
                years_experience=t.years_experience,
                availability_status=t.availability_status,
            )
            for t in techs
        ]

        resp_skill = SkillResponse.model_validate(skill)
        resp_skill.technician_count = len(tech_summaries)

        return SkillWithTechniciansResponse(
            skill=resp_skill,
            technicians=tech_summaries,
            technician_count=len(tech_summaries),
        )

    async def get_my_skills(self, user_id: uuid.UUID) -> list[SkillResponse]:
        """Fetch skills associated with current authenticated technician."""
        skills = await self.repo.get_skills_for_technician_user(user_id)
        results = []
        for s in skills:
            tech_count = await self.repo.get_technician_count_for_skill(s.id)
            sr = SkillResponse.model_validate(s)
            sr.technician_count = tech_count
            results.append(sr)
        return results
