import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    CheckConstraint,
    ForeignKey,
    Index,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class RecyclingCentre(Base):
    __tablename__ = "recycling_centres"

    __table_args__ = (
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="ck_recycling_centres_latitude"
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_recycling_centres_longitude"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="RESTRICT", name="fk_recycling_centres_owner_id_users"),
            nullable=True,
            
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    address: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    state: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    contact_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    accepted_materials = relationship(
    "RecyclingCentreMaterial",
    back_populates="recycling_centre",
    cascade="all, delete-orphan"
    )

    owner = relationship(
        "User",
        back_populates="recycling_centres"
    )

# Composite index for recycler centre listing
Index(
    "ix_recycling_centres_owner_created_at_id",
    RecyclingCentre.owner_id,
    RecyclingCentre.created_at.desc(),
    RecyclingCentre.id.asc(),
)    