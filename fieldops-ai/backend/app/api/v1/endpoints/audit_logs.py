"""
Audit Log REST API endpoints for tracking operational plan changes, assignments, status transitions, and overrides.
"""

import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_roles
from app.database.session import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.schemas.audit import AuditLogResponse, PaginatedAuditLogResponse
from app.schemas.auth import UserResponse

router = APIRouter(tags=["Audit Trail"])


@router.get(
    "/audit-logs",
    response_model=PaginatedAuditLogResponse,
    status_code=status.HTTP_200_OK,
    summary="List and filter operational audit logs",
)
async def list_audit_logs(
    search: Optional[str] = Query(None, description="Search across action, entity, reason, or details"),
    action: Optional[str] = Query(None, description="Filter by audit action (e.g. TECHNICIAN_ASSIGNED, ETA_OVERRIDE_CREATED)"),
    entity: Optional[str] = Query(None, description="Filter by audited entity (e.g. Job, Assignment, Technician)"),
    entity_id: Optional[str] = Query(None, description="Filter by entity UUID / ID"),
    user_id: Optional[str] = Query(None, description="Filter by actor User UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: UserResponse = Depends(require_roles(UserRole.DISPATCHER, UserRole.ADMINISTRATOR)),
) -> PaginatedAuditLogResponse:
    """List system audit logs with filtering and pagination. Restricted to Dispatcher and Administrator roles."""
    async with AsyncSessionLocal() as db:
        query = select(AuditLog).options(selectinload(AuditLog.user))

        filters = []
        if action:
            filters.append(AuditLog.action == action)
        if entity:
            filters.append(AuditLog.entity == entity)
        if entity_id:
            filters.append(AuditLog.entity_id == entity_id)
        if user_id:
            try:
                filters.append(AuditLog.user_id == UUID(user_id))
            except ValueError:
                pass
        if search:
            search_pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    AuditLog.action.ilike(search_pattern),
                    AuditLog.entity.ilike(search_pattern),
                    AuditLog.entity_id.ilike(search_pattern),
                    AuditLog.reason.ilike(search_pattern),
                    AuditLog.old_value.ilike(search_pattern),
                    AuditLog.new_value.ilike(search_pattern),
                )
            )

        if filters:
            query = query.where(*filters)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        # Pagination & Ordering
        offset = (page - 1) * page_size
        query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)

        result = await db.execute(query)
        audit_logs = result.scalars().all()

        items = []
        for log in audit_logs:
            user_name = log.user.full_name if log.user else "System / Automated"
            items.append(
                AuditLogResponse(
                    id=log.id,
                    user_id=log.user_id,
                    user_full_name=user_name,
                    action=log.action,
                    entity=log.entity,
                    entity_id=log.entity_id,
                    reason=log.reason,
                    old_value=log.old_value,
                    new_value=log.new_value,
                    created_at=log.created_at,
                )
            )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return PaginatedAuditLogResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


@router.get(
    "/jobs/{job_id}/audit-history",
    response_model=list[AuditLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Get complete audit history sequence for a specific service job",
)
async def get_job_audit_history(
    job_id: UUID,
    current_user: UserResponse = Depends(require_roles(UserRole.DISPATCHER, UserRole.ADMINISTRATOR)),
) -> list[AuditLogResponse]:
    """Retrieve full chronological audit trail of plan changes, status transitions, overrides, and assignments for a job."""
    async with AsyncSessionLocal() as db:
        job_id_str = str(job_id)
        query = (
            select(AuditLog)
            .options(selectinload(AuditLog.user))
            .where(
                or_(
                    AuditLog.entity_id == job_id_str,
                    AuditLog.old_value.ilike(f"%{job_id_str}%"),
                    AuditLog.new_value.ilike(f"%{job_id_str}%"),
                )
            )
            .order_by(AuditLog.created_at.asc())
        )

        result = await db.execute(query)
        logs = result.scalars().all()

        return [
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                user_full_name=log.user.full_name if log.user else "System",
                action=log.action,
                entity=log.entity,
                entity_id=log.entity_id,
                reason=log.reason,
                old_value=log.old_value,
                new_value=log.new_value,
                created_at=log.created_at,
            )
            for log in logs
        ]
