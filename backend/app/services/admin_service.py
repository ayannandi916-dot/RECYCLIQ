from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.models import User
from app.services.audit_log_service import log_admin_action


def list_users(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    role: str | None = None,
    search: str | None = None,
):
    query = db.query(User)

    if role:
        query = query.filter(User.role == role)

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.name.ilike(search_term),
                User.email.ilike(search_term),
            )
        )

    total = query.count()

    users = (
        query
        .order_by(User.created_at.desc(), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size

    return {
        "users": users,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_user_by_id(db: Session, user_id: UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return user


def set_user_active_status(
    db: Session,
    user_id: UUID,
    is_active: bool,
    admin: User | None = None,
    admin_id: UUID | None = None,
) -> User:

    try:
        # Resolve administrator for both supported calling styles.
        if admin is None:
            if admin_id is None:
                raise ValueError("An administrator must be provided.")

            admin = db.query(User).filter(User.id == admin_id).first()

        if admin is None or admin.role != "admin":
            raise ValueError("Valid administrator not found.")

        # Serialize administrator deactivation operations.
        if not is_active:
            db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": 726381},
            )

        user = get_user_by_id(db, user_id)

        # Prevent an admin from deactivating their own account.
        if not is_active and user.id == admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account.",
            )

        # Prevent deactivation of the last active administrator.
        if not is_active and user.role == "admin" and user.is_active:
            active_admin_count = (
                db.query(func.count(User.id))
                .filter(
                    User.role == "admin",
                    User.is_active.is_(True),
                )
                .scalar()
            )

            if active_admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate the last active administrator.",
                )

        # Idempotent operation: don't create duplicate audit entries.
        if user.is_active == is_active:
            db.rollback()
            return user

        old_status = user.is_active

        user.is_active = is_active

        # Record the administrative action.
        log_admin_action(
            db=db,
            admin=admin,
            action="ACTIVATE" if is_active else "DEACTIVATE",
            resource_type="USER",
            resource_id=user.id,
            old_values={
                "is_active": old_status,
            },
            new_values={
                "is_active": is_active,
            },
        )

        # Commit user update and audit record together.
        db.commit()
        db.refresh(user)

        return user

    except Exception:
        db.rollback()
        raise