import math
import threading

import cv2
import numpy as np

from app.ai.model_loader import get_model


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
    """

    if not image_bytes:
        raise ValueError("Image data is empty.")

    image_array = np.frombuffer(
        image_bytes,
        dtype=np.uint8,
    )

    image = cv2.imdecode(
        image_array,
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise ValueError("Unable to decode image.")

    height, width = image.shape[:2]

    if width <= 0 or height <= 0:
        raise ValueError("Invalid image dimensions.")

    # Run inference using the shared model.
    with INFERENCE_LOCK:
        model = get_model()

        results = model.predict(
            source=image,
            conf=CONFIDENCE_THRESHOLD,
            iou=NMS_IOU_THRESHOLD,
            imgsz=IMAGE_SIZE,
            device="cpu",
            verbose=False,
        )

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
            class_id = int(box.cls[0].item())

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

            detections.append({
                "class_id": class_id,
                "label": class_name,
                "confidence": round(confidence, 4),
                "bounding_box": {
                    "x1": round(x1, 2),
                    "y1": round(y1, 2),
                    "x2": round(x2, 2),
                    "y2": round(y2, 2),
                },
            })

    return {
        "image_width": width,
        "image_height": height,
        "total_detections": len(detections),
        "detections": detections,
    }