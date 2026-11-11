import gc
import csv
from pathlib import Path
from collections import defaultdict

import numpy as np
from ultralytics import YOLO


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

MODEL_PATH = (
    PROJECT_DIR
    / "runs"
    / "runs"
    / "recycliq"
    / "yolo11n_100ep"
    / "weights"
    / "best.pt"
)

IMAGE_DIR = (
    BASE_DIR
    / "datasets"
    / "waste"
    / "cleaned"
    / "detection"
    / "valid"
    / "images"
)

LABEL_DIR = (
    BASE_DIR
    / "datasets"
    / "waste"
    / "cleaned"
    / "detection"
    / "valid"
    / "labels"
)

CLASS_NAMES = [
    "BIODEGRADABLE",
    "CARDBOARD",
    "GLASS",
    "METAL",
    "PAPER",
    "PLASTIC",
]

IMAGE_SIZE = 640
DEVICE = "cpu"

# Detection configurations:
# (confidence threshold, NMS IoU threshold)

CONFIGURATIONS = [
    (0.25, 0.70),
    (0.30, 0.50),
    (0.35, 0.50),
    (0.40, 0.50),
]

# IoU used to match predictions with ground truth.
# This is separate from the NMS IoU above.

MATCH_IOU = 0.50

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


# ============================================================
# GROUND TRUTH LOADING
# ============================================================

def load_ground_truth(label_path, image_width, image_height):

    ground_truth = []

    if not label_path.exists():
        return ground_truth

    with open(label_path, "r") as file:

        for line in file:

            values = line.strip().split()

            if len(values) != 5:
                continue

            try:
                cls = int(values[0])

                cx = float(values[1])
                cy = float(values[2])
                w = float(values[3])
                h = float(values[4])

            except ValueError:
                continue

            if cls < 0 or cls >= len(CLASS_NAMES):
                continue

            # YOLO normalized coordinates -> pixel coordinates

            x1 = (cx - w / 2) * image_width
            y1 = (cy - h / 2) * image_height

            x2 = (cx + w / 2) * image_width
            y2 = (cy + h / 2) * image_height

            ground_truth.append({
                "class": cls,
                "box": [x1, y1, x2, y2],
            })

    return ground_truth


# ============================================================
# IOU CALCULATION
# ============================================================

def calculate_iou(box1, box2):

    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])

    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection_width = max(0, x2 - x1)
    intersection_height = max(0, y2 - y1)

    intersection = (
        intersection_width * intersection_height
    )

    area1 = (
        max(0, box1[2] - box1[0])
        * max(0, box1[3] - box1[1])
    )

    area2 = (
        max(0, box2[2] - box2[0])
        * max(0, box2[3] - box2[1])
    )

    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


# ============================================================
# EVALUATE ONE IMAGE
# ============================================================

def evaluate_image(predictions, ground_truth):

    stats = {
        cls: {
            "tp": 0,
            "fp": 0,
            "fn": 0,
        }
        for cls in range(len(CLASS_NAMES))
    }

    for cls in range(len(CLASS_NAMES)):

        class_predictions = [
            p for p in predictions
            if p["class"] == cls
        ]

        class_ground_truth = [
            g for g in ground_truth
            if g["class"] == cls
        ]

        matched_gt = set()

        # Highest-confidence predictions first

        class_predictions.sort(
            key=lambda p: p["confidence"],
            reverse=True
        )

        for prediction in class_predictions:

            best_iou = 0.0
            best_gt_index = None

            for gt_index, gt in enumerate(class_ground_truth):

                if gt_index in matched_gt:
                    continue

                iou = calculate_iou(
                    prediction["box"],
                    gt["box"]
                )

                if iou > best_iou:

                    best_iou = iou
                    best_gt_index = gt_index

            if (
                best_gt_index is not None
                and best_iou >= MATCH_IOU
            ):

                stats[cls]["tp"] += 1
                matched_gt.add(best_gt_index)

            else:

                stats[cls]["fp"] += 1

        # Unmatched ground-truth objects are false negatives

        stats[cls]["fn"] += (
            len(class_ground_truth) - len(matched_gt)
        )

    return stats


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(tp, fp, fn):

    precision = (
        tp / (tp + fp)
        if tp + fp > 0
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if tp + fn > 0
        else 0.0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall > 0
        else 0.0
    )

    return precision, recall, f1


# ============================================================
# VALIDATION FOR ONE CONFIGURATION
# ============================================================

def run_validation(model, images, conf, nms_iou):

    total = {
        cls: {
            "tp": 0,
            "fp": 0,
            "fn": 0,
        }
        for cls in range(len(CLASS_NAMES))
    }

    print("\n" + "=" * 65)
    print(f"CONFIDENCE: {conf} | NMS IOU: {nms_iou}")
    print("=" * 65)

    processed = 0

    for image_path in images:

        label_path = (
            LABEL_DIR / f"{image_path.stem}.txt"
        )

        # Run inference on ONE image at a time.
        # This keeps CPU memory usage manageable.

        results = model.predict(
            source=str(image_path),
            imgsz=IMAGE_SIZE,
            conf=conf,
            iou=nms_iou,
            device=DEVICE,
            verbose=False,
            max_det=300,
        )

        result = results[0]

        image_height, image_width = result.orig_shape

        ground_truth = load_ground_truth(
            label_path,
            image_width,
            image_height
        )

        predictions = []

        if result.boxes is not None:

            for box in result.boxes:

                predictions.append({

                    "class": int(box.cls[0]),

                    "box": box.xyxy[0].cpu().tolist(),

                    "confidence": float(box.conf[0]),
                })

        image_stats = evaluate_image(
            predictions,
            ground_truth
        )

        for cls, values in image_stats.items():

            for key in ("tp", "fp", "fn"):

                total[cls][key] += values[key]

        processed += 1

        del results
        del predictions
        del ground_truth
        del image_stats

        # Release temporary CPU memory periodically

        if processed % 50 == 0:

            gc.collect()

            print(
                f"Processed {processed}/{len(images)}"
            )

    gc.collect()

    # ========================================================
    # OVERALL RESULTS
    # ========================================================

    tp = sum(v["tp"] for v in total.values())
    fp = sum(v["fp"] for v in total.values())
    fn = sum(v["fn"] for v in total.values())

    precision, recall, f1 = calculate_metrics(
        tp, fp, fn
    )

    print("\nOVERALL RESULTS")

    print(f"Images: {processed}")
    print(f"TP: {tp}")
    print(f"FP: {fp}")
    print(f"FN: {fn}")

    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1 Score: {f1:.4f}")

    # ========================================================
    # PER-CLASS RESULTS
    # ========================================================

    print("\nPER-CLASS RESULTS")

    class_results = []

    for cls, name in enumerate(CLASS_NAMES):

        values = total[cls]

        p, r, class_f1 = calculate_metrics(
            values["tp"],
            values["fp"],
            values["fn"]
        )

        print(f"\n{name}")

        print(f"TP: {values['tp']}")
        print(f"FP: {values['fp']}")
        print(f"FN: {values['fn']}")

        print(f"Precision: {p:.4f}")
        print(f"Recall: {r:.4f}")
        print(f"F1: {class_f1:.4f}")

        class_results.append({

            "class": name,
            "tp": values["tp"],
            "fp": values["fp"],
            "fn": values["fn"],
            "precision": p,
            "recall": r,
            "f1": class_f1,
        })

    return {

        "confidence": conf,
        "nms_iou": nms_iou,

        "images": processed,

        "tp": tp,
        "fp": fp,
        "fn": fn,

        "precision": precision,
        "recall": recall,
        "f1": f1,

        "class_results": class_results,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("RECYCLIQ - FULL YOLO VALIDATION")
    print("=" * 65)

    # Check paths

    if not MODEL_PATH.exists():

        raise FileNotFoundError(
            f"Model not found: {MODEL_PATH}"
        )

    if not IMAGE_DIR.exists():

        raise FileNotFoundError(
            f"Image directory not found: {IMAGE_DIR}"
        )

    # Collect validation images

    images = sorted([
        p for p in IMAGE_DIR.iterdir()
        if p.suffix.lower() in IMAGE_EXTENSIONS
    ])

    if not images:

        raise RuntimeError(
            "No validation images found."
        )

    print(f"\nModel: {MODEL_PATH}")
    print(f"Validation directory: {IMAGE_DIR}")
    print(f"Validation images: {len(images)}")

    print("\nLoading V3 model...")

    model = YOLO(str(MODEL_PATH))

    all_results = []

    # Run every configuration

    for conf, nms_iou in CONFIGURATIONS:

        result = run_validation(
            model,
            images,
            conf,
            nms_iou
        )

        all_results.append(result)

    # ========================================================
    # CONFIGURATION COMPARISON
    # ========================================================

    print("\n\n")
    print("=" * 85)
    print("FINAL CONFIGURATION COMPARISON")
    print("=" * 85)

    print(
        f"{'CONF':<10}"
        f"{'NMS IOU':<12}"
        f"{'PRECISION':<14}"
        f"{'RECALL':<12}"
        f"{'F1':<12}"
        f"{'TP':<10}"
        f"{'FP':<10}"
        f"{'FN':<10}"
    )

    for result in all_results:

        print(
            f"{result['confidence']:<10.2f}"
            f"{result['nms_iou']:<12.2f}"
            f"{result['precision']:<14.4f}"
            f"{result['recall']:<12.4f}"
            f"{result['f1']:<12.4f}"
            f"{result['tp']:<10}"
            f"{result['fp']:<10}"
            f"{result['fn']:<10}"
        )

    # ========================================================
    # SAVE CSV
    # ========================================================

    output_path = BASE_DIR / "full_validation_results.csv"

    with open(
        output_path,
        "w",
        newline=""
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "confidence",
            "nms_iou",
            "images",
            "tp",
            "fp",
            "fn",
            "precision",
            "recall",
            "f1",
        ])

        for result in all_results:

            writer.writerow([
                result["confidence"],
                result["nms_iou"],
                result["images"],
                result["tp"],
                result["fp"],
                result["fn"],
                result["precision"],
                result["recall"],
                result["f1"],
            ])

    # Save detailed per-class results separately

    class_output_path = (
        BASE_DIR / "full_validation_class_results.csv"
    )

    with open(
        class_output_path,
        "w",
        newline=""
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "confidence",
            "nms_iou",
            "class",
            "tp",
            "fp",
            "fn",
            "precision",
            "recall",
            "f1",
        ])

        for result in all_results:

            for cls_result in result["class_results"]:

                writer.writerow([
                    result["confidence"],
                    result["nms_iou"],
                    cls_result["class"],
                    cls_result["tp"],
                    cls_result["fp"],
                    cls_result["fn"],
                    cls_result["precision"],
                    cls_result["recall"],
                    cls_result["f1"],
                ])

    print("\n" + "=" * 65)
    print("VALIDATION COMPLETED")
    print("=" * 65)

    print(f"Overall results: {output_path}")
    print(f"Class results: {class_output_path}")


if __name__ == "__main__":
    main()