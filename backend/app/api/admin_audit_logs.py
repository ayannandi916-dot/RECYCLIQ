from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.permissions import require_role
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.admin_audit import AdminAuditLogListResponse
from app.services.admin_audit_service import list_admin_audit_logs


router = APIRouter(
    prefix="/admin",
    tags=["Admin - Audit Logs"],
)


@router.get(
    "/audit-logs",
    response_model=AdminAuditLogListResponse,
)
def get_admin_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None, min_length=1, max_length=50),
    resource_type: str | None = Query(
        default=None,
        min_length=1,
        max_length=50,
    ),
    admin_id: UUID | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must be earlier than or equal to end_date.",
        )

    return list_admin_audit_logs(
        db=db,
        page=page,
        page_size=page_size,
        action=action,
        resource_type=resource_type,
        admin_id=admin_id,
        start_date=start_date,
        end_date=end_date,
    )