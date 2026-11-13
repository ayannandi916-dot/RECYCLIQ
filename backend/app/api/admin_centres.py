from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.api.permissions import require_role
from app.models.user import User

from app.schemas.recycling_centre import RecyclingCentreResponse
from app.schemas.admin_centre import AdminCentreListResponse

from app.services.admin_centre_service import (
    list_all_centres,
    get_admin_centre,
    set_centre_status,
)


router = APIRouter(
    prefix="/admin/centres",
    tags=["Admin - Recycling Centres"],
)


@router.get(
    "",
    response_model=AdminCentreListResponse,
)
def admin_list_centres(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=150),
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return list_all_centres(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
    )


@router.get(
    "/{centre_id}",
    response_model=RecyclingCentreResponse,
)
def admin_get_centre(
    centre_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return get_admin_centre(db, centre_id)


@router.patch(
    "/{centre_id}/activate",
    response_model=RecyclingCentreResponse,
)
def activate_centre(
    centre_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return set_centre_status(
        db=db,
        centre_id=centre_id,
        is_active=True,
    )


@router.patch(
    "/{centre_id}/deactivate",
    response_model=RecyclingCentreResponse,
)
def deactivate_centre(
    centre_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return set_centre_status(
        db=db,
        centre_id=centre_id,
        is_active=False,
    )