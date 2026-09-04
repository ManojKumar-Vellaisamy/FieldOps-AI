"""
Standard API response utilities.
Provides consistent response envelopes for all endpoints.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class SuccessResponse(BaseModel, Generic[DataT]):
    """Standard success response envelope."""

    data: DataT
    message: str = "Success"


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Standard paginated response envelope."""

    data: list[DataT]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(
        cls,
        data: list[DataT],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[DataT]":
        import math
        return cls(
            data=data,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
        )


def success_response(data: Any, message: str = "Success") -> dict[str, Any]:
    """Return a plain success dict for endpoints that don't use Pydantic response_model."""
    return {"data": data, "message": message}
