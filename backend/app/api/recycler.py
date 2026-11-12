from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.api.dependencies import get_current_user
from app.api.permissions import require_role

from app.models.user import User

from app.schemas.recycler import (
    RecyclerApplicationCreate,
    RecyclerApplicationUpdate,
    RecyclerApplicationResponse,
    RecyclerApplicationReject,
)

from app.services.recycler_service import (
    submit_application,
    get_my_application,
    update_application,
    get_all_applications,
    approve_application,
    reject_application,
)


router = APIRouter(prefix="/recycler", tags=["Recycler"])

admin_router = APIRouter(prefix="/admin/recycler", tags=["Admin - Recycler"])


# USER ROUTES

@router.post(
    "/apply",
    response_model=RecyclerApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_for_recycler(
    data: RecyclerApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("user")),
):
    return submit_application(db, current_user, data)


@router.get(
    "/application",
    response_model=RecyclerApplicationResponse,
)
def my_application(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_my_application(db, current_user)


@router.put(
    "/application",
    response_model=RecyclerApplicationResponse,
)
def edit_application(
    data: RecyclerApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("user")),
):
    return update_application(db, current_user, data)


# ADMIN ROUTES

@admin_router.get("/applications")
def list_applications(
    application_status: str | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return get_all_applications(db, application_status)


@admin_router.post(
    "/applications/{application_id}/approve",
    response_model=RecyclerApplicationResponse,
)
def approve_recycler(
    application_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return approve_application(db, application_id, admin)


@admin_router.post(
    "/applications/{application_id}/reject",
    response_model=RecyclerApplicationResponse,
)
def reject_recycler(
    application_id: UUID,
    data: RecyclerApplicationReject,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return reject_application(db, application_id, admin, data)