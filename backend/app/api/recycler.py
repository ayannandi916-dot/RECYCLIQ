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

from app.schemas.recycling_centre import (
    RecyclingCentreCreate,
    RecyclingCentreUpdate,
    RecyclingCentreResponse,
)

from app.services.recycling_centre_service import (
    create_centre,
    get_my_centres,
    get_centre,
    update_centre,
    delete_centre,
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

# =========================================================
# RECYCLER CENTRE MANAGEMENT
# =========================================================


@router.post(
    "/centres",
    response_model=RecyclingCentreResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_recycling_centre(
    centre_data: RecyclingCentreCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("recycler")),
):
    return create_centre(
        db=db,
        current_user_id=current_user.id,
        centre_data=centre_data,
    )


@router.get(
    "/centres",
    response_model=list[RecyclingCentreResponse],
)
def list_my_recycling_centres(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("recycler")),
):
    return get_my_centres(
        db=db,
        current_user_id=current_user.id,
    )


@router.get(
    "/centres/{centre_id}",
    response_model=RecyclingCentreResponse,
)
def get_recycling_centre(
    centre_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("recycler")),
):
    return get_centre(
        db=db,
        current_user_id=current_user.id,
        centre_id=centre_id,
    )


@router.put(
    "/centres/{centre_id}",
    response_model=RecyclingCentreResponse,
)
def update_recycling_centre(
    centre_id: UUID,
    centre_data: RecyclingCentreUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("recycler")),
):
    return update_centre(
        db=db,
        current_user_id=current_user.id,
        centre_id=centre_id,
        centre_data=centre_data,
    )


@router.delete(
    "/centres/{centre_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_recycling_centre(
    centre_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("recycler")),
):
    delete_centre(
        db=db,
        current_user_id=current_user.id,
        centre_id=centre_id,
    )

    return None


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