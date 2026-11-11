from pathlib import Path
from collections import Counter

ROOT = Path(
    "datasets/waste/general/Trash Detection Dataset/CUSTOM_DATASET"
)

reasons = Counter()
examples = []

for split in ["train", "valid", "test"]:

    label_dir = ROOT / split / "labels"

    for file in label_dir.glob("*.txt"):

        for line_no, line in enumerate(
            file.read_text().splitlines(), 1
        ):

            if not line.strip():
                continue

            parts = line.split()

            try:
                values = [float(x) for x in parts]
            except ValueError:
                reasons["Non-numeric values"] += 1
                continue

            if len(values) == 5:
                reasons["5-value bounding box"] += 1

            elif len(values) > 5 and len(values) % 2 == 1:
                reasons["Possible segmentation annotation"] += 1

            else:
                reasons[f"Unexpected {len(values)} values"] += 1

            if len(parts) != 5 and len(examples) < 15:
                examples.append({
                    "file": file.name,
                    "line": line_no,
                    "values": len(parts),
                    "content": line
                })

print("\nANNOTATION FORMAT SUMMARY")

for reason, count in reasons.items():
    print(reason, ":", count)

print("\nFIRST 15 NON-STANDARD ROWS")

for item in examples:
    print("\nFile:", item["file"])
    print("Line:", item["line"])
    print("Number of values:", item["values"])
    print("Content:", item["content"])