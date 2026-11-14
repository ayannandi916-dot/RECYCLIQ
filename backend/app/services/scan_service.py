import logging
from io import BytesIO

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from starlette.concurrency import run_in_threadpool

from app.models import (
    User,
    WasteScan,
    ScanObject,
    ScanObjectMaterial,
    Material,
    Recommendation,
)

from app.services.cloudinary_service import upload_image, delete_image
from app.services.recommendation_service import generate_recommendations
from app.ai.detector import detect_waste


logger = logging.getLogger(__name__)


MATERIAL_MAPPING = {
    "BIODEGRADABLE": "Biodegradable",
    "CARDBOARD": "Cardboard",
    "GLASS": "Glass",
    "METAL": "Metal",
    "PAPER": "Paper",
    "PLASTIC": "Plastic",
}


def mark_scan_failed(db: Session, scan_id):
    """
    Mark an already-created scan as failed.

    Uses a fresh transaction after rolling back any failed
    detection or persistence transaction.
    """

    if scan_id is None:
        return

    try:
        db.rollback()

        scan = (
            db.query(WasteScan)
            .filter(WasteScan.id == scan_id)
            .first()
        )

        if scan is not None:
            scan.scan_status = "failed"
            db.commit()

            logger.info("Scan %s marked as failed.", scan_id)

    except Exception:
        db.rollback()

        logger.exception(
            "Could not mark scan %s as failed.",
            scan_id,
        )


async def process_scan(
    image_bytes: bytes,
    current_user: User,
    db: Session,
):
    """
    Complete scanning workflow:

    1. Upload image to Cloudinary.
    2. Create pending scan.
    3. Run YOLO inference.
    4. Classify detected materials.
    5. Generate recommendations.
    6. Persist all results.
    7. Mark scan completed.
    """

    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image data is empty.",
        )

    image_data = None
    scan_id = None
    scan_committed = False

    def cleanup_uncommitted_image():
        if (
            not scan_committed
            and image_data
            and image_data.get("public_id")
        ):
            try:
                deleted = delete_image(image_data["public_id"])

                if not deleted:
                    logger.warning(
                        "Cloudinary did not confirm deletion of image %s.",
                        image_data["public_id"],
                )
            except Exception:
                logger.exception(
                    "Failed to delete uncommitted Cloudinary image."
                )

    try:

        # 1. Upload image to Cloudinary.

        image_data = await run_in_threadpool(
            upload_image,
            BytesIO(image_bytes),
        )

        # 2. Create initial scan record.

        scan = WasteScan(
            user_id=current_user.id,
            image_url=image_data["image_url"],
            scan_status="pending",
        )

        db.add(scan)
        db.commit()

        scan_committed = True
        scan_id = scan.id

        db.refresh(scan)

        # 3. Run YOLO inference.

        try:
            result = await run_in_threadpool(
                detect_waste,
                image_bytes,
            )

        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="YOLO model checkpoint is unavailable.",
         )

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            )

        detections = result["detections"]

        # 4. Fetch materials in one query.

        material_names = set(MATERIAL_MAPPING.values())

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
                "Missing materials in database: "
                + ", ".join(sorted(missing_materials))
            )

        # 5. Persist detected objects, classifications
        #    and recommendations.

        saved_detections = []

        for detection in detections:

            object_label = detection["label"].upper()

            material_name = MATERIAL_MAPPING.get(object_label)

            if material_name is None:
                raise RuntimeError(
                    f"Unknown YOLO class: {object_label}"
                )

            material = material_lookup[material_name]

            scan_object = ScanObject(
                scan_id=scan_id,
                object_label=object_label,
                detection_confidence=detection["confidence"],
                bounding_box=detection["bounding_box"],
            )

            db.add(scan_object)
            db.flush()

            classification = ScanObjectMaterial(
                scan_object_id=scan_object.id,
                material_id=material.id,
                confidence_score=detection["confidence"],
            )

            db.add(classification)

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
                    ],
                )

                db.add(new_recommendation)

                saved_recommendations.append({
                    "type": recommendation["recommendation_type"],
                    "title": recommendation["title"],
                    "description": recommendation["description"],
                    "difficulty": recommendation["difficulty_level"],
                    "estimated_co2_saved": recommendation[
                        "estimated_co2_saved"
                    ],
                })

            saved_detections.append({
                **detection,
                "scan_object_id": str(scan_object.id),
                "material_id": str(material.id),
                "material_name": material.name,
                "recommendations": saved_recommendations,
            })

        # 6. Mark scan completed.

        scan = db.query(WasteScan).filter(
            WasteScan.id == scan_id
        ).first()

        if scan is None:
            raise RuntimeError(
                "Scan record disappeared during processing."
            )

        scan.scan_status = "completed"

        db.commit()
        db.refresh(scan)

        # 7. Return complete result.

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
            "detections": saved_detections,
        }

    except Exception:
        cleanup_uncommitted_image()

        logger.exception("Scan processing failed.")

        if scan_committed:
            mark_scan_failed(db, scan_id)
        else:
            db.rollback()

        raise

