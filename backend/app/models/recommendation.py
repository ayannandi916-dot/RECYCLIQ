import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    CheckConstraint
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    __table_args__ = (
        CheckConstraint(
            "recommendation_type IN "
            "('reuse', 'repair', 'recycle', 'upcycle')",
            name="ck_recommendations_type"
        ),
        CheckConstraint(
            "difficulty_level IN ('easy', 'medium', 'hard')",
            name="ck_recommendations_difficulty"
        ),
        CheckConstraint(
            "estimated_co2_saved IS NULL OR estimated_co2_saved >= 0",
            name="ck_recommendations_co2"
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

    recommendation_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    title: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    difficulty_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    estimated_co2_saved: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    scan_object = relationship(
        "ScanObject",
        back_populates="recommendations"
    )