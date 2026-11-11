import threading

import cv2
import numpy as np

from app.ai.model_loader import get_model


# Evaluation-based initial inference configuration
CONFIDENCE_THRESHOLD = 0.25
NMS_IOU_THRESHOLD = 0.70
IMAGE_SIZE = 640

# Protect the shared model during concurrent inference.
INFERENCE_LOCK = threading.Lock()


def detect_waste(image_bytes: bytes) -> dict:
    """
    Detect waste objects in an image using RECYCLIQ YOLO.
    """

    if not image_bytes:
        raise ValueError("Image data is empty.")

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)

    image = cv2.imdecode(
        image_array,
        cv2.IMREAD_COLOR
    )

    if image is None:
        raise ValueError("Unable to decode image.")

    height, width = image.shape[:2]

    with INFERENCE_LOCK:
        model = get_model()

        results = model.predict(
            source=image,
            conf=CONFIDENCE_THRESHOLD,
            iou=NMS_IOU_THRESHOLD,
            imgsz=IMAGE_SIZE,
            device="cpu",
            verbose=False
        )

    result = results[0]

    detections = []

    if result.boxes is not None:

        for box in result.boxes:

            coordinates = (
                box.xyxy[0]
                .cpu()
                .tolist()
            )

            class_id = int(box.cls[0].item())

            confidence = float(
                box.conf[0].item()
            )

            if isinstance(model.names, dict):
                class_name = model.names[class_id]
            else:
                class_name = model.names[class_id]

            detections.append({
                "class_id": class_id,
                "label": class_name,
                "confidence": round(confidence, 4),
                "bounding_box": {
                    "x1": round(coordinates[0], 2),
                    "y1": round(coordinates[1], 2),
                    "x2": round(coordinates[2], 2),
                    "y2": round(coordinates[3], 2)
                }
            })

    return {
        "image_width": width,
        "image_height": height,
        "total_detections": len(detections),
        "detections": detections
    }
    