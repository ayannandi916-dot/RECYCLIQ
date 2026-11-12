import logging
from io import BytesIO

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends,
    HTTPException,
    status
)

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user
from app.database.dependencies import get_db

from app.models import (
    User,
    WasteScan,
    ScanObject,
    ScanObjectMaterial,
    Material,
    Recommendation
)

from app.utils.image_validator import validate_image
from app.services.cloudinary_service import upload_image, delete_image
from app.ai.detector import detect_waste
from app.services.recommendation_service import (
    generate_recommendations
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai",
    tags=["AI Waste Detection"]
)


# Map YOLO class labels to database material names.
MATERIAL_MAPPING = {
    "BIODEGRADABLE": "Biodegradable",
    "CARDBOARD": "Cardboard",
    "GLASS": "Glass",
    "METAL": "Metal",
    "PAPER": "Paper",
    "PLASTIC": "Plastic"
}


def mark_scan_failed(db: Session, scan_id):
    """
    Mark a scan as failed after an inference
    or database persistence error.
    """

    if scan_id is None:
        return

    try:
        # Recover the session after a failed transaction.
        db.rollback()

        # Retrieve the original scan using its preserved ID.
        scan = (
            db.query(WasteScan)
            .filter(WasteScan.id == scan_id)
            .first()
        )

        if scan:
            scan.scan_status = "failed"
            db.commit()

            logger.info(
                "Scan %s successfully marked as failed.",
                scan_id
            )

    except Exception:
        db.rollback()

        logger.exception(
            "Could not mark scan %s as failed.",
            scan_id
        )


@router.post(
    "/detect",
    status_code=status.HTTP_200_OK
)
async def detect_waste_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload an image, detect waste using YOLO,
    generate recommendations and persist results
    in Neon PostgreSQL.
    """

    await validate_image(file)

    image_bytes = await file.read()

    # Keep the database ID separately from the ORM object.
    scan_id = None
    image_data = None
    scan_committed = False

    def cleanup_uncommitted_image():
        """Delete the Cloudinary image only if its scan was not committed."""
        if (
            not scan_committed
            and image_data
            and image_data.get("public_id")
        ):
            try:
                delete_image(image_data["public_id"])
            except Exception:
                # Cleanup failure must not hide the original API error.
                logger.exception(
                    "Failed to clean up Cloudinary image: %s",
                    image_data["public_id"]
                )

    try:

        # -----------------------------------------
        # 1. Upload image to Cloudinary
        # -----------------------------------------

        image_data = await run_in_threadpool(
            upload_image,
            BytesIO(image_bytes)
        )

        # -----------------------------------------
        # 2. Create initial scan record
        # -----------------------------------------

        scan = WasteScan(
            user_id=current_user.id,
            image_url=image_data["image_url"],
            scan_status="pending"
        )

        db.add(scan)
        db.commit()

        # The initial scan is now durable. Preserve its ID before refresh.
        scan_committed = True
        scan_id = scan.id

        db.refresh(scan)

        # -----------------------------------------
        # 3. Run YOLO inference
        # -----------------------------------------

        result = await run_in_threadpool(
            detect_waste,
            image_bytes
        )

        detections = result["detections"]

        # -----------------------------------------
        # 4. Fetch materials from Neon
        # -----------------------------------------

        material_names = set(
            MATERIAL_MAPPING.values()
        )

        materials = (
            db.query(Material)
            .filter(Material.name.in_(material_names))
            .all()
        )

        material_lookup = {
            material.name: material
            for material in materials
        }

        missing_materials = (
            material_names - set(material_lookup.keys())
        )

        if missing_materials:
            raise RuntimeError(
                f"Missing materials in database: "
                f"{', '.join(sorted(missing_materials))}"
            )

        # -----------------------------------------
        # 5. Save detected objects,
        #    classifications and recommendations
        # -----------------------------------------

        saved_detections = []

        for detection in detections:

            object_label = detection["label"].upper()

            material_name = MATERIAL_MAPPING.get(
                object_label
            )

            if material_name is None:
                raise RuntimeError(
                    f"Unknown YOLO class: {object_label}"
                )

            material = material_lookup[material_name]

            # Create detected object.
            scan_object = ScanObject(
                scan_id=scan_id,
                object_label=object_label,
                detection_confidence=detection["confidence"],
                bounding_box=detection["bounding_box"]
            )

            db.add(scan_object)

            # Generate database ID before classification.
            db.flush()

            # Link detected object to material.
            classification = ScanObjectMaterial(
                scan_object_id=scan_object.id,
                material_id=material.id,
                confidence_score=detection["confidence"]
            )

            db.add(classification)

            # -----------------------------------------
            # Generate recommendations
            # -----------------------------------------

            recommendation_data = generate_recommendations(
                material_name
            )
            

            saved_recommendations = []

            for recommendation in recommendation_data:

                new_recommendation = Recommendation(
                    scan_object_id=scan_object.id,
                    recommendation_type=recommendation[
                        "recommendation_type"
                    ],
                    title=recommendation["title"],
                    description=recommendation["description"],
                    difficulty_level=recommendation[
                        "difficulty_level"
                    ],
                    estimated_co2_saved=recommendation[
                        "estimated_co2_saved"
                    ]
                )

                db.add(new_recommendation)

                saved_recommendations.append({
                    "type": recommendation["recommendation_type"],
                    "title": recommendation["title"],
                    "description": recommendation["description"],
                    "difficulty": recommendation["difficulty_level"],
                    "estimated_co2_saved": recommendation[
                        "estimated_co2_saved"
                    ]
                })

            # -----------------------------------------
            # Store detection response
            # -----------------------------------------

            saved_detections.append({
                **detection,
                "scan_object_id": str(scan_object.id),
                "material_id": str(material.id),
                "material_name": material.name,
                "recommendations": saved_recommendations
            })

        # -----------------------------------------
        # 6. Mark scan completed
        # -----------------------------------------

        scan = (
            db.query(WasteScan)
            .filter(WasteScan.id == scan_id)
            .first()
        )

        scan.scan_status = "completed"

        db.commit()
        db.refresh(scan)

        # -----------------------------------------
        # 7. Return complete response
        # -----------------------------------------

        return {
            "message": (
                "Waste detection and database persistence "
                "completed successfully."
            ),
            "scan_id": str(scan_id),
            "user_id": str(current_user.id),
            "image_url": scan.image_url,
            "scan_status": scan.scan_status,
            "image_width": result["image_width"],
            "image_height": result["image_height"],
            "total_detections": len(saved_detections),
            "detections": saved_detections
        }

    except FileNotFoundError:

        cleanup_uncommitted_image()
        mark_scan_failed(db, scan_id)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YOLO model checkpoint is unavailable."
        )

    except ValueError as error:

        cleanup_uncommitted_image()
        mark_scan_failed(db, scan_id)

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error)
        )

    except Exception:

        cleanup_uncommitted_image()

        logger.exception(
            "Waste detection or database persistence failed."
        )

        mark_scan_failed(db, scan_id)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Waste detection or database persistence failed."
            )
        )