import logging
from io import BytesIO

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.database.connection import SessionLocal
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
from app.services.material_classifier import classify_detections
from app.services.material_service import resolve_materials_for_detections
from app.ai.detector import detect_waste


logger = logging.getLogger(__name__)


def mark_scan_failed(db: Session, scan_id):
    """Mark an already-created scan as failed using a fresh transaction."""
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


def process_scan_sync(
    image_bytes: bytes,
    user_id,
    session_factory=None,
):
    """
    Run the complete blocking scan workflow in one worker thread.

    This function owns its SQLAlchemy session from creation through close.
    Never pass a request-scoped Session into this function.
    """
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image data is empty.",
        )

    db = (session_factory or SessionLocal)()
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
        # 1. Upload image.
        image_data = upload_image(BytesIO(image_bytes))

        # 2. Create initial pending scan record.
        scan = WasteScan(
            user_id=user_id,
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
            result = detect_waste(image_bytes)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="YOLO model checkpoint is unavailable.",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

        detections = result["detections"]

        # 4. Classify detections and resolve only required materials.
        try:
            classified_detections = classify_detections(detections)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

        material_lookup = resolve_materials_for_detections(
            db,
            classified_detections,
        )

        # 5. Persist objects, classifications and recommendations.
        saved_detections = []

        for detection, classified in zip(
            detections,
            classified_detections,
        ):
            object_label = classified["label"]
            material_name = classified["material_name"]
            material = material_lookup[material_name]

            scan_object = ScanObject(
                scan_id=scan_id,
                object_label=object_label,
                detection_confidence=classified["confidence"],
                bounding_box=classified["bounding_box"],
            )

            db.add(scan_object)
            db.flush()

            classification = ScanObjectMaterial(
                scan_object_id=scan_object.id,
                material_id=material.id,
                confidence_score=classified["confidence"],
            )
            db.add(classification)

            recommendation_data = generate_recommendations(material_name)
            saved_recommendations = []

            for recommendation in recommendation_data:
                new_recommendation = Recommendation(
                    scan_object_id=scan_object.id,
                    recommendation_type=recommendation["recommendation_type"],
                    title=recommendation["title"],
                    description=recommendation["description"],
                    difficulty_level=recommendation["difficulty_level"],
                    estimated_co2_saved=recommendation["estimated_co2_saved"],
                )
                db.add(new_recommendation)

                saved_recommendations.append({
                    "type": recommendation["recommendation_type"],
                    "title": recommendation["title"],
                    "description": recommendation["description"],
                    "difficulty": recommendation["difficulty_level"],
                    "estimated_co2_saved": recommendation["estimated_co2_saved"],
                })

            saved_detections.append({
                **detection,
                "label": object_label,
                "confidence": classified["confidence"],
                "bounding_box": classified["bounding_box"],
                "scan_object_id": str(scan_object.id),
                "material_id": str(material.id),
                "material_name": material.name,
                "recommendations": saved_recommendations,
            })

        # 6. Mark scan completed and commit all scan results atomically.
        scan = (
            db.query(WasteScan)
            .filter(WasteScan.id == scan_id)
            .first()
        )

        if scan is None:
            raise RuntimeError("Scan record disappeared during processing.")

        scan.scan_status = "completed"
        db.commit()
        db.refresh(scan)

        return {
            "message": (
                "Waste detection and database persistence "
                "completed successfully."
            ),
            "scan_id": str(scan_id),
            "user_id": str(user_id),
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

    finally:
        db.close()


async def process_scan(image_bytes: bytes, user_id):
    """
    Async entry point. All synchronous I/O and SQLAlchemy work runs
    in one worker thread with a session created and closed there.
    """
    return await run_in_threadpool(
        process_scan_sync,
        image_bytes,
        user_id,
    )
