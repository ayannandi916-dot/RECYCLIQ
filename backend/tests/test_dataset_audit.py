import sys
from pathlib import Path
import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ML_DIR = PROJECT_ROOT / "ML experiments"
sys.path.insert(0, str(ML_DIR if ML_DIR.is_dir() else PROJECT_ROOT))

from dataset_audit import audit_dataset


def _make_split(root, split="valid"):
    image_dir = root / split / "images"
    label_dir = root / split / "labels"
    image_dir.mkdir(parents=True)
    label_dir.mkdir(parents=True)
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    assert cv2.imwrite(str(image_dir / "sample.jpg"), image)
    (label_dir / "sample.txt").write_text("0 0.5 0.5 0.25 0.25\n", encoding="utf-8")
    return image_dir, label_dir


def test_audit_reports_missing_splits(tmp_path):
    _make_split(tmp_path)
    report = audit_dataset(tmp_path)
    assert not report["passed"]
    assert any("missing images/ or labels/ directory" in issue for issue in report["issues"])


def test_audit_accepts_valid_dataset(tmp_path):
    for split in ("train", "valid", "test"):
        _make_split(tmp_path, split)
    report = audit_dataset(tmp_path)
    assert report["passed"]
    assert report["counts"]["annotations"] == 3


def test_audit_rejects_malformed_annotation(tmp_path):
    for split in ("train", "valid", "test"):
        _, labels = _make_split(tmp_path, split)
        (labels / "sample.txt").write_text("0 0.5 0.5 0.2\n", encoding="utf-8")
    report = audit_dataset(tmp_path)
    assert not report["passed"]
    assert any("expected 5 values" in issue for issue in report["issues"])


def test_audit_rejects_missing_and_orphan_labels(tmp_path):
    for split in ("train", "valid", "test"):
        image_dir, label_dir = _make_split(tmp_path, split)
        (image_dir / "unlabelled.jpg").write_bytes((image_dir / "sample.jpg").read_bytes())
        (label_dir / "orphan.txt").write_text("", encoding="utf-8")
    report = audit_dataset(tmp_path)
    assert not report["passed"]
    assert any("missing label" in issue for issue in report["issues"])
    assert any("orphan label" in issue for issue in report["issues"])
