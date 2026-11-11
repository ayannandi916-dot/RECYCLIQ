from pathlib import Path
from collections import Counter

ROOT = Path("datasets/waste/general/Trash Detection Dataset/CUSTOM_DATASET")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
CLASS_NAMES = {
    0: "BIODEGRADABLE",
    1: "CARDBOARD",
    2: "GLASS",
    3: "METAL",
    4: "PAPER",
    5: "PLASTIC"
}

total_images = 0
total_labels = 0
total_objects = 0

class_counts = Counter()
issues = []

for split in ["train", "valid", "test"]:

    image_dir = ROOT / split / "images"
    label_dir = ROOT / split / "labels"

    images = {
        p.stem for p in image_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    }

    labels = {
        p.stem: p for p in label_dir.glob("*.txt")
    }

    missing_labels = images - labels.keys()
    orphan_labels = labels.keys() - images

    total_images += len(images)
    total_labels += len(labels)

    print(f"\n--- {split.upper()} ---")
    print("Images:", len(images))
    print("Labels:", len(labels))
    print("Missing labels:", len(missing_labels))
    print("Orphan labels:", len(orphan_labels))

    for stem in sorted(missing_labels):
        issues.append(f"Missing label: {split}/{stem}")

    for stem in sorted(orphan_labels):
        issues.append(f"Orphan label: {split}/{stem}")

    for stem, label_path in labels.items():

        for line_number, line in enumerate(
            label_path.read_text().splitlines(), start=1
        ):

            if not line.strip():
                continue

            parts = line.split()

            if len(parts) != 5:
                issues.append(
                    f"Malformed row: {label_path}, line {line_number}"
                )
                continue

            try:
                class_id = int(parts[0])
                x, y, w, h = map(float, parts[1:])
            except ValueError:
                issues.append(
                    f"Invalid values: {label_path}, line {line_number}"
                )
                continue

            if class_id not in CLASS_NAMES:
                issues.append(
                    f"Invalid class ID {class_id}: {label_path}"
                )
                continue

            if not all(0 <= v <= 1 for v in (x, y, w, h)):
                issues.append(
                    f"Coordinates outside [0,1]: {label_path}"
                )
                continue

            if w <= 0 or h <= 0:
                issues.append(
                    f"Invalid bounding box size: {label_path}"
                )
                continue

            if x - w / 2 < -1e-6 or x + w / 2 > 1 + 1e-6:
                issues.append(
                    f"Bounding box exceeds image width: {label_path}"
                )

            if y - h / 2 < -1e-6 or y + h / 2 > 1 + 1e-6:
                issues.append(
                    f"Bounding box exceeds image height: {label_path}"
                )

            class_counts[class_id] += 1
            total_objects += 1

print("\n========== SUMMARY ==========")
print("Total images:", total_images)
print("Total label files:", total_labels)
print("Total annotated objects:", total_objects)

print("\nCLASS DISTRIBUTION")

for class_id, name in CLASS_NAMES.items():
    print(f"{class_id}: {name}: {class_counts[class_id]}")

print("\nTOTAL ISSUES:", len(issues))

for issue in issues[:30]:
    print("WARNING:", issue)



    print("\n========== ISSUE BREAKDOWN ==========")

issue_types = Counter(
    issue.split(":")[0] for issue in issues
)

for issue_type, count in issue_types.most_common():
    print(f"{issue_type}: {count}")