from pathlib import Path
import cv2

from ultralytics import YOLO

MODEL_PATH = Path(
    "../runs/runs/recycliq/yolo11n_100ep/weights/best.pt"
)

BASE = Path("datasets/waste/cleaned/detection/valid")

IMAGE_DIR = BASE / "images"
LABEL_DIR = BASE / "labels"

OUTPUT_DIR = Path("../runs/recycliq/ground_truth_comparison")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CLASS_NAMES = [
    "BIODEGRADABLE",
    "CARDBOARD",
    "GLASS",
    "METAL",
    "PAPER",
    "PLASTIC"
]

IMAGE_NAMES = [
    "biodegradable382_jpg.rf.1f7f0cb86d2e3fa01b87b545ab74336c.jpg",
    "paper1350_jpg.rf.62f47694e3d87b864e8f99e865a2cbe7.jpg"
]

model = YOLO(str(MODEL_PATH))

for name in IMAGE_NAMES:

    image_path = IMAGE_DIR / name
    label_path = LABEL_DIR / f"{image_path.stem}.txt"

    image = cv2.imread(str(image_path))

    if image is None:
        print(f"Could not read image: {image_path}")
        continue

    height, width = image.shape[:2]

    # Draw ground-truth boxes in GREEN
    with open(label_path, "r") as f:

        for line in f:

            values = line.strip().split()

            if len(values) != 5:
                continue

            cls, xc, yc, bw, bh = map(float, values)

            x1 = int((xc - bw / 2) * width)
            y1 = int((yc - bh / 2) * height)
            x2 = int((xc + bw / 2) * width)
            y2 = int((yc + bh / 2) * height)

            class_name = CLASS_NAMES[int(cls)]

            cv2.rectangle(
                image,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )

            cv2.putText(
                image,
                f"GT: {class_name}",
                (max(0, x1), max(20, y1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )

    # Draw predictions in RED
    results = model.predict(
        source=str(image_path),
        imgsz=640,
        conf=0.40,
        iou=0.50,
        device="cpu",
        verbose=False
    )

    for box in results[0].boxes:

        x1, y1, x2, y2 = map(
            int, box.xyxy[0].tolist()
        )

        cls = int(box.cls[0])
        confidence = float(box.conf[0])

        label = (
            f"PRED: {CLASS_NAMES[cls]} "
            f"{confidence:.2f}"
        )

        cv2.rectangle(
            image,
            (x1, y1),
            (x2, y2),
            (0, 0, 255),
            2
        )

        cv2.putText(
            image,
            label,
            (max(0, x1), max(20, y1 + 18)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 0, 255),
            2
        )

    output_path = OUTPUT_DIR / name

    cv2.imwrite(str(output_path), image)

    print(f"Saved: {output_path}")

print("\nGround truth comparison completed!")