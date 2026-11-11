from pathlib import Path
import numpy as np
from ultralytics import YOLO

MODEL = Path("../runs/runs/recycliq/yolo11n_100ep/weights/best.pt")

BASE = Path("datasets/waste/cleaned/detection/valid")
IMAGE_DIR = BASE / "images"
LABEL_DIR = BASE / "labels"

IMAGE_NAME = (
    "biodegradable382_jpg.rf."
    "1f7f0cb86d2e3fa01b87b545ab74336c.jpg"
)

CLASS_NAMES = [
    "BIODEGRADABLE",
    "CARDBOARD",
    "GLASS",
    "METAL",
    "PAPER",
    "PLASTIC"
]

IOU_MATCH = 0.50

def calculate_iou(box1, box2):
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0, x2-x1) * max(0, y2-y1)

    area1 = max(0, box1[2]-box1[0]) * max(0, box1[3]-box1[1])
    area2 = max(0, box2[2]-box2[0]) * max(0, box2[3]-box2[1])

    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0


def load_ground_truth(label_path, width, height):
    objects = []

    for line in label_path.read_text().splitlines():
        values = line.split()

        if len(values) != 5:
            continue

        cls, xc, yc, bw, bh = map(float, values)

        box = [
            (xc-bw/2)*width,
            (yc-bh/2)*height,
            (xc+bw/2)*width,
            (yc+bh/2)*height
        ]

        objects.append((int(cls), box))

    return objects


model = YOLO(str(MODEL))

image_path = IMAGE_DIR / IMAGE_NAME
label_path = LABEL_DIR / f"{image_path.stem}.txt"

# Use each configuration separately
for conf, nms_iou in [
    (0.25, 0.70),
    (0.30, 0.50),
    (0.35, 0.50),
    (0.40, 0.50)
]:

    result = model.predict(
        source=str(image_path),
        imgsz=640,
        conf=conf,
        iou=nms_iou,
        device="cpu",
        verbose=False
    )[0]

    height, width = result.orig_shape

    ground_truth = load_ground_truth(
        label_path, width, height
    )

    predictions = []

    for box in result.boxes:
        predictions.append((
            int(box.cls[0]),
            box.xyxy[0].tolist(),
            float(box.conf[0])
        ))

    matched_gt = set()
    tp = 0

    # Highest-confidence predictions first
    predictions.sort(key=lambda x: x[2], reverse=True)

    for pred_class, pred_box, confidence in predictions:

        best_iou = 0
        best_index = None

        for index, (gt_class, gt_box) in enumerate(ground_truth):

            if index in matched_gt or pred_class != gt_class:
                continue

            iou = calculate_iou(pred_box, gt_box)

            if iou > best_iou:
                best_iou = iou
                best_index = index

        if best_index is not None and best_iou >= IOU_MATCH:
            tp += 1
            matched_gt.add(best_index)

    fp = len(predictions) - tp
    fn = len(ground_truth) - tp

    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0

    print(f"\nConfiguration: conf={conf}, NMS IoU={nms_iou}")
    print(f"Ground truth: {len(ground_truth)}")
    print(f"Predictions: {len(predictions)}")
    print(f"TP: {tp}, FP: {fp}, FN: {fn}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")