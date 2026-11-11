from pathlib import Path
from collections import Counter

ROOT = Path(
    "datasets/waste/general/Trash Detection Dataset/CUSTOM_DATASET"
)

stats = Counter()
examples = []

for split in ["train", "valid", "test"]:

    label_dir = ROOT / split / "labels"

    for file in label_dir.glob("*.txt"):

        for line_no, line in enumerate(
            file.read_text().splitlines(), 1
        ):

            parts = line.split()

            if len(parts) == 5:
                continue

            stats["polygon_rows"] += 1

            try:
                class_id = int(parts[0])
                coords = [float(v) for v in parts[1:]]

                if class_id not in range(6):
                    stats["invalid_class"] += 1

                if len(coords) < 6:
                    stats["too_few_coordinates"] += 1

                if len(coords) % 2 != 0:
                    stats["odd_coordinate_count"] += 1

                if not all(0 <= v <= 1 for v in coords):
                    stats["coordinates_outside_range"] += 1

            except (ValueError, IndexError):
                stats["unparseable_rows"] += 1

                if len(examples) < 10:
                    examples.append(
                        (file.name, line_no, line)
                    )

print("\nPOLYGON VALIDATION")

for key, value in stats.items():
    print(f"{key}: {value}")

print("\nUNPARSEABLE EXAMPLES")

for example in examples:
    print(example)