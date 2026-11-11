from pathlib import Path
import random

from ultralytics import YOLO

# Project paths
MODEL_PATH = Path(
    "../runs/runs/recycliq/yolo11n_100ep/weights/best.pt"
)

VALID_IMAGES = Path(
    "datasets/waste/cleaned/detection/valid/images"
)

OUTPUT_DIR = Path("../runs/recycliq")

# Reproducible sample selection
random.seed(42)

# Load model
print("Loading RECYCLIQ YOLO model...")

model = YOLO(str(MODEL_PATH))

# Collect validation images
image_extensions = {".jpg", ".jpeg", ".png", ".webp"}

images = [
    p for p in VALID_IMAGES.iterdir()
    if p.suffix.lower() in image_extensions
]

if len(images) < 20:
    raise RuntimeError("Not enough validation images found.")

# Select 20 images
selected_images = random.sample(images, 20)

print(f"\nSelected {len(selected_images)} images.")

# Run inference
print("\nRunning inference...")

results = model.predict(
    source=[str(p) for p in selected_images],
    imgsz=640,
    conf=0.40,
    iou=0.50,
    device="cpu",
    save=True,
    save_conf=True,
    project=str(OUTPUT_DIR),
    name="v3_visual_review_conf40",
    exist_ok=True
)

# Print detection summary
print("\n========== INFERENCE SUMMARY ==========")

for image_path, result in zip(selected_images, results):

    boxes = result.boxes
    count = len(boxes) if boxes is not None else 0

    print(f"\nImage: {image_path.name}")
    print(f"Objects detected: {count}")

    if boxes is not None:
        for box in boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])

            label = model.names[class_id]

            print(
                f"  {label}: {confidence:.3f}"
            )

print("\nVisual inference testing completed!")

print(
    "\nResults saved in:",
    OUTPUT_DIR / "v3_visual_review_conf40"
)