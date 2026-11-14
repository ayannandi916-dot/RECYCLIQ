import logging
import math
import threading
import time

import cv2
import numpy as np

from app.ai.model_loader import get_model


logger = logging.getLogger(__name__)


# Existing evaluation-based inference configuration
CONFIDENCE_THRESHOLD = 0.25
NMS_IOU_THRESHOLD = 0.70
IMAGE_SIZE = 640

# Protect the shared model during concurrent inference.
INFERENCE_LOCK = threading.Lock()


def detect_waste(image_bytes: bytes) -> dict:
    """
    Detect waste objects using the RECYCLIQ YOLO model.

    Validates image decoding, inference results,
    class IDs, confidence scores and bounding boxes.

    Records performance timings for image decoding,
    model acquisition, inference and total execution.
    """

    total_started = time.perf_counter()

    # --------------------------------------------------
    # 1. Validate and decode image
    # --------------------------------------------------

    decode_started = time.perf_counter()

    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ValueError("Image data is empty or invalid.")

    try:
        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8,
        )

        image = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR,
        )

    except (ValueError, TypeError, cv2.error) as exc:
        raise ValueError("Unable to decode image.") from exc

    if image is None:
        raise ValueError("Unable to decode image.")

    height, width = image.shape[:2]

    if width <= 0 or height <= 0:
        raise ValueError("Invalid image dimensions.")

    decode_ms = (
        time.perf_counter() - decode_started
    ) * 1000

    # --------------------------------------------------
    # 2. Run inference using the shared model
    # --------------------------------------------------

    lock_started = time.perf_counter()

    with INFERENCE_LOCK:

        lock_wait_ms = (
            time.perf_counter() - lock_started
        ) * 1000

        model_started = time.perf_counter()

        model = get_model()

        model_acquisition_ms = (
            time.perf_counter() - model_started
        ) * 1000

        inference_started = time.perf_counter()

        results = model.predict(
            source=image,
            conf=CONFIDENCE_THRESHOLD,
            iou=NMS_IOU_THRESHOLD,
            imgsz=IMAGE_SIZE,
            device="cpu",
            verbose=False,
        )

        inference_ms = (
            time.perf_counter() - inference_started
        ) * 1000

    # --------------------------------------------------
    # 3. Validate inference results
    # --------------------------------------------------

    if results is None or len(results) == 0:
        raise RuntimeError(
            "YOLO returned no inference results."
        )

    result = results[0]

    if result is None:
        raise RuntimeError(
            "YOLO returned an invalid inference result."
        )

    detections = []

    if result.boxes is not None:

        for box in result.boxes:

            # Extract bounding-box coordinates.
            coordinates = (
                box.xyxy[0]
                .cpu()
                .tolist()
            )

            if len(coordinates) != 4:
                raise RuntimeError(
                    "YOLO returned an invalid bounding box."
                )

            coordinates = [
                float(value)
                for value in coordinates
            ]

            if not all(
                math.isfinite(value)
                for value in coordinates
            ):
                raise RuntimeError(
                    "YOLO returned non-finite bounding-box coordinates."
                )

            x1, y1, x2, y2 = coordinates

            if not (
                0 <= x1 < x2 <= width
                and 0 <= y1 < y2 <= height
            ):
                raise RuntimeError(
                    "YOLO returned out-of-bounds bounding-box coordinates."
                )

            # Extract class ID.
            raw_class_id = float(box.cls[0].item())

            if (
                not math.isfinite(raw_class_id)
                or not raw_class_id.is_integer()
                or raw_class_id < 0
            ):
                raise RuntimeError("YOLO returned an invalid class ID.")

            class_id = int(raw_class_id)

            # Support both dictionary and list class names.
            class_names = model.names

            if isinstance(class_names, dict):
                class_name = class_names.get(class_id)

            elif isinstance(class_names, (list, tuple)):
                class_name = (
                    class_names[class_id]
                    if 0 <= class_id < len(class_names)
                    else None
                )

            else:
                raise RuntimeError(
                    "YOLO returned an unsupported class-name mapping."
                )

            if not isinstance(class_name, str) or not class_name.strip():
                raise RuntimeError(
                    f"Invalid YOLO class ID: {class_id}"
                )

            # Extract confidence.
            confidence = float(
                box.conf[0].item()
            )

            if (
                not math.isfinite(confidence)
                or not 0 <= confidence <= 1
            ):
                raise RuntimeError(
                    "YOLO returned an invalid confidence score."
                )

            rounded_coordinates = [
                round(value, 2)
                for value in coordinates
            ]

            x1, y1, x2, y2 = rounded_coordinates

            if not (x1 < x2 and y1 < y2):
                raise RuntimeError(
                    "YOLO returned an invalid bounding box after rounding."
                )

            detections.append({
                "class_id": class_id,
                "label": class_name,
                "confidence": round(confidence, 4),
                "bounding_box": {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                },
            })

    # --------------------------------------------------
    # 4. Performance logging
    # --------------------------------------------------

    total_ms = (
        time.perf_counter() - total_started
    ) * 1000

    logger.info(
        "YOLO detection timing | "
        "decode_ms=%.2f | "
        "lock_wait_ms=%.2f | "
        "model_acquisition_ms=%.2f | "
        "inference_ms=%.2f | "
        "total_ms=%.2f",
        decode_ms,
        lock_wait_ms,
        model_acquisition_ms,
        inference_ms,
        total_ms,
    )

    # --------------------------------------------------
    # 5. Return detection response
    # --------------------------------------------------

    return {
        "image_width": width,
        "image_height": height,
        "total_detections": len(detections),
        "detections": detections,
    }