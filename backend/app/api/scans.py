import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends,
    HTTPException,
    status,
    Query,
)
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user
from app.database.dependencies import get_db
from app.models import (
    User,
    WasteScan,
    ScanObject,
    ScanObjectMaterial,
)
from app.utils.image_validator import validate_image
from app.services.scan_service import process_scan


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/scans",
    tags=["Waste Scanning"],
)


@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_waste_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    await validate_image(file)
    image_bytes = await file.read()

    try:
        return await process_scan(
            image_bytes=image_bytes,
            user_id=current_user.id,
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception("Scan upload and processing failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Scan processing failed.",
        ) from exc


@router.get("/history")
def get_scan_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
):
    offset = (page - 1) * limit

    scans = (
        db.query(WasteScan)
        .filter(WasteScan.user_id == current_user.id)
        .order_by(
            WasteScan.created_at.desc(),
            WasteScan.id.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    total_scans = (
        db.query(WasteScan)
        .filter(WasteScan.user_id == current_user.id)
        .count()
    )

    return {
        "total_scans": total_scans,
        "page": page,
        "limit": limit,
        "scans": [
            {
                "scan_id": str(scan.id),
                "image_url": scan.image_url,
                "scan_status": scan.scan_status,
                "created_at": scan.created_at,
            }
            for scan in scans
        ],
    }


@router.get("/{scan_id}")
def get_scan_details(
    scan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve complete scan details including detected objects,
    material classifications and recycling recommendations.
    Users can only access their own scans.
    """
    scan = (
        db.query(WasteScan)
        .options(
            selectinload(
                WasteScan.detected_objects
            ).selectinload(
                ScanObject.material_classifications
            ).selectinload(
                ScanObjectMaterial.material
            ),
            selectinload(
                WasteScan.detected_objects
            ).selectinload(
                ScanObject.recommendations
            ),
        )
        .filter(
            WasteScan.id == scan_id,
            WasteScan.user_id == current_user.id,
        )
        .first()
    )

    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found.",
        )

    detected_objects = []

    for obj in scan.detected_objects:
        classifications = []

        for classification in obj.material_classifications:
            material = classification.material
            classifications.append({
                "material_id": str(material.id),
                "material_name": material.name,
                "category": material.category,
                "recyclable": material.recyclable,
                "biodegradable": material.biodegradable,
                "confidence_score": classification.confidence_score,
                "quantity_estimate": classification.quantity_estimate,
                "quantity_unit": classification.quantity_unit,
            })

        recommendations = []

        for recommendation in obj.recommendations:
            recommendations.append({
                "recommendation_id": str(recommendation.id),
                "type": recommendation.recommendation_type,
                "title": recommendation.title,
                "description": recommendation.description,
                "difficulty": recommendation.difficulty_level,
                "estimated_co2_saved": recommendation.estimated_co2_saved,
                "created_at": recommendation.created_at.isoformat(),
            })

        detected_objects.append({
            "scan_object_id": str(obj.id),
            "object_label": obj.object_label,
            "detection_confidence": obj.detection_confidence,
            "bounding_box": obj.bounding_box,
            "created_at": obj.created_at.isoformat(),
            "materials": classifications,
            "recommendations": recommendations,
        })

    return {
        "message": "Scan details retrieved successfully.",
        "scan": {
            "scan_id": str(scan.id),
            "user_id": str(scan.user_id),
            "image_url": scan.image_url,
            "scan_status": scan.scan_status,
            "created_at": scan.created_at.isoformat(),
            "total_detected_objects": len(detected_objects),
            "total_recommendations": sum(
                len(obj["recommendations"])
                for obj in detected_objects
            ),
            "detected_objects": detected_objects,
        },
    }
