import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class WasteScan(Base):
    __tablename__ = "waste_scans"

    __table_args__ = (
        CheckConstraint(
            "scan_status IN ('pending', 'completed', 'failed')",
            name="ck_waste_scans_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        
    )

    image_url: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    scan_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user = relationship("User", back_populates="waste_scans")

    detected_objects = relationship(
        "ScanObject",
        back_populates="scan",
        cascade="all, delete-orphan"
    )

# Composite index for user scan history
Index(
    "ix_waste_scans_user_created_at_id",
    WasteScan.user_id,
    WasteScan.created_at.desc(),
    WasteScan.id.asc(),
)
    