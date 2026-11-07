import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Float,
    String,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ScanObjectMaterial(Base):
    __tablename__ = "scan_object_materials"

    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_scan_object_materials_confidence"
        ),
        CheckConstraint(
            "quantity_estimate IS NULL OR quantity_estimate >= 0",
            name="ck_scan_object_materials_quantity"
        ),
        UniqueConstraint(
            "scan_object_id",
            "material_id",
            name="uq_scan_object_material"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    scan_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    quantity_estimate: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    quantity_unit: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    scan_object = relationship(
        "ScanObject",
        back_populates="material_classifications"
    )

    material = relationship("Material")