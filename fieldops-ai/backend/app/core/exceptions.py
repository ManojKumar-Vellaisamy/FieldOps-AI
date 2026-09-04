"""
Custom exception hierarchy and FastAPI exception handlers.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


# ── Custom Exception Hierarchy ────────────────────────────────────────────────

class FieldOpsException(Exception):
    """Base exception for all FieldOps AI application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_ERROR",
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class NotFoundError(FieldOpsException):
    """Raised when a requested resource is not found."""

    def __init__(self, resource: str, resource_id: str | int) -> None:
        super().__init__(
            message=f"{resource} with id '{resource_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
        )


class ConflictError(FieldOpsException):
    """Raised when a resource already exists or causes a conflict."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT",
        )


class ValidationError(FieldOpsException):
    """Raised for domain-level validation failures."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
        )


class BadRequestError(FieldOpsException):
    """Raised when client sends invalid request data or domain rule violation."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BAD_REQUEST",
        )


class UnauthorizedError(FieldOpsException):
    """Raised when authentication credentials are missing or invalid."""

    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
        )


class ForbiddenError(FieldOpsException):
    """Raised when the authenticated user lacks permission."""

    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
        )


# ── Exception Handlers ────────────────────────────────────────────────────────

async def fieldops_exception_handler(
    request: Request,  # noqa: ARG001
    exc: FieldOpsException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app."""
    app.add_exception_handler(FieldOpsException, fieldops_exception_handler)  # type: ignore[arg-type]
