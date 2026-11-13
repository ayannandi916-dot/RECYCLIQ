from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing import Literal
from datetime import datetime
from uuid import UUID

class RecyclerApplicationCreate(BaseModel):
    
    business_name: str = Field(min_length=2, max_length=150)
    contact_number: str = Field(min_length=7, max_length=20)
    business_address: str = Field(min_length=5, max_length=1000)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    registration_number: str | None = Field(default=None, max_length=100)
    website: HttpUrl | None = None


class RecyclerApplicationUpdate(BaseModel):
    business_name: str = Field(min_length=2, max_length=150)
    contact_number: str = Field(min_length=7, max_length=20)
    business_address: str = Field(min_length=5, max_length=1000)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    registration_number: str | None = Field(default=None, max_length=100)
    website: HttpUrl | None = None


class RecyclerApplicationResponse(BaseModel):
    id: UUID
    user_id: UUID
    business_name: str
    contact_number: str
    business_address: str
    city: str
    state: str
    postal_code: str | None
    registration_number: str | None
    website: str | None
    status: Literal["pending", "approved", "rejected"]
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecyclerApplicationReject(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)