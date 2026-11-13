from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.permissions import require_role
from app.database.dependencies import get_db
from app.models import User

from app.services.admin_analytics_service import (
    get_overview,
    get_scan_analytics,
    get_recycler_analytics,
    get_centre_analytics,
    get_object_analytics,
    get_recent_activity,
)

from app.schemas.admin_analytics import (
    OverviewResponse,
    ScanStatusAnalytics,
    RecyclerAnalytics,
    CentreAnalyticsResponse,
    ObjectAnalyticsResponse,
    ActivityResponse,
)


router = APIRouter(
    prefix="/admin/analytics",
    tags=["Admin Analytics"],
)


# --------------------------------------------------
# OVERVIEW
# --------------------------------------------------

@router.get(
    "/overview",
    response_model=OverviewResponse,
)
def analytics_overview(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return get_overview(db)


# --------------------------------------------------
# SCAN ANALYTICS
# --------------------------------------------------

@router.get(
    "/scans",
    response_model=ScanStatusAnalytics,
)
def analytics_scans(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return get_scan_analytics(db)


# --------------------------------------------------
# RECYCLER ANALYTICS
# --------------------------------------------------

@router.get(
    "/recyclers",
    response_model=RecyclerAnalytics,
)
def analytics_recyclers(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return get_recycler_analytics(db)


# --------------------------------------------------
# RECYCLING CENTRE ANALYTICS
# --------------------------------------------------

@router.get(
    "/centres",
    response_model=CentreAnalyticsResponse,
)
def analytics_centres(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return get_centre_analytics(db)


# --------------------------------------------------
# OBJECT DETECTION ANALYTICS
# --------------------------------------------------

@router.get(
    "/objects",
    response_model=ObjectAnalyticsResponse,
)
def analytics_objects(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    return get_object_analytics(db)


# --------------------------------------------------
# RECENT PLATFORM ACTIVITY
# --------------------------------------------------

@router.get(
    "/activity",
    response_model=ActivityResponse,
)
def analytics_activity(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    items = get_recent_activity(
        db=db,
        limit=limit,
    )

    return {
        "total": len(items),
        "items": items,
    }