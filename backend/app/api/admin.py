from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.permissions import require_role
from app.database.dependencies import get_db
from app.models import User
from app.schemas.admin import (
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserStatusResponse,
)
from app.services.admin_service import (
    list_users,
    get_user_by_id,
    set_user_active_status,
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin User Management"],
)


@router.get(
    "/users",
    response_model=AdminUserListResponse,
)
def get_all_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str | None = Query(None, min_length=1, max_length=20),
    search: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return list_users(
        db=db,
        page=page,
        page_size=page_size,
        role=role,
        search=search,
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserResponse,
)
def get_user_details(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return get_user_by_id(db, user_id)


@router.patch(
    "/users/{user_id}/activate",
    response_model=AdminUserStatusResponse,
)
def activate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    user = set_user_active_status(
        db=db,
        user_id=user_id,
        is_active=True,
        admin_id=admin.id,
    )

    return {
        "message": "User account activated successfully.",
        "user": user,
    }


@router.patch(
    "/users/{user_id}/deactivate",
    response_model=AdminUserStatusResponse,
)
def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    user = set_user_active_status(
        db=db,
        user_id=user_id,
        is_active=False,
        admin_id=admin.id,
    )

    return {
        "message": "User account deactivated successfully.",
        "user": user,
    }