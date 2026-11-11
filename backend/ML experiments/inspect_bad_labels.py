from pathlib import Path
from collections import Counter

ROOT = Path(
    "datasets/waste/general/Trash Detection Dataset/CUSTOM_DATASET"
)

malformed = []
reason_counts = Counter()

for split in ["train", "valid", "test"]:

    label_dir = ROOT / split / "labels"

    for label_file in label_dir.glob("*.txt"):

        for line_number, line in enumerate(
            label_file.read_text().splitlines(), start=1
        ):

            if not line.strip():
                continue

            parts = line.split()
            reason = None

            if len(parts) != 5:
                reason = f"Expected 5 values, got {len(parts)}"

            else:
                try:
                    class_id = int(parts[0])
                    x, y, w, h = map(float, parts[1:])

                    if class_id not in range(6):
                        reason = "Invalid class ID"

                    elif not all(
                        0 <= value <= 1
                        for value in (x, y, w, h)
                    ):
                        reason = "Coordinate outside [0,1]"

                    elif w <= 0 or h <= 0:
                        reason = "Invalid width/height"

                    elif (
                        x - w / 2 < -1e-6
                        or x + w / 2 > 1 + 1e-6
                        or y - h / 2 < -1e-6
                        or y + h / 2 > 1 + 1e-6
                    ):
                        reason = "Bounding box outside image"

                except ValueError:
                    reason = "Non-numeric annotation"

            if reason:
                reason_counts[reason] += 1

                malformed.append({
                    "file": str(label_file),
                    "line": line_number,
                    "reason": reason,
                    "content": line
                })

print("\n========== MALFORMED ANNOTATION SUMMARY ==========")

for reason, count in reason_counts.items():
    print(f"{reason}: {count}")

print("\n========== FIRST 15 PROBLEMATIC ROWS ==========")

for item in malformed[:15]:
    print("\nFile:", item["file"])
    print("Line:", item["line"])
    print("Reason:", item["reason"])
    print("Content:", item["content"])

print("\nTotal malformed rows:", len(malformed))