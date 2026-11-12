from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.recycler_application import RecyclerApplication
from app.schemas.recycler import (
    RecyclerApplicationCreate,
    RecyclerApplicationUpdate,
    RecyclerApplicationReject,
)


def submit_application(
    db: Session,
    user: User,
    data: RecyclerApplicationCreate,
):
    if user.role != "user":
        raise HTTPException(
            status_code=403,
            detail="Only regular users can apply for recycler access.",
        )

    existing = db.scalar(
        select(RecyclerApplication).where(
            RecyclerApplication.user_id == user.id
        )
    )

    if existing:
        if existing.status == "approved":
            raise HTTPException(
                status_code=409,
                detail="You are already an approved recycler.",
            )

        if existing.status == "pending":
            raise HTTPException(
                status_code=409,
                detail="You already have a pending application.",
            )

        # Allow rejected applications to be resubmitted.
        existing.business_name = data.business_name
        existing.contact_number = data.contact_number
        existing.business_address = data.business_address
        existing.city = data.city
        existing.state = data.state
        existing.postal_code = data.postal_code
        existing.registration_number = data.registration_number
        existing.website = str(data.website) if data.website else None
        existing.status = "pending"
        existing.rejection_reason = None
        existing.reviewed_by = None
        existing.reviewed_at = None

        application = existing

    else:
        application = RecyclerApplication(
            user_id=user.id,
            business_name=data.business_name,
            contact_number=data.contact_number,
            business_address=data.business_address,
            city=data.city,
            state=data.state,
            postal_code=data.postal_code,
            registration_number=data.registration_number,
            website=str(data.website) if data.website else None,
        )

        db.add(application)

    try:
        db.commit()
        db.refresh(application)
        return application
    except Exception:
        db.rollback()
        raise


def get_my_application(db: Session, user: User):
    application = db.scalar(
        select(RecyclerApplication).where(
            RecyclerApplication.user_id == user.id
        )
    )

    if not application:
        raise HTTPException(
            status_code=404,
            detail="No recycler application found.",
        )

    return application


def update_application(
    db: Session,
    user: User,
    data: RecyclerApplicationUpdate,
):
    application = get_my_application(db, user)

    if application.status != "rejected":
        raise HTTPException(
            status_code=409,
            detail="Only rejected applications can be edited and resubmitted.",
        )

    application.business_name = data.business_name
    application.contact_number = data.contact_number
    application.business_address = data.business_address
    application.city = data.city
    application.state = data.state
    application.postal_code = data.postal_code
    application.registration_number = data.registration_number
    application.website = str(data.website) if data.website else None

    application.status = "pending"
    application.rejection_reason = None
    application.reviewed_by = None
    application.reviewed_at = None

    try:
        db.commit()
        db.refresh(application)
        return application
    except Exception:
        db.rollback()
        raise


def get_all_applications(db: Session, application_status: str | None = None):
    query = select(RecyclerApplication).order_by(
        RecyclerApplication.created_at.desc()
    )

    if application_status:
        query = query.where(
            RecyclerApplication.status == application_status
        )

    return db.scalars(query).all()


def approve_application(
    db: Session,
    application_id: UUID,
    admin: User,
):
    application = db.scalar(
        select(RecyclerApplication)
        .where(RecyclerApplication.id == application_id)
        .with_for_update()
    )

    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")

    if application.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending applications can be approved.",
        )

    applicant = db.scalar(
        select(User)
        .where(User.id == application.user_id)
        .with_for_update()
    )

    if not applicant:
        raise HTTPException(
            status_code=404,
            detail="Applicant account not found.",
        )

    if applicant.role != "user":
        raise HTTPException(
            status_code=409,
            detail="Applicant is no longer eligible for approval.",
        )

    try:
        application.status = "approved"
        application.reviewed_by = admin.id
        application.reviewed_at = datetime.now(timezone.utc)
        application.rejection_reason = None

        applicant.role = "recycler"

        db.commit()
        db.refresh(application)

        return application

    except Exception:
        db.rollback()
        raise


def reject_application(
    db: Session,
    application_id: UUID,
    admin: User,
    data: RecyclerApplicationReject,
):
    application = db.scalar(
        select(RecyclerApplication)
        .where(RecyclerApplication.id == application_id)
        .with_for_update()
    )

    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")

    if application.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending applications can be rejected.",
        )

    try:
        application.status = "rejected"
        application.rejection_reason = data.reason
        application.reviewed_by = admin.id
        application.reviewed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(application)

        return application

    except Exception:
        db.rollback()
        raise