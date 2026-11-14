"""Run strict dataset audit, fixed-threshold evaluation, and standard Ultralytics mAP."""
import json
from collections import defaultdict
from pathlib import Path
import cv2
import yaml
from ultralytics import YOLO

from dataset_audit import audit_dataset, CLASS_NAMES
from evaluation_engine import match_image, aggregate, metrics
from paths import DATASET_DIR, DATA_YAML, MODEL_PATH, require_paths

IMAGE_SIZE = 640
DEVICE = "cpu"
CONFIDENCE = 0.25
NMS_IOU = 0.70
MATCH_IOU = 0.50
OUTPUT_DIR = Path(__file__).resolve().parent / "e3_reports"


def load_ground_truth(label_path: Path, width: int, height: int):
    """Read YOLO normalized xywh labels; malformed data is an error, never skipped."""
    if not label_path.is_file():
        raise FileNotFoundError(f"Missing ground-truth label: {label_path}")
    objects = []
    for line_no, line in enumerate(label_path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"{label_path}:{line_no}: expected five YOLO values")
        class_value, xc, yc, box_w, box_h = map(float, parts)
        class_id = int(class_value)
        if class_value != class_id or not 0 <= class_id < len(CLASS_NAMES):
            raise ValueError(f"{label_path}:{line_no}: invalid class id")
        x1 = (xc - box_w / 2) * width
        y1 = (yc - box_h / 2) * height
        x2 = (xc + box_w / 2) * width
        y2 = (yc + box_h / 2) * height
        objects.append({"class": class_id, "box": [x1, y1, x2, y2]})
    return objects


def _resolved_data_yaml():
    """Create a temporary YAML config using the current dataset paths."""
    config = yaml.safe_load(DATA_YAML.read_text(encoding="utf-8")) or {}

    config["path"] = str(DATASET_DIR.resolve())
    config["train"] = "train/images"
    config["val"] = "valid/images"
    config["test"] = "test/images"
    config["nc"] = len(CLASS_NAMES)
    config["names"] = CLASS_NAMES

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    config_path = OUTPUT_DIR / "evaluation_data.yaml"
    config_path.write_text(
        yaml.safe_dump(config, sort_keys=False),
        encoding="utf-8"
    )

    return str(config_path)

def evaluate_fixed_threshold(model):
    image_dir = DATASET_DIR / "valid" / "images"
    label_dir = DATASET_DIR / "valid" / "labels"
    class_totals = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    image_count = 0
    for image_path in sorted(p for p in image_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}):
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Unreadable validation image: {image_path}")
        height, width = image.shape[:2]
        gt = load_ground_truth(label_dir / f"{image_path.stem}.txt", width, height)
        result_list = model.predict(source=str(image_path), conf=CONFIDENCE, iou=NMS_IOU, imgsz=IMAGE_SIZE, device=DEVICE, verbose=False)
        if not result_list or result_list[0] is None:
            raise RuntimeError(f"Model returned no result for {image_path.name}")
        result = result_list[0]
        predictions = []
        if result.boxes is not None:
            for box in result.boxes:
                coords = box.xyxy[0].cpu().tolist()
                class_id = int(box.cls[0].cpu().item())
                confidence = float(box.conf[0].cpu().item())
                predictions.append({"class": class_id, "box": coords, "confidence": confidence})
        per_class = match_image(predictions, gt, class_count=len(CLASS_NAMES), match_iou=MATCH_IOU)
        for class_id, values in per_class.items():
            for key in ("tp", "fp", "fn"):
                class_totals[class_id][key] += values[key]
        image_count += 1

    normalized = {class_id: class_totals[class_id] for class_id in range(len(CLASS_NAMES))}
    overall = aggregate(normalized)
    per_class = {
        CLASS_NAMES[class_id]: {**values, **metrics(**values)}
        for class_id, values in normalized.items()
    }
    return {"images": image_count, "confidence_threshold": CONFIDENCE, "nms_iou_threshold": NMS_IOU, "matching_iou_threshold": MATCH_IOU, "overall": overall, "per_class": per_class}


def main():
    require_paths(DATA_YAML, MODEL_PATH, DATASET_DIR)
    audit = audit_dataset(DATASET_DIR)
    if not audit["passed"]:
        raise RuntimeError(f"Dataset audit failed with {len(audit['issues'])} issue(s):\n" + "\n".join(audit["issues"][:30]))

    model = YOLO(str(MODEL_PATH))
    fixed_metrics = evaluate_fixed_threshold(model)

    # Ultralytics mAP evaluation using corrected paths, independent of stale YAML paths.
    results = model.val(data=_resolved_data_yaml(), split="val", imgsz=IMAGE_SIZE, device=DEVICE, plots=False, verbose=False)
    box = results.box
    report = {
        "model": str(MODEL_PATH.resolve()),
        "dataset_yaml": str(DATA_YAML.resolve()),
        "split": "valid",
        "image_size": IMAGE_SIZE,
        "device": DEVICE,
        "dataset_audit": audit["counts"],
        "fixed_threshold_metrics": fixed_metrics,
        "ultralytics_metrics": {
            "precision": float(box.mp),
            "recall": float(box.mr),
            "map50": float(box.map50),
            "map50_95": float(box.map),
            "per_class_map50_95": [float(value) for value in box.maps],
        },
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "validation_metrics.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Saved report: {output_path}")


if __name__ == "__main__":
    main()
