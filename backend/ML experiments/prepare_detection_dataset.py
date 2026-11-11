from pathlib import Path
from collections import Counter
import shutil
import math
import cv2

# ==========================================
# CONFIGURATION
# ==========================================

SOURCE = Path(
    "datasets/waste/general/Trash Detection Dataset/CUSTOM_DATASET"
)

OUTPUT = Path("datasets/waste/cleaned/detection")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

CLASS_NAMES = [
    "BIODEGRADABLE",
    "CARDBOARD",
    "GLASS",
    "METAL",
    "PAPER",
    "PLASTIC"
]

SPLITS = ["train", "valid", "test"]

# ==========================================
# SAFETY CHECK
# ==========================================

if not SOURCE.exists():
    raise SystemExit(f"Dataset not found: {SOURCE}")

if OUTPUT.exists() and any(OUTPUT.iterdir()):
    raise SystemExit(
        f"\nOutput directory already contains files:\n{OUTPUT}\n"
        "Move or rename the existing output before running again."
    )

OUTPUT.mkdir(parents=True, exist_ok=True)

# ==========================================
# STATISTICS
# ==========================================

stats = Counter()
class_counts = Counter()
rejected_samples = []
duplicate_samples = []

# ==========================================
# ANNOTATION CONVERSION
# ==========================================

def convert_annotation(label_path):

    converted_rows = []

    lines = label_path.read_text(encoding="utf-8").splitlines()

    for line_number, line in enumerate(lines, start=1):

        if not line.strip():
            continue

        parts = line.split()

        try:
            values = [float(value) for value in parts]

            if len(values) < 5:
                raise ValueError("Too few values")

            if not all(math.isfinite(v) for v in values):
                raise ValueError("Non-finite values")

            class_id = int(values[0])

            if values[0] != class_id or not 0 <= class_id < len(CLASS_NAMES):
                raise ValueError("Invalid class ID")

            coordinates = values[1:]

            # ----------------------------------
            # STANDARD YOLO BOUNDING BOX
            # ----------------------------------

            if len(coordinates) == 4:

                x, y, w, h = coordinates

                if not all(0 <= v <= 1 for v in coordinates):
                    raise ValueError("Bounding box coordinate outside [0,1]")

                if w <= 0 or h <= 0:
                    raise ValueError("Invalid bounding box dimensions")

                if (
                    x - w / 2 < -1e-6
                    or x + w / 2 > 1 + 1e-6
                    or y - h / 2 < -1e-6
                    or y + h / 2 > 1 + 1e-6
                ):
                    raise ValueError("Bounding box outside image")

                bbox = (x, y, w, h)

                stats["original_bbox_rows"] += 1

            # ----------------------------------
            # YOLO SEGMENTATION POLYGON
            # ----------------------------------

            elif len(coordinates) >= 6 and len(coordinates) % 2 == 0:

                if not all(0 <= v <= 1 for v in coordinates):
                    raise ValueError("Polygon coordinate outside [0,1]")

                xs = coordinates[0::2]
                ys = coordinates[1::2]

                xmin = min(xs)
                xmax = max(xs)

                ymin = min(ys)
                ymax = max(ys)

                w = xmax - xmin
                h = ymax - ymin

                if w <= 0 or h <= 0:
                    raise ValueError("Invalid polygon dimensions")

                x = (xmin + xmax) / 2
                y = (ymin + ymax) / 2

                bbox = (x, y, w, h)

                stats["converted_polygon_rows"] += 1

            else:
                raise ValueError(
                    f"Unexpected number of coordinates: {len(coordinates)}"
                )

            converted_rows.append(
                f"{class_id} "
                f"{bbox[0]:.8f} "
                f"{bbox[1]:.8f} "
                f"{bbox[2]:.8f} "
                f"{bbox[3]:.8f}"
            )

            class_counts[class_id] += 1

        except (ValueError, OverflowError) as error:

            raise ValueError(
                f"Line {line_number}: {error}"
            ) from error

    return converted_rows


# ==========================================
# PROCESS EACH DATASET SPLIT
# ==========================================

for split in SPLITS:

    print(f"\nProcessing {split.upper()}...")

    source_images = SOURCE / split / "images"
    source_labels = SOURCE / split / "labels"

    output_images = OUTPUT / split / "images"
    output_labels = OUTPUT / split / "labels"

    output_images.mkdir(parents=True, exist_ok=True)
    output_labels.mkdir(parents=True, exist_ok=True)

    images = sorted(
        p for p in source_images.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )

    processed = 0

    for image_path in images:

        stem = image_path.stem

        # ----------------------------------
        # EXCLUDE IDENTICAL DUPLICATE IMAGES
        # ----------------------------------

        if stem.endswith("(1)"):

            duplicate_samples.append(image_path.name)

            stats["duplicate_images_skipped"] += 1

            continue

        label_path = source_labels / f"{stem}.txt"

        # ----------------------------------
        # CHECK MATCHING LABEL
        # ----------------------------------

        if not label_path.exists():

            rejected_samples.append(
                f"{split}/{image_path.name}: Missing annotation"
            )

            stats["missing_labels"] += 1

            continue

        # ----------------------------------
        # VALIDATE IMAGE
        # ----------------------------------

        image = cv2.imread(str(image_path))

        if image is None:

            rejected_samples.append(
                f"{split}/{image_path.name}: Unreadable image"
            )

            stats["unreadable_images"] += 1

            continue

        # ----------------------------------
        # CONVERT ANNOTATIONS
        # ----------------------------------

        try:

            converted = convert_annotation(label_path)

        except ValueError as error:

            rejected_samples.append(
                f"{split}/{image_path.name}: {error}"
            )

            stats["invalid_samples"] += 1

            continue

        # ----------------------------------
        # COPY VALID IMAGE AND LABEL
        # ----------------------------------

        shutil.copy2(
            image_path,
            output_images / image_path.name
        )

        (output_labels / f"{stem}.txt").write_text(
            "\n".join(converted) + ("\n" if converted else ""),
            encoding="utf-8"
        )

        processed += 1

    stats[f"{split}_images"] = processed

    print(f"Successfully processed: {processed}")


# ==========================================
# CREATE YOLO DATA YAML
# ==========================================

yaml_content = f"""path: {OUTPUT.resolve().as_posix()}

train: train/images
val: valid/images
test: test/images

nc: {len(CLASS_NAMES)}

names:
"""

for index, name in enumerate(CLASS_NAMES):
    yaml_content += f"  {index}: {name}\n"

(OUTPUT / "data.yaml").write_text(
    yaml_content,
    encoding="utf-8"
)

# ==========================================
# GENERATE CLEANING REPORT
# ==========================================

report = []

report.append("RECYCLIQ DATASET CLEANING REPORT")
report.append("=" * 45)

report.append("\nSPLIT STATISTICS")

for split in SPLITS:
    report.append(
        f"{split}: {stats[f'{split}_images']} images"
    )

report.append("\nANNOTATION STATISTICS")

report.append(
    f"Original bounding boxes: {stats['original_bbox_rows']}"
)

report.append(
    f"Converted segmentation polygons: {stats['converted_polygon_rows']}"
)

report.append("\nCLEANING STATISTICS")

for key, value in stats.items():
    report.append(f"{key}: {value}")

report.append("\nCLASS DISTRIBUTION")

for class_id, name in enumerate(CLASS_NAMES):
    report.append(
        f"{class_id} - {name}: {class_counts[class_id]}"
    )

report.append("\nREJECTED SAMPLES")

for sample in rejected_samples:
    report.append(sample)

report.append("\nDUPLICATE IMAGES SKIPPED")

for sample in duplicate_samples:
    report.append(sample)

report_text = "\n".join(report)

(OUTPUT / "cleaning_report.txt").write_text(
    report_text,
    encoding="utf-8"
)

print("\n========== CLEANING COMPLETED ==========")

print(report_text)

print(f"\nOutput directory: {OUTPUT.resolve()}")