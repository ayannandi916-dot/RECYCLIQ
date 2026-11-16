from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AdminAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    admin_id: UUID | None
    admin_email: str | None
    action: str
    resource_type: str
    resource_id: UUID | None
    old_values: dict | None
    new_values: dict | None
    created_at: datetime


class AdminAuditLogListResponse(BaseModel):
    logs: list[AdminAuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int