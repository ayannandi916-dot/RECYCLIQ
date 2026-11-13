
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.waste_scan import WasteScan
from app.models.recycler_application import RecyclerApplication
from app.models.recycling_centre import RecyclingCentre
from app.models.scan_object import ScanObject


# ==================================================
# OVERVIEW ANALYTICS
# ==================================================

def get_overview(db: Session):

    total_users = db.scalar(
        select(func.count()).select_from(User)
    ) or 0

    active_users = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.is_active.is_(True))
    ) or 0

    inactive_users = total_users - active_users

    total_recyclers = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == "recycler")
    ) or 0

    total_scans = db.scalar(
        select(func.count()).select_from(WasteScan)
    ) or 0

    total_centres = db.scalar(
        select(func.count()).select_from(RecyclingCentre)
    ) or 0

    active_centres = db.scalar(
        select(func.count())
        .select_from(RecyclingCentre)
        .where(RecyclingCentre.is_active.is_(True))
    ) or 0

    application_counts = db.execute(
        select(
            RecyclerApplication.status,
            func.count(RecyclerApplication.id),
        )
        .group_by(RecyclerApplication.status)
    ).all()

    applications = {
        "pending": 0,
        "approved": 0,
        "rejected": 0,
    }

    for application_status, count in application_counts:
        applications[application_status] = count

    total_applications = sum(applications.values())

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": inactive_users,
            "recyclers": total_recyclers,
        },
        "scans": {
            "total": total_scans,
        },
        "centres": {
            "total": total_centres,
            "active": active_centres,
            "inactive": total_centres - active_centres,
        },
        "applications": {
            "total": total_applications,
            **applications,
        },
    }


# ==================================================
# SCAN ANALYTICS
# ==================================================

def get_scan_analytics(db: Session):

    status_counts = db.execute(
        select(
            WasteScan.scan_status,
            func.count(WasteScan.id),
        )
        .group_by(WasteScan.scan_status)
    ).all()

    status_data = {
        "pending": 0,
        "completed": 0,
        "failed": 0,
    }

    for scan_status, count in status_counts:
        status_data[scan_status] = count

    total_scans = sum(status_data.values())

    return {
        "total": total_scans,
        "pending": status_data["pending"],
        "completed": status_data["completed"],
        "failed": status_data["failed"],
    }


# ==================================================
# RECYCLER ANALYTICS
# ==================================================

def get_recycler_analytics(db: Session):

    total_recyclers = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == "recycler")
    ) or 0

    application_counts = db.execute(
        select(
            RecyclerApplication.status,
            func.count(RecyclerApplication.id),
        )
        .group_by(RecyclerApplication.status)
    ).all()

    applications = {
        "pending": 0,
        "approved": 0,
        "rejected": 0,
    }

    for application_status, count in application_counts:
        applications[application_status] = count

    total_applications = sum(applications.values())

    return {
        "total_recyclers": total_recyclers,
        "applications": {
            "total": total_applications,
            **applications,
        },
    }


# ==================================================
# RECYCLING CENTRE ANALYTICS
# ==================================================

def get_centre_analytics(db: Session):

    total = db.scalar(
        select(func.count()).select_from(RecyclingCentre)
    ) or 0

    active = db.scalar(
        select(func.count())
        .select_from(RecyclingCentre)
        .where(RecyclingCentre.is_active.is_(True))
    ) or 0

    inactive = total - active

    locations = db.execute(
        select(
            RecyclingCentre.state,
            func.count(RecyclingCentre.id),
        )
        .group_by(RecyclingCentre.state)
        .order_by(desc(func.count(RecyclingCentre.id)))
    ).all()

    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "by_state": [
            {
                "state": state,
                "total": count,
            }
            for state, count in locations
        ],
    }


# ==================================================
# OBJECT DETECTION ANALYTICS
# ==================================================

def get_object_analytics(db: Session):

    total_objects = db.scalar(
        select(func.count()).select_from(ScanObject)
    ) or 0

    objects_by_label = db.execute(
        select(
            ScanObject.object_label,
            func.count(ScanObject.id),
        )
        .group_by(ScanObject.object_label)
        .order_by(desc(func.count(ScanObject.id)))
    ).all()

    average_confidence = db.scalar(
        select(func.avg(ScanObject.detection_confidence))
    )

    return {
        "total_objects": total_objects,
        "average_confidence": (
            round(float(average_confidence), 4)
            if average_confidence is not None
            else None
        ),
        "by_label": [
            {
                "label": label,
                "count": count,
            }
            for label, count in objects_by_label
        ],
    }


# ==================================================
# RECENT PLATFORM ACTIVITY
# ==================================================

def get_recent_activity(db: Session, limit: int = 20):

    recent_users = db.execute(
        select(User.id, User.name, User.created_at)
        .order_by(User.created_at.desc())
        .limit(limit)
    ).all()

    recent_scans = db.execute(
        select(
            WasteScan.id,
            WasteScan.scan_status,
            WasteScan.created_at,
        )
        .order_by(WasteScan.created_at.desc())
        .limit(limit)
    ).all()

    recent_applications = db.execute(
        select(
            RecyclerApplication.id,
            RecyclerApplication.business_name,
            RecyclerApplication.status,
            RecyclerApplication.created_at,
        )
        .order_by(RecyclerApplication.created_at.desc())
        .limit(limit)
    ).all()

    recent_centres = db.execute(
        select(
            RecyclingCentre.id,
            RecyclingCentre.name,
            RecyclingCentre.city,
            RecyclingCentre.created_at,
        )
        .order_by(RecyclingCentre.created_at.desc())
        .limit(limit)
    ).all()

    activities = []

    for user in recent_users:
        activities.append({
            "type": "user_registered",
            "description": f"New user registered: {user.name}",
            "timestamp": user.created_at,
            "entity_id": str(user.id),
        })

    for scan in recent_scans:
        activities.append({
            "type": "waste_scan",
            "description": f"Waste scan {scan.scan_status}",
            "timestamp": scan.created_at,
            "entity_id": str(scan.id),
        })

    for application in recent_applications:
        activities.append({
            "type": "recycler_application",
            "description": (
                f"{application.business_name}: "
                f"{application.status}"
            ),
            "timestamp": application.created_at,
            "entity_id": str(application.id),
        })

    for centre in recent_centres:
        activities.append({
            "type": "recycling_centre",
            "description": (
                f"New centre registered: "
                f"{centre.name}, {centre.city}"
            ),
            "timestamp": centre.created_at,
            "entity_id": str(centre.id),
        })

    activities.sort(
        key=lambda item: item["timestamp"],
        reverse=True,
    )

    return activities[:limit]
