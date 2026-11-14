from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.models.recycling_centre import RecyclingCentre


def list_all_centres(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    is_active: bool | None = None,
):
    statement = select(RecyclingCentre)

    if search:
        search_term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                RecyclingCentre.name.ilike(search_term),
                RecyclingCentre.city.ilike(search_term),
                RecyclingCentre.state.ilike(search_term),
            )
        )

    if is_active is not None:
        statement = statement.where(
            RecyclingCentre.is_active == is_active
        )

    total = db.scalar(
        select(func.count()).select_from(
            statement.order_by(None).subquery()
        )
    )

    centres = db.scalars(
        statement
        .order_by(
            RecyclingCentre.created_at.desc(),
            RecyclingCentre.id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "items": centres,
        "total": total or 0,
        "page": page,
        "page_size": page_size,
        "pages": (
            (total + page_size - 1) // page_size
            if total else 0
        ),
    }


def get_admin_centre(
    db: Session,
    centre_id: UUID,
):
    centre = db.scalar(
        select(RecyclingCentre).where(
            RecyclingCentre.id == centre_id
        )
    )

    if centre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recycling centre not found",
        )

    return centre


def set_centre_status(
    db: Session,
    centre_id: UUID,
    is_active: bool,
):
    centre = get_admin_centre(db, centre_id)

    # Idempotent: repeated requests do not cause errors.
    if centre.is_active == is_active:
        return centre

    try:
        centre.is_active = is_active
        db.commit()
        db.refresh(centre)
        return centre

    except Exception:
        db.rollback()
        raise