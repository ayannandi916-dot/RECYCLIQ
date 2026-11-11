import gc
import csv
from pathlib import Path

from ultralytics import YOLO

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent

DATASET = BASE / "datasets/waste/cleaned/detection"

IMAGE_DIR = DATASET / "valid/images"
LABEL_DIR = DATASET / "valid/labels"

MODELS = {
    "V2": PROJECT / "runs/runs/recycliq/yolo11n_60ep/weights/best.pt",
    "V3": PROJECT / "runs/runs/recycliq/yolo11n_100ep/weights/best.pt",
}

CLASS_NAMES = [
    "BIODEGRADABLE",
    "CARDBOARD",
    "GLASS",
    "METAL",
    "PAPER",
    "PLASTIC",
]

CONF = 0.25
NMS_IOU = 0.70
MATCH_IOU = 0.50

def iou(box1, box2):
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter = max(0, x2-x1) * max(0, y2-y1)

    a1 = max(0, box1[2]-box1[0]) * max(0, box1[3]-box1[1])
    a2 = max(0, box2[2]-box2[0]) * max(0, box2[3]-box2[1])

    union = a1 + a2 - inter
    return inter / union if union > 0 else 0


def load_gt(path, width, height):
    objects = []

    if not path.exists():
        return objects

    for line in path.read_text().splitlines():
        values = line.split()

        if len(values) != 5:
            continue

        cls, cx, cy, w, h = map(float, values)

        objects.append({
            "class": int(cls),
            "box": [
                (cx-w/2)*width,
                (cy-h/2)*height,
                (cx+w/2)*width,
                (cy+h/2)*height
            ]
        })

    return objects


def evaluate(predictions, ground_truth):

    stats = {
        c: {"tp": 0, "fp": 0, "fn": 0}
        for c in range(len(CLASS_NAMES))
    }

    for cls in range(len(CLASS_NAMES)):

        preds = sorted(
            [p for p in predictions if p["class"] == cls],
            key=lambda p: p["confidence"],
            reverse=True
        )

        targets = [
            g for g in ground_truth if g["class"] == cls
        ]

        matched = set()

        for pred in preds:

            best_iou = 0
            best_index = None

            for i, gt in enumerate(targets):

                if i in matched:
                    continue

                score = iou(pred["box"], gt["box"])

                if score > best_iou:
                    best_iou = score
                    best_index = i

            if best_index is not None and best_iou >= MATCH_IOU:
                stats[cls]["tp"] += 1
                matched.add(best_index)
            else:
                stats[cls]["fp"] += 1

        stats[cls]["fn"] += len(targets) - len(matched)

    return stats


def metrics(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    f = 2*p*r/(p+r) if p+r else 0
    return p, r, f


def main():

    images = sorted(
        p for p in IMAGE_DIR.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )

    print(f"Validation images: {len(images)}")

    if len(images) != 1008:
        print("WARNING: Expected 1008 images. Check dataset.")

    overall_results = []
    class_results = []

    for model_name, model_path in MODELS.items():

        if not model_path.exists():
            raise FileNotFoundError(model_path)

        print(f"\nLoading {model_name}: {model_path}")

        model = YOLO(str(model_path))

        total = {
            c: {"tp": 0, "fp": 0, "fn": 0}
            for c in range(len(CLASS_NAMES))
        }

        processed = 0

        for image_path in images:

            result = model.predict(
                source=str(image_path),
                imgsz=640,
                conf=CONF,
                iou=NMS_IOU,
                device="cpu",
                verbose=False
            )[0]

            height, width = result.orig_shape

            gt = load_gt(
                LABEL_DIR / f"{image_path.stem}.txt",
                width,
                height
            )

            predictions = []

            if result.boxes is not None:
                for box in result.boxes:
                    predictions.append({
                        "class": int(box.cls[0]),
                        "box": box.xyxy[0].cpu().tolist(),
                        "confidence": float(box.conf[0])
                    })

            image_stats = evaluate(predictions, gt)

            for cls, values in image_stats.items():
                for key in ("tp", "fp", "fn"):
                    total[cls][key] += values[key]

            processed += 1

            if processed % 100 == 0:
                print(f"{model_name}: {processed}/{len(images)}")

            del result, predictions, gt, image_stats

            if processed % 50 == 0:
                gc.collect()

        tp = sum(v["tp"] for v in total.values())
        fp = sum(v["fp"] for v in total.values())
        fn = sum(v["fn"] for v in total.values())

        p, r, f = metrics(tp, fp, fn)

        overall_results.append({
            "model": model_name,
            "images": processed,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": p,
            "recall": r,
            "f1": f
        })

        for cls, name in enumerate(CLASS_NAMES):

            v = total[cls]
            cp, cr, cf = metrics(v["tp"], v["fp"], v["fn"])

            class_results.append({
                "model": model_name,
                "class": name,
                **v,
                "precision": cp,
                "recall": cr,
                "f1": cf
            })

        del model
        gc.collect()

    output = BASE / "v2_v3_comparison.csv"
    class_output = BASE / "v2_v3_class_comparison.csv"

    for path, rows in [
        (output, overall_results),
        (class_output, class_results)
    ]:
        with open(path, "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    print("\n========== V2 vs V3 ==========")

    for row in overall_results:
        print(
            f"{row['model']}: "
            f"P={row['precision']:.4f} "
            f"R={row['recall']:.4f} "
            f"F1={row['f1']:.4f}"
        )

    print(f"\nOverall CSV: {output}")
    print(f"Class CSV: {class_output}")


if __name__ == "__main__":
    main()