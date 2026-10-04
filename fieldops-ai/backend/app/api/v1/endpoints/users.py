"""
User Management API v1 Endpoints.
Provides administration oversight of platform user accounts with strict Single Administrator protection.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.database.session import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.enums import UserRole, UserStatus
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import UserResponse

logger = get_logger(__name__)

router = APIRouter(tags=["User Management"])


class CreateUserPayload(BaseModel):
    """Payload for administrative user account creation."""

    email: EmailStr = Field(..., description="Corporate email address")
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name of user")
    phone: Optional[str] = Field(None, max_length=50, description="Contact phone number")
    role: str = Field(..., description="Role to assign: 'Dispatcher' or 'Technician'")
    password: str = Field(..., min_length=8, description="Initial temporary password")


class UserAccountResponse(BaseModel):
    """User account response item."""

    id: UUID
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: str
    status: str
    must_change_password: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserStatusPayload(BaseModel):
    """Payload to update user account status."""

    status: Optional[UserStatus] = None


@router.get(
    "",
    response_model=list[UserAccountResponse],
    status_code=status.HTTP_200_OK,
    summary="List all platform user accounts",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))],
)
async def list_users(
    search: Optional[str] = Query(None, description="Search name or email"),
    role_filter: Optional[str] = Query(None, description="Filter by role name"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    current_user: UserResponse = Depends(get_current_user),
) -> list[UserAccountResponse]:
    """Retrieve all user accounts from the database. Restricted to Administrator."""
    async with AsyncSessionLocal() as session:
        stmt = select(User).options(selectinload(User.role_rel)).order_by(User.created_at.desc())
        result = await session.execute(stmt)
        users = result.scalars().all()

        output: list[UserAccountResponse] = []
        for u in users:
            role_name = u.role
            status_val = u.status.value if hasattr(u.status, "value") else str(u.status)

            if search:
                s = search.strip().lower()
                if s not in u.full_name.lower() and s not in u.email.lower():
                    continue

            if role_filter and role_filter != "ALL":
                if role_name.lower() != role_filter.strip().lower():
                    continue

            if status_filter and status_filter != "ALL":
                if status_val.upper() != status_filter.strip().upper():
                    continue

            output.append(
                UserAccountResponse(
                    id=u.id,
                    email=u.email,
                    full_name=u.full_name,
                    phone=u.phone,
                    role=role_name,
                    status=status_val,
                    must_change_password=u.must_change_password,
                    created_at=u.created_at,
                    last_login=u.last_login,
                )
            )

        return output


@router.post(
    "",
    response_model=UserAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new platform user account",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))],
)
async def create_user(
    payload: CreateUserPayload,
    current_user: UserResponse = Depends(get_current_user),
) -> UserAccountResponse:
    """
    Create a new user account (Dispatcher or Technician).
    Strictly prohibits creation of additional Administrator accounts.
    """
    normalized_role = payload.role.strip()

    # 1. HARD SECURITY BLOCK: Administrator role creation is prohibited
    if normalized_role.lower() in ("administrator", "admin"):
        logger.warning(
            "admin_creation_blocked",
            actor=current_user.email,
            attempted_email=payload.email,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Creation of additional Administrator accounts is prohibited. The platform permits exactly one Administrator.",
        )

    # 2. Validate allowed roles
    if normalized_role.capitalize() not in (UserRole.DISPATCHER.value, UserRole.TECHNICIAN.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{normalized_role}'. Permitted roles are 'Dispatcher' or 'Technician'.",
        )

    canonical_role_name = normalized_role.capitalize()
    email_clean = payload.email.strip().lower()

    async with AsyncSessionLocal() as session:
        # 3. Check for existing email
        existing_stmt = select(User).where(User.email == email_clean)
        existing_user = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User account with email '{email_clean}' already exists.",
            )

        # 4. Lookup role entity
        role_stmt = select(Role).where(Role.name == canonical_role_name)
        role_obj = (await session.execute(role_stmt)).scalar_one_or_none()
        if not role_obj:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Role '{canonical_role_name}' is not configured in database.",
            )

        now = datetime.now(timezone.utc)
        new_user = User(
            id=uuid.uuid4(),
            role_id=role_obj.id,
            email=email_clean,
            full_name=payload.full_name.strip(),
            phone=payload.phone.strip() if payload.phone else None,
            password_hash=get_password_hash(payload.password),
            status=UserStatus.ACTIVE,
            must_change_password=True,
            created_at=now,
            updated_at=now,
        )
        session.add(new_user)
        await session.flush()

        # NOTE: If canonical_role_name is 'Technician', we do NOT create a Technician
        # operational profile here. Operational profiles must be explicitly provisioned
        # through the Technician Management interface.

        # Audit log
        audit = AuditLog(
            id=uuid.uuid4(),
            user_id=current_user.id,
            action="USER_CREATED",
            entity="User",
            entity_id=str(new_user.id),
            reason=f"Administrator provisioned new user with role '{canonical_role_name}'",
            old_value=None,
            new_value=f"email={new_user.email}, role={canonical_role_name}",
        )
        session.add(audit)
        await session.commit()

        logger.info(
            "user_created_by_admin",
            user_id=str(new_user.id),
            email=new_user.email,
            role=canonical_role_name,
        )

        return UserAccountResponse(
            id=new_user.id,
            email=new_user.email,
            full_name=new_user.full_name,
            phone=new_user.phone,
            role=canonical_role_name,
            status=UserStatus.ACTIVE.value,
            must_change_password=new_user.must_change_password,
            created_at=new_user.created_at,
            last_login=None,
        )


@router.patch(
    "/{id}/status",
    response_model=UserAccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle user active/inactive status",
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR))],
)
async def toggle_user_status(
    id: UUID,
    payload: Optional[UserStatusPayload] = None,
    current_user: UserResponse = Depends(get_current_user),
) -> UserAccountResponse:
    """Toggle or update account status. Protects the primary Administrator account."""
    async with AsyncSessionLocal() as session:
        stmt = select(User).options(selectinload(User.role_rel)).where(User.id == id)
        user_obj = (await session.execute(stmt)).scalar_one_or_none()
        if not user_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID '{id}' not found.",
            )

        # Protect primary Administrator account from deactivation
        if user_obj.role == UserRole.ADMINISTRATOR.value or user_obj.email == "admin@fieldops.ai":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The primary Administrator account status cannot be modified.",
            )

        old_status = user_obj.status.value if hasattr(user_obj.status, "value") else str(user_obj.status)
        if payload and payload.status:
            new_status = payload.status
        else:
            new_status = UserStatus.INACTIVE if user_obj.status == UserStatus.ACTIVE else UserStatus.ACTIVE

        user_obj.status = new_status
        user_obj.updated_at = datetime.now(timezone.utc)

        audit = AuditLog(
            id=uuid.uuid4(),
            user_id=current_user.id,
            action="USER_STATUS_UPDATED",
            entity="User",
            entity_id=str(user_obj.id),
            reason=f"Administrator changed user status from {old_status} to {new_status.value}",
            old_value=f"status={old_status}",
            new_value=f"status={new_status.value}",
        )
        session.add(audit)
        await session.commit()

        return UserAccountResponse(
            id=user_obj.id,
            email=user_obj.email,
            full_name=user_obj.full_name,
            phone=user_obj.phone,
            role=user_obj.role,
            status=new_status.value,
            must_change_password=user_obj.must_change_password,
            created_at=user_obj.created_at,
            last_login=user_obj.last_login,
        )
