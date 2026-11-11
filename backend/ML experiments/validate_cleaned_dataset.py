from pathlib import Path
from collections import Counter
import math
import cv2

ROOT = Path("datasets/waste/cleaned/detection")

SPLITS = ["train", "valid", "test"]

CLASS_NAMES = [
    "BIODEGRADABLE",
    "CARDBOARD",
    "GLASS",
    "METAL",
    "PAPER",
    "PLASTIC"
]

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

stats = Counter()
class_counts = Counter()
issues = []

for split in SPLITS:

    print(f"\n========== {split.upper()} ==========")

    image_dir = ROOT / split / "images"
    label_dir = ROOT / split / "labels"

    images = [
        p for p in image_dir.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONS
    ]

    labels = list(label_dir.glob("*.txt"))

    image_stems = {p.stem for p in images}
    label_stems = {p.stem for p in labels}

    missing = image_stems - label_stems
    orphan = label_stems - image_stems

    stats[f"{split}_images"] = len(images)

    print("Images:", len(images))
    print("Labels:", len(labels))
    print("Missing labels:", len(missing))
    print("Orphan labels:", len(orphan))

    for name in missing:
        issues.append(f"{split}: Missing label for {name}")

    for name in orphan:
        issues.append(f"{split}: Orphan label {name}")

    for image_path in images:

        image = cv2.imread(str(image_path))

        if image is None:
            issues.append(f"Unreadable image: {image_path.name}")
            continue

        label_path = label_dir / f"{image_path.stem}.txt"

        if not label_path.exists():
            continue

        for line_no, line in enumerate(
            label_path.read_text().splitlines(), 1
        ):

            if not line.strip():
                continue

            parts = line.split()

            if len(parts) != 5:
                issues.append(
                    f"{label_path.name}:{line_no} "
                    f"Expected 5 values, found {len(parts)}"
                )
                continue

            try:
                class_value = float(parts[0])
                x, y, w, h = map(float, parts[1:])

                if not math.isfinite(class_value) or not all(
                    math.isfinite(v) for v in (x, y, w, h)
                ):
                    raise ValueError("Non-finite values")

                class_id = int(class_value)

                if class_value != class_id or not 0 <= class_id < 6:
                    raise ValueError("Invalid class ID")

                if not all(0 <= v <= 1 for v in (x, y, w, h)):
                    raise ValueError("Coordinate outside [0,1]")

                if w <= 0 or h <= 0:
                    raise ValueError("Invalid dimensions")

                if (
                    x - w / 2 < -1e-6
                    or x + w / 2 > 1 + 1e-6
                    or y - h / 2 < -1e-6
                    or y + h / 2 > 1 + 1e-6
                ):
                    raise ValueError("Bounding box outside image")

                class_counts[class_id] += 1
                stats["valid_annotations"] += 1

            except (ValueError, OverflowError) as error:

                issues.append(
                    f"{label_path.name}:{line_no} - {error}"
                )

print("\n========== CLASS DISTRIBUTION ==========")

for class_id, name in enumerate(CLASS_NAMES):
    print(f"{class_id}: {name}: {class_counts[class_id]}")

print("\n========== FINAL SUMMARY ==========")

print("Total images:", sum(stats[f"{s}_images"] for s in SPLITS))
print("Total valid annotations:", stats["valid_annotations"])
print("Total issues:", len(issues))

for issue in issues[:50]:
    print("WARNING:", issue)

if not issues:
    print("\nSUCCESS: Cleaned dataset passed validation!")
else:
    print("\nVALIDATION FAILED: Investigate the warnings.")