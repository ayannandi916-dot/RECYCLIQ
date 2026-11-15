from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.recycling_centre import RecyclingCentre
from app.models.recycling_centre_material import RecyclingCentreMaterial


def list_public_centres(
    db: Session,
    city: str | None = None,
    state: str | None = None,
):
    statement = (
        select(RecyclingCentre)
        .where(RecyclingCentre.is_active.is_(True))
        .options(
            selectinload(RecyclingCentre.accepted_materials)
            .selectinload(RecyclingCentreMaterial.material)
        )
    )

    # Filter by city
    if city:
        statement = statement.where(
            RecyclingCentre.city.ilike(city.strip())
        )

    # Filter by state
    if state:
        statement = statement.where(
            RecyclingCentre.state.ilike(state.strip())
        )

    # Stable ordering
    statement = statement.order_by(
        RecyclingCentre.name.asc(),
        RecyclingCentre.id.asc(),
    )

    centres = db.scalars(statement).all()

    results = []

    for centre in centres:
        accepted_materials = []

        for mapping in centre.accepted_materials:
            material = mapping.material

            if material is not None and material.recyclable:
                accepted_materials.append({
                    "id": material.id,
                    "name": material.name,
                    "category": material.category,
                    "description": material.description,
                    "recyclable": material.recyclable,
                    "biodegradable": material.biodegradable,
                })

        results.append({
            "id": centre.id,
            "name": centre.name,
            "address": centre.address,
            "city": centre.city,
            "state": centre.state,
            "postal_code": centre.postal_code,
            "latitude": centre.latitude,
            "longitude": centre.longitude,
            "contact_number": centre.contact_number,
            "accepted_materials": accepted_materials,
        })

    return results