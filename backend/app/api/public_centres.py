from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.services.public_centre_service import list_public_centres


router = APIRouter(
    prefix="/public/centres",
    tags=["Public - Recycling Centres"],
)


@router.get("")
def get_public_centres(
    city: str | None = Query(default=None, max_length=100),
    state: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    return list_public_centres(
        db=db,
        city=city,
        state=state,
    )