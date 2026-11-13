from datetime import datetime
from pydantic import BaseModel


class UserAnalytics(BaseModel):
    total: int
    active: int
    inactive: int
    recyclers: int


class ScanAnalytics(BaseModel):
    total: int
    pending: int
    completed: int
    failed: int


class CentreAnalytics(BaseModel):
    total: int
    active: int
    inactive: int


class ApplicationAnalytics(BaseModel):
    total: int
    pending: int
    approved: int
    rejected: int


class OverviewResponse(BaseModel):
    users: UserAnalytics
    scans: dict
    centres: CentreAnalytics
    applications: ApplicationAnalytics


class ScanStatusAnalytics(BaseModel):
    total: int
    pending: int
    completed: int
    failed: int


class RecyclerAnalytics(BaseModel):
    total_recyclers: int
    applications: ApplicationAnalytics


class CentreStateAnalytics(BaseModel):
    state: str
    total: int


class CentreAnalyticsResponse(BaseModel):
    total: int
    active: int
    inactive: int
    by_state: list[CentreStateAnalytics]


class ObjectLabelAnalytics(BaseModel):
    label: str
    count: int


class ObjectAnalyticsResponse(BaseModel):
    total_objects: int
    average_confidence: float | None
    by_label: list[ObjectLabelAnalytics]


class ActivityItem(BaseModel):
    type: str
    description: str
    timestamp: datetime
    entity_id: str | None = None


class ActivityResponse(BaseModel):
    total: int
    items: list[ActivityItem]