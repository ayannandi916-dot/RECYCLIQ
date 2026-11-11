from pathlib import Path
from ultralytics import YOLO

MODEL = Path("../runs/runs/recycliq/yolo11n_100ep/weights/best.pt")

IMAGE_DIR = Path("datasets/waste/cleaned/detection/valid/images")

image_names = [
    "biodegradable382_jpg.rf.1f7f0cb86d2e3fa01b87b545ab74336c.jpg",
    "paper1350_jpg.rf.62f47694e3d87b864e8f99e865a2cbe7.jpg"
]

model = YOLO(str(MODEL))

for name in image_names:
    image = IMAGE_DIR / name

    if not image.exists():
        print(f"Missing image: {image}")
        continue

    print(f"\n{'=' * 60}")
    print(f"IMAGE: {name}")

    for conf, iou in [(0.25, 0.70), (0.40, 0.50)]:
        results = model.predict(
            source=str(image),
            imgsz=640,
            conf=conf,
            iou=iou,
            device="cpu",
            verbose=False
        )

        result = results[0]
        boxes = result.boxes

        print(f"\nConfiguration: conf={conf}, iou={iou}")
        print(f"Total detections: {len(boxes)}")

        for box in boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()

            print(
                f"{model.names[class_id]}: {confidence:.3f}"
                 f"Box: {[round(v, 1) for v in xyxy]}"
            )