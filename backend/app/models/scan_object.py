import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Float,
    DateTime,
    ForeignKey,
    CheckConstraint
)

from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ScanObject(Base):
    __tablename__ = "scan_objects"

    __table_args__ = (
        CheckConstraint(
            "detection_confidence >= 0 AND detection_confidence <= 1",
            name="ck_scan_objects_confidence"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("waste_scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    object_label: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    detection_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    bounding_box: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    scan = relationship(
        "WasteScan",
        back_populates="detected_objects"
    )
    
    material_classifications = relationship(
    "ScanObjectMaterial",
    back_populates="scan_object",
    cascade="all, delete-orphan"
    )