"""Strict audit of RECYCLIQ's cleaned YOLO detection dataset."""
from collections import Counter
import math
from pathlib import Path
import cv2

from paths import DATASET_DIR

CLASS_NAMES = ["BIODEGRADABLE", "CARDBOARD", "GLASS", "METAL", "PAPER", "PLASTIC"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
SPLITS = ("train", "valid", "test")


def _read_label_rows(label_path: Path, split: str, issues: list[str]):
    try:
        return label_path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        issues.append(f"{split}/{label_path.name}: cannot read label file: {exc}")
        return []


def audit_dataset(root: Path = DATASET_DIR) -> dict:
    root = Path(root)
    issues: list[str] = []
    counts = Counter()
    for split in SPLITS:
        image_dir, label_dir = root / split / "images", root / split / "labels"
        if not image_dir.is_dir() or not label_dir.is_dir():
            issues.append(f"{split}: missing images/ or labels/ directory")
            continue
        images = sorted(p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
        labels = {p.stem: p for p in label_dir.glob("*.txt") if p.is_file()}
        image_stems = {p.stem for p in images}
        for stem in sorted(image_stems - labels.keys()):
            issues.append(f"{split}: missing label for image {stem}")
        for stem in sorted(labels.keys() - image_stems):
            issues.append(f"{split}: orphan label {stem}")
        counts[f"{split}_images"] = len(images)
        counts[f"{split}_label_files"] = len(labels)

        for image_path in images:
            image = cv2.imread(str(image_path))
            if image is None:
                issues.append(f"{split}: unreadable image {image_path.name}")
                continue
            counts[f"{split}_readable_images"] += 1
            label_path = labels.get(image_path.stem)
            if label_path is None:
                continue
            rows = _read_label_rows(label_path, split, issues)
            for line_no, line in enumerate(rows, 1):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) != 5:
                    issues.append(f"{split}/{label_path.name}:{line_no}: expected 5 values, got {len(parts)}")
                    continue
                try:
                    values = [float(v) for v in parts]
                    if not all(math.isfinite(v) for v in values):
                        raise ValueError("non-finite value")
                    class_value, x, y, w, h = values
                    class_id = int(class_value)
                    if class_value != class_id or not 0 <= class_id < len(CLASS_NAMES):
                        raise ValueError(f"invalid class id {class_value}")
                    if not all(0.0 <= v <= 1.0 for v in (x, y, w, h)):
                        raise ValueError("normalized coordinates must be in [0, 1]")
                    if w <= 0 or h <= 0:
                        raise ValueError("box width and height must be positive")
                    eps = 1e-6
                    if x - w / 2 < -eps or x + w / 2 > 1 + eps or y - h / 2 < -eps or y + h / 2 > 1 + eps:
                        raise ValueError("bounding box extends outside image")
                    counts[f"class_{class_id}"] += 1
                    counts[f"{split}_annotations"] += 1
                    counts["annotations"] += 1
                except (ValueError, OverflowError) as exc:
                    issues.append(f"{split}/{label_path.name}:{line_no}: {exc}")

    return {"passed": not issues, "counts": dict(counts), "issues": issues}


if __name__ == "__main__":
    result = audit_dataset()
    print("RECYCLIQ CLEANED DATASET AUDIT")
    for key, value in sorted(result["counts"].items()):
        print(f"{key}: {value}")
    print(f"Issues: {len(result['issues'])}")
    for issue in result["issues"][:100]:
        print(f"ERROR: {issue}")
    if not result["passed"]:
        raise SystemExit("Dataset audit failed; refusing model evaluation.")
    print("Dataset audit passed.")
