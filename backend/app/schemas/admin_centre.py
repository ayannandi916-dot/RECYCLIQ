


from pydantic import BaseModel, ConfigDict

from app.schemas.recycling_centre import RecyclingCentreResponse


class AdminCentreListResponse(BaseModel):
    items: list[RecyclingCentreResponse]
    total: int
    page: int
    page_size: int
    pages: int

    model_config = ConfigDict(from_attributes=True)