import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ML_DIR = PROJECT_ROOT / "ML experiments"
sys.path.insert(0, str(ML_DIR if ML_DIR.is_dir() else PROJECT_ROOT))

from evaluation_engine import box_iou, match_image, metrics, aggregate


def test_iou_identical_boxes():
    assert box_iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0


def test_iou_no_overlap():
    assert box_iou([0, 0, 1, 1], [2, 2, 3, 3]) == 0.0


def test_iou_degenerate_box():
    assert box_iou([0, 0, 0, 10], [0, 0, 10, 10]) == 0.0


def test_one_to_one_matching_and_false_positive():
    gt = [{"class": 0, "box": [0, 0, 10, 10]}]
    preds = [
        {"class": 0, "box": [0, 0, 10, 10], "confidence": 0.9},
        {"class": 0, "box": [0, 0, 10, 10], "confidence": 0.8},
    ]
    assert match_image(preds, gt, class_count=1)[0] == {"tp": 1, "fp": 1, "fn": 0}


def test_class_mismatch_is_fp_and_fn():
    gt = [{"class": 1, "box": [0, 0, 10, 10]}]
    preds = [{"class": 0, "box": [0, 0, 10, 10], "confidence": 0.9}]
    stats = match_image(preds, gt, class_count=2)
    assert stats[0] == {"tp": 0, "fp": 1, "fn": 0}
    assert stats[1] == {"tp": 0, "fp": 0, "fn": 1}


def test_zero_division_is_safe():
    assert metrics(0, 0, 0) == {"precision": 0.0, "recall": 0.0, "f1": 0.0}


def test_aggregate_micro_metrics():
    result = aggregate({0: {"tp": 3, "fp": 1, "fn": 1}, 1: {"tp": 1, "fp": 1, "fn": 0}})
    assert result["tp"] == 4
    assert result["fp"] == 2
    assert result["fn"] == 1
    assert result["precision"] == pytest.approx(4 / 6)
    assert result["recall"] == pytest.approx(4 / 5)


def test_invalid_class_is_rejected():
    with pytest.raises(ValueError, match="class"):
        match_image([{"class": 2, "box": [0, 0, 1, 1], "confidence": 0.9}], [], class_count=2)


def test_invalid_confidence_is_rejected():
    with pytest.raises(ValueError, match="confidence"):
        match_image([{"class": 0, "box": [0, 0, 1, 1], "confidence": float("nan")}], [], class_count=1)
