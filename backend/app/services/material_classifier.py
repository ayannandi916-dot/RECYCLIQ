"""Normalize and validate YOLO detections for material classification."""

from __future__ import annotations

import math
from typing import Any, TypedDict


MATERIAL_MAPPING: dict[str, str] = {
    "BIODEGRADABLE": "Biodegradable",
    "CARDBOARD": "Cardboard",
    "GLASS": "Glass",
    "METAL": "Metal",
    "PAPER": "Paper",
    "PLASTIC": "Plastic",
}


class ClassifiedDetection(TypedDict):
    label: str
    material_name: str
    confidence: float
    bounding_box: dict[str, float]


def classify_detection(detection: Any) -> ClassifiedDetection:
    """Validate a detector result and map its label to a display material name.

    Additional detector fields (for example class_id) are intentionally kept
    by the caller; this function returns only the normalized classification
    fields needed by persistence.
    """
    if not isinstance(detection, dict):
        raise ValueError("Detection must be an object.")

    raw_label = detection.get("label")
    if not isinstance(raw_label, str) or not raw_label.strip():
        raise ValueError("Detection label must be a non-empty string.")

    label = raw_label.strip().upper()
    material_name = MATERIAL_MAPPING.get(label)
    if material_name is None:
        raise ValueError(f"Unknown YOLO class: {label}")

    raw_confidence = detection.get("confidence")
    if isinstance(raw_confidence, bool) or not isinstance(raw_confidence, (int, float)):
        raise ValueError("Detection confidence must be a number.")
    confidence = float(raw_confidence)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("Detection confidence must be finite and between 0 and 1.")

    raw_box = detection.get("bounding_box")
    if not isinstance(raw_box, dict):
        raise ValueError("Detection bounding_box must be an object.")
    coordinates: dict[str, float] = {}
    for key in ("x1", "y1", "x2", "y2"):
        value = raw_box.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Bounding box coordinate {key} must be a number.")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Bounding box coordinate {key} must be finite.")
        coordinates[key] = number
    if coordinates["x2"] <= coordinates["x1"] or coordinates["y2"] <= coordinates["y1"]:
        raise ValueError("Detection bounding_box must have positive width and height.")

    return {
        "label": label,
        "material_name": material_name,
        "confidence": confidence,
        "bounding_box": coordinates,
    }


def classify_detections(detections: Any) -> list[ClassifiedDetection]:
    """Validate and classify a collection, preserving its order."""
    if not isinstance(detections, list):
        raise ValueError("Detections must be a list.")
    return [classify_detection(item) for item in detections]
