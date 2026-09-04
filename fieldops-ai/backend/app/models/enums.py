"""
Application database domain enums.
"""

from enum import Enum


class UserRole(str, Enum):
    """Supported enterprise security roles."""

    ADMINISTRATOR = "Administrator"
    DISPATCHER = "Dispatcher"
    TECHNICIAN = "Technician"


class UserStatus(str, Enum):
    """User account status."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class JobStatus(str, Enum):
    """Job / Work Order lifecycle status."""

    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    TRAVELLING = "TRAVELLING"
    ARRIVED = "ARRIVED"
    WORKING = "WORKING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Priority(str, Enum):
    """Job priority urgency level."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AssignmentType(str, Enum):
    """Source of job assignment."""

    SYSTEM = "SYSTEM"
    MANUAL = "MANUAL"
