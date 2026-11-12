import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String(20),
        default="user",
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    waste_scans = relationship(
        "WasteScan",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    recycling_centres = relationship(
        "RecyclingCentre",
        back_populates="owner",
        passive_deletes=True
    )

    recycler_application = relationship(
        "RecyclerApplication",
        foreign_keys="RecyclerApplication.user_id",
        back_populates="applicant",
        uselist=False,
        cascade="all, delete-orphan",
    )