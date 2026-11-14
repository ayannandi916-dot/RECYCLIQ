import math

import pytest

from app.services.material_classifier import (
    MATERIAL_MAPPING,
    classify_detection,
    classify_detections,
)


def detection(label="PLASTIC", confidence=0.95):
    return {
        "class_id": 5,
        "label": label,
        "confidence": confidence,
        "bounding_box": {"x1": 10, "y1": 20, "x2": 100, "y2": 120},
    }


@pytest.mark.parametrize("label,expected", list(MATERIAL_MAPPING.items()))
def test_classifies_all_supported_materials(label, expected):
    assert classify_detection(detection(label))["material_name"] == expected


def test_normalizes_case_and_whitespace():
    result = classify_detection(detection("  pLaStIc  "))
    assert result["label"] == "PLASTIC"
    assert result["material_name"] == "Plastic"


@pytest.mark.parametrize("label", [None, "", "   ", 5, "WOOD"])
def test_rejects_missing_empty_or_unsupported_label(label):
    with pytest.raises(ValueError):
        classify_detection(detection(label))


@pytest.mark.parametrize("confidence", [None, "0.5", True, -0.1, 1.1, math.nan, math.inf, -math.inf])
def test_rejects_invalid_confidence(confidence):
    with pytest.raises(ValueError):
        classify_detection(detection(confidence=confidence))


@pytest.mark.parametrize("box", [None, [], {}, {"x1": 0, "y1": 0, "x2": 1},
                                  {"x1": 2, "y1": 0, "x2": 1, "y2": 1},
                                  {"x1": 0, "y1": 0, "x2": 1, "y2": math.nan}])
def test_rejects_invalid_bounding_box(box):
    item = detection()
    item["bounding_box"] = box
    with pytest.raises(ValueError):
        classify_detection(item)


def test_rejects_non_object_detection_and_non_list_collection():
    with pytest.raises(ValueError):
        classify_detection("PLASTIC")
    with pytest.raises(ValueError):
        classify_detections(None)


def test_classifies_multiple_different_materials_in_order():
    items = [detection("PLASTIC"), detection("GLASS"), detection("METAL")]
    result = classify_detections(items)
    assert [item["material_name"] for item in result] == ["Plastic", "Glass", "Metal"]
