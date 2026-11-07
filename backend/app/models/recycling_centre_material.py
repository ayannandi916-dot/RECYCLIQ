import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class RecyclingCentreMaterial(Base):
    __tablename__ = "recycling_centre_materials"

    __table_args__ = (
        UniqueConstraint(
            "recycling_centre_id",
            "material_id",
            name="uq_recycling_centre_material"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    recycling_centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recycling_centres.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    recycling_centre = relationship(
        "RecyclingCentre",
        back_populates="accepted_materials"
    )

    material = relationship("Material")