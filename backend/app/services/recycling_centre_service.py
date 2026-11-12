from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recycling_centre import RecyclingCentre
from app.schemas.recycling_centre import (
    RecyclingCentreCreate,
    RecyclingCentreUpdate,
)


def create_centre(
    db: Session,
    current_user_id: UUID,
    centre_data: RecyclingCentreCreate,
):
    centre = RecyclingCentre(
        owner_id=current_user_id,
        **centre_data.model_dump(),
    )

    try:
        db.add(centre)
        db.commit()
        db.refresh(centre)
        return centre

    except Exception:
        db.rollback()
        raise


def get_my_centres(
    db: Session,
    current_user_id: UUID,
):
    statement = (
        select(RecyclingCentre)
        .where(RecyclingCentre.owner_id == current_user_id)
        .order_by(RecyclingCentre.created_at.desc())
    )

    return db.scalars(statement).all()


def get_centre(
    db: Session,
    current_user_id: UUID,
    centre_id: UUID,
):
    statement = select(RecyclingCentre).where(
        RecyclingCentre.id == centre_id,
        RecyclingCentre.owner_id == current_user_id,
    )

    centre = db.scalar(statement)

    if centre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recycling centre not found",
        )

    return centre


def update_centre(
    db: Session,
    current_user_id: UUID,
    centre_id: UUID,
    centre_data: RecyclingCentreUpdate,
):
    centre = get_centre(db, current_user_id, centre_id)

    update_data = centre_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(centre, field, value)

    try:
        db.commit()
        db.refresh(centre)
        return centre

    except Exception:
        db.rollback()
        raise


def delete_centre(
    db: Session,
    current_user_id: UUID,
    centre_id: UUID,
):
    centre = get_centre(db, current_user_id, centre_id)

    try:
        db.delete(centre)
        db.commit()

    except Exception:
        db.rollback()
        raise