"""Database resolution for material records used by scan persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Material


def resolve_materials(db: Session, material_names: set[str]) -> dict[str, Material]:
    """Fetch only the required materials in one query.

    An empty set performs no database query. Missing records are reported
    explicitly so a scan cannot silently persist an incomplete classification.
    """
    if not material_names:
        return {}

    materials = (
        db.query(Material)
        .filter(Material.name.in_(material_names))
        .all()
    )
    lookup = {material.name: material for material in materials}
    missing = material_names - set(lookup)
    if missing:
        raise RuntimeError(
            "Missing materials in database: " + ", ".join(sorted(missing))
        )
    return lookup


def resolve_materials_for_detections(db: Session, classified: list[dict[str, Any]]) -> dict[str, Material]:
    """Resolve the distinct material names present in classified detections."""
    return resolve_materials(
        db,
        {item["material_name"] for item in classified},
    )
