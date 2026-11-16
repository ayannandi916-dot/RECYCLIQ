from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def list_admin_audit_logs(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
    resource_type: str | None = None,
    admin_id: UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    query = select(AuditLog)

    filters = []

    if action:
        filters.append(AuditLog.action == action.upper())

    if resource_type:
        filters.append(
            AuditLog.resource_type == resource_type.upper()
        )

    if admin_id:
        filters.append(AuditLog.admin_id == admin_id)

    if start_date:
        filters.append(AuditLog.created_at >= start_date)

    if end_date:
        filters.append(AuditLog.created_at <= end_date)

    if filters:
        query = query.where(*filters)

    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0

    logs = db.scalars(
        query
        .order_by(
            AuditLog.created_at.desc(),
            AuditLog.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "logs": logs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (
            (total + page_size - 1) // page_size
            if total
            else 0
        ),
    }