from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.models.recycling_centre import RecyclingCentre
from app.schemas.recycling_centre import (
    RecyclingCentreCreate,
    RecyclingCentreUpdate,
)


from app.models.material import Material
from app.models.recycling_centre_material import RecyclingCentreMaterial

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

def get_centre_materials(
    db: Session,
    current_user_id: UUID,
    centre_id: UUID,
):
    # Verify centre ownership
    get_centre(db, current_user_id, centre_id)

    statement = (
        select(Material)
        .join(
            RecyclingCentreMaterial,
            RecyclingCentreMaterial.material_id == Material.id,
        )
        .where(
            RecyclingCentreMaterial.recycling_centre_id == centre_id
        )
        .order_by(Material.name.asc())
    )

    return db.scalars(statement).all()

def replace_centre_materials(
    db: Session,
    current_user_id: UUID,
    centre_id: UUID,
    material_ids: list[UUID],
):
    # Verify centre ownership
    get_centre(db, current_user_id, centre_id)

    # Validate all material IDs before modifying anything
    if material_ids:
        statement = select(Material.id).where(
            Material.id.in_(material_ids)
        )

        existing_ids = set(db.scalars(statement).all())
        requested_ids = set(material_ids)

        missing_ids = requested_ids - existing_ids

        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "One or more materials do not exist",
                    "missing_material_ids": [
                        str(material_id)
                        for material_id in missing_ids
                    ],
                },
            )

    try:
        # Remove existing mappings
        db.execute(
            delete(RecyclingCentreMaterial).where(
                RecyclingCentreMaterial.recycling_centre_id == centre_id
            )
        )

        # Insert replacement mappings
        new_mappings = [
            RecyclingCentreMaterial(
                recycling_centre_id=centre_id,
                material_id=material_id,
            )
            for material_id in material_ids
        ]

        db.add_all(new_mappings)

        db.commit()

    except Exception:
        db.rollback()
        raise

    # Return the updated material list
    return get_centre_materials(
        db=db,
        current_user_id=current_user_id,
        centre_id=centre_id,
    )