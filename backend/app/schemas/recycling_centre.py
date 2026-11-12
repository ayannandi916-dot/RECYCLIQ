from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RecyclingCentreCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=5, max_length=1000)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)

    postal_code: str | None = Field(default=None, max_length=20)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    contact_number: str | None = Field(default=None, max_length=20)
    is_active: bool = True


class RecyclingCentreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = Field(default=None, min_length=5, max_length=1000)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    state: str | None = Field(default=None, min_length=2, max_length=100)

    postal_code: str | None = Field(default=None, max_length=20)

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    contact_number: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class RecyclingCentreResponse(BaseModel):
    id: UUID
    owner_id: UUID

    name: str
    address: str
    city: str
    state: str
    postal_code: str | None

    latitude: float
    longitude: float

    contact_number: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)