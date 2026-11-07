from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends,
    HTTPException,
    status
)
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.dependencies import get_db
from app.models import User, WasteScan
from app.utils.image_validator import validate_image
from app.services.cloudinary_service import upload_image


router = APIRouter(
    prefix="/scans",
    tags=["Waste Scanning"]
)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_waste_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    await validate_image(file)

    image_data = None

    try:
        image_data = upload_image(file.file)

        new_scan = WasteScan(
            user_id=current_user.id,
            image_url=image_data["image_url"],
            scan_status="pending"
        )

        db.add(new_scan)
        db.commit()
        db.refresh(new_scan)

        return {
            "message": "Image uploaded and scan created successfully!",
            "scan_id": str(new_scan.id),
            "user_id": str(current_user.id),
            "image_url": new_scan.image_url,
            "scan_status": new_scan.scan_status
        }

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to upload image or create scan."
        )